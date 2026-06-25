#!/usr/bin/env python3
"""
Prospects Google Sheets Sync
Two-way sync between the outreach tracker Google Sheet and the SQLite prospects table.

Sheet columns (14): Business Name, Phone, Search Keyword, City, Niche, Score, Rank,
                    Website, Email, Social URL, FB DM Opener, Channel, Status, Notes

DB columns: id, name, phone, keyword, city, niche, score, rank, website, email,
            social, fb_dm_opener, channel, status, notes, pipeline_stage, created_at, updated_at

Required env vars:
  GOOGLE_OAUTH_CLIENT_ID     - OAuth client ID
  GOOGLE_OAUTH_CLIENT_SECRET - OAuth client secret
"""

import json
import os
import sqlite3
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

# ─── Config ──────────────────────────────────────────────────────────────────
SHEET_ID = os.environ.get('PROSPECTS_SHEET_ID', '1G-I2YI8AX6SAmOEP1ysBZoMETNIHOZi6QKUeBFYJphg')
SHEET_RANGE = 'Outreach!A2:N'  # Skip header row
TOKEN_PATH = '/root/.hermes/google_token.json'

DB_PATH = os.environ.get(
    "SEO_OS_DB_PATH",
    str(Path(__file__).resolve().parent.parent / "data" / "seo-os.sqlite")
)

# ─── HTTP helpers ────────────────────────────────────────────────────────────
def _refresh_token():
    """Refresh the OAuth token."""
    import urllib.request, urllib.parse
    token = json.load(open(TOKEN_PATH))
    client_id = os.environ.get('GOOGLE_OAUTH_CLIENT_ID', '')
    client_secret = os.environ.get('GOOGLE_OAUTH_CLIENT_SECRET', '')
    if not client_id or not client_secret:
        raise RuntimeError("GOOGLE_OAUTH_CLIENT_ID and GOOGLE_OAUTH_CLIENT_SECRET env vars required")
    data = urllib.parse.urlencode({
        'client_id': client_id,
        'client_secret': client_secret,
        'refresh_token': token['refresh_token'],
        'grant_type': 'refresh_token'
    }).encode()
    resp = urllib.request.urlopen('https://oauth2.googleapis.com/token', data=data, timeout=10)
    new_tokens = json.loads(resp.read())
    token['token'] = new_tokens['access_token']
    json.dump(token, open(TOKEN_PATH, 'w'))
    return token['token']


def _get_token():
    """Get the current access token."""
    token = json.load(open(TOKEN_PATH))
    return token['token']


def _api_request(url, data=None, method='GET'):
    """Make an authenticated Google API request with auto-retry on 401."""
    import urllib.request
    token = _get_token()
    headers = {'Authorization': f'Bearer {token}'}
    if data:
        headers['Content-Type'] = 'application/json'
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        resp = urllib.request.urlopen(req, timeout=15)
        return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        if e.code == 401:
            token = _refresh_token()
            headers['Authorization'] = f'Bearer {token}'
            req = urllib.request.Request(url, data=data, headers=headers, method=method)
            resp = urllib.request.urlopen(req, timeout=15)
            return json.loads(resp.read())
        raise


# ─── Sheet operations ────────────────────────────────────────────────────────
def read_sheet():
    """Read all rows from the Google Sheet."""
    url = f'https://sheets.googleapis.com/v4/spreadsheets/{SHEET_ID}/values/{SHEET_RANGE}?valueRenderOption=UNFORMATTED_VALUE'
    data = _api_request(url)
    return data.get('values', [])


def write_cell(row_index, col_index, value):
    """Write a single cell to the Sheet (0-indexed)."""
    col_letter = chr(65 + col_index)
    cell = f'Outreach!{col_letter}{row_index + 2}'
    url = f'https://sheets.googleapis.com/v4/spreadsheets/{SHEET_ID}/values/{cell}?valueInputOption=USER_ENTERED'
    payload = json.dumps({'values': [[str(value)]]}).encode()
    _api_request(url, data=payload, method='PUT')


# ─── DB operations ───────────────────────────────────────────────────────────
def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def get_all_prospects():
    """Get all prospects from DB as dict keyed by name."""
    conn = get_conn()
    rows = conn.execute('SELECT * FROM prospects').fetchall()
    conn.close()
    return {r['name']: dict(r) for r in rows}


def insert_prospect(data):
    """Insert a new prospect into the DB."""
    t = datetime.now(timezone.utc).isoformat()
    conn = get_conn()
    pid = f'prospect_{uuid.uuid4().hex[:12]}'
    # Auto-populate social from website if it's a Facebook URL
    social = data['social']
    if not social and data.get('website') and 'facebook.com' in data['website'].lower():
        social = data['website']
    conn.execute(
        """INSERT INTO prospects (id, name, phone, keyword, city, niche, score, rank,
           website, email, social, fb_dm_opener, channel, status, notes, pipeline_stage,
           created_at, updated_at)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (pid, data['name'], data['phone'], data['keyword'], data['city'], data['niche'],
         data['score'], data['rank'], data['website'], data['email'], social,
         data['fb_dm_opener'], data['channel'], data['status'], data['notes'], 'new', t, t)
    )
    conn.commit()
    conn.close()
    return pid


def update_prospect_from_sheet(data):
    """Update an existing prospect from Sheet data."""
    t = datetime.now(timezone.utc).isoformat()
    conn = get_conn()
    conn.execute(
        """UPDATE prospects SET phone=?, keyword=?, city=?, niche=?, score=?, rank=?,
           website=?, email=?, social=?, fb_dm_opener=?, channel=?, status=?, notes=?,
           updated_at=?
           WHERE name=?""",
        (data['phone'], data['keyword'], data['city'], data['niche'],
         data['score'], data['rank'], data['website'], data['email'], data['social'],
         data['fb_dm_opener'], data['channel'], data['status'], data['notes'], t, data['name'])
    )
    conn.commit()
    conn.close()


# Status normalization map (Sheet values → canonical values)
STATUS_MAP = {
    'new': 'new',
    'contacted': 'contacted',
    'pitched': 'pitched',
    'negotiation': 'negotiation',
    'closed_won': 'closed_won',
    'closed_lost': 'closed_lost',
    'not_interested': 'not_interested',
    'not interested': 'not_interested',
    'wrong_city': 'wrong_city',
    'wrong city': 'wrong_city',
    'engaged': 'engaged',
    'message_sent': 'message_sent',
    'message sent': 'message_sent',
    'replied': 'replied',
    'active': 'active',
    'fb dm sent': 'message_sent',
    'fb_dm_sent': 'message_sent',
}

def normalize_status(raw):
    """Normalize status from Sheet to canonical form."""
    key = str(raw).strip().lower().replace('-', '_').replace('  ', ' ')
    if key in STATUS_MAP:
        return STATUS_MAP[key]
    # Try with underscores replaced by spaces
    key_spaces = key.replace('_', ' ')
    if key_spaces in STATUS_MAP:
        return STATUS_MAP[key_spaces]
    return str(raw).strip().lower().replace(' ', '_') or 'new'


# ─── Sync logic ──────────────────────────────────────────────────────────────
def sheet_row_to_dict(row):
    """Convert a Sheet row (list) to a dict."""
    while len(row) < 14:
        row.append('')
    raw_status = str(row[12]).strip()
    return {
        'name': str(row[0]).strip(),
        'phone': str(row[1]).strip(),
        'keyword': str(row[2]).strip(),
        'city': str(row[3]).strip(),
        'niche': str(row[4]).strip(),
        'score': int(row[5]) if str(row[5]).strip().isdigit() else 0,
        'rank': int(row[6]) if str(row[6]).strip().isdigit() else 0,
        'website': str(row[7]).strip(),
        'email': str(row[8]).strip(),
        'social': str(row[9]).strip(),
        'fb_dm_opener': str(row[10]).strip(),
        'channel': str(row[11]).strip() if str(row[11]).strip() else 'FB DM',
        'status': normalize_status(raw_status) if raw_status else 'new',
        'notes': str(row[13]).strip(),
    }


def pull_from_sheet():
    """Pull new/updated prospects from Google Sheet into DB."""
    sheet_rows = read_sheet()
    if not sheet_rows:
        print("No data found in Sheet")
        return {'pulled': 0, 'updated': 0, 'skipped': 0}

    db_prospects = get_all_prospects()
    pulled = 0
    updated = 0
    skipped = 0

    for row in sheet_rows:
        if not row or not str(row[0]).strip():
            skipped += 1
            continue

        data = sheet_row_to_dict(row)
        name = data['name']

        if name in db_prospects:
            existing = db_prospects[name]
            changed = any(
                str(existing.get(k, '')) != str(v)
                for k, v in data.items()
            )
            if changed:
                update_prospect_from_sheet(data)
                updated += 1
            else:
                skipped += 1
        else:
            insert_prospect(data)
            pulled += 1

    result = {'pulled': pulled, 'updated': updated, 'skipped': skipped}
    print(f"Pull from Sheet: {result}")
    return result


def push_single_status(name, new_status):
    """Push a single prospect's status change back to the Sheet."""
    sheet_rows = read_sheet()
    for i, row in enumerate(sheet_rows):
        if not row or not str(row[0]).strip():
            continue
        if str(row[0]).strip() == name:
            write_cell(i, 12, new_status)
            print(f"Pushed status '{new_status}' for '{name}' to Sheet row {i+2}")
            return True
    print(f"Prospect '{name}' not found in Sheet for write-back")
    return False


def push_to_sheet():
    """Push status changes from DB back to Google Sheet."""
    sheet_rows = read_sheet()
    if not sheet_rows:
        print("No data in Sheet to update")
        return {'pushed': 0, 'skipped': 0}

    db_prospects = get_all_prospects()
    pushed = 0
    skipped = 0

    for i, row in enumerate(sheet_rows):
        if not row or not str(row[0]).strip():
            skipped += 1
            continue

        name = str(row[0]).strip()
        if name not in db_prospects:
            skipped += 1
            continue

        sheet_status = str(row[12]).strip() if len(row) > 12 else ''
        db_status = db_prospects[name]['status']

        if sheet_status != db_status:
            write_cell(i, 12, db_status)
            pushed += 1
        else:
            skipped += 1

    result = {'pushed': pushed, 'skipped': skipped}
    print(f"Push to Sheet: {result}")
    return result


def full_sync():
    """Run a full two-way sync."""
    print(f"\n{'='*50}")
    print(f"Prospects Sync — {datetime.now(timezone.utc).isoformat()}")
    print(f"{'='*50}")

    pull_result = pull_from_sheet()
    push_result = push_to_sheet()

    print(f"\nSync complete: {pull_result['pulled']} new, {pull_result['updated']} updated from Sheet, {push_result['pushed']} status changes pushed to Sheet")
    return {'pull': pull_result, 'push': push_result}


if __name__ == '__main__':
    full_sync()
