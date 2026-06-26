#!/usr/bin/env python3
"""Google account discovery — list all GSC sites and GA4 properties the authenticated user can access."""

import json
import os
import sys
import urllib.request
import urllib.error
import urllib.parse
import sqlite3
from pathlib import Path

DB_PATH = os.environ.get("SEO_OS_DB_PATH", str(Path(__file__).resolve().parent.parent / "data" / "seo-os.sqlite"))
TOKEN_PATH = Path("/root/.hermes/google_token.json")

# ─── Token Management ────────────────────────────────────────────────────────

def load_token():
    """Load Google OAuth token, refreshing if needed."""
    if not TOKEN_PATH.exists():
        return None
    with open(TOKEN_PATH) as f:
        token = json.load(f)
    
    # If token is missing or expired, try refresh
    access_token = token.get("token") or token.get("access_token")
    if not access_token:
        token = refresh_token()
    return token

def refresh_token():
    """Refresh the Google OAuth token."""
    with open(TOKEN_PATH) as f:
        token = json.load(f)
    if "refresh_token" not in token:
        return token
    
    data = urllib.parse.urlencode({
        "client_id": token["client_id"],
        "client_secret": token["client_secret"],
        "refresh_token": token["refresh_token"],
        "grant_type": "refresh_token",
    }).encode()
    
    req = urllib.request.Request(
        "https://oauth2.googleapis.com/token", data=data,
        headers={"Content-Type": "application/x-www-form-urlencoded"}, method="POST"
    )
    try:
        resp = urllib.request.urlopen(req, timeout=10)
        result = json.loads(resp.read())
        token["token"] = result["access_token"]
        with open(TOKEN_PATH, "w") as f:
            json.dump(token, f)
    except Exception as e:
        print(f"Token refresh failed: {e}", file=sys.stderr)
    
    return token

def get_access_token():
    """Get a valid access token string."""
    token = load_token()
    if not token:
        return None
    return token.get("token") or token.get("access_token")

# ─── GSC Site Discovery ──────────────────────────────────────────────────────

def discover_gsc_sites():
    """List all sites from Google Search Console API."""
    access_token = get_access_token()
    if not access_token:
        return {"ok": False, "error": "No valid Google OAuth token", "sites": []}
    
    url = "https://www.googleapis.com/webmasters/v3/sites"
    req = urllib.request.Request(url, headers={
        "Authorization": f"Bearer {access_token}",
        "Accept": "application/json"
    })
    
    try:
        resp = urllib.request.urlopen(req, timeout=15)
        data = json.loads(resp.read())
        sites = data.get("siteEntry", [])
        return {
            "ok": True,
            "sites": [
                {
                    "siteUrl": s.get("siteUrl", ""),
                    "permissionLevel": s.get("permissionLevel", "unknown"),
                    "domain": _extract_domain(s.get("siteUrl", ""))
                }
                for s in sites
            ]
        }
    except urllib.error.HTTPError as e:
        body = e.read().decode() if e.fp else ""
        return {"ok": False, "error": f"GSC API error {e.code}: {body[:200]}", "sites": []}
    except Exception as e:
        return {"ok": False, "error": str(e), "sites": []}

# ─── GA4 Property Discovery ──────────────────────────────────────────────────

def discover_ga4_properties():
    """List all GA4 properties from Google Analytics Admin API."""
    access_token = get_access_token()
    if not access_token:
        return {"ok": False, "error": "No valid Google OAuth token", "properties": []}
    
    # Use accountSummaries to get all accessible properties
    url = "https://analyticsadmin.googleapis.com/v1beta/accountSummaries?pageSize=200"
    req = urllib.request.Request(url, headers={
        "Authorization": f"Bearer {access_token}",
        "Accept": "application/json"
    })
    
    try:
        resp = urllib.request.urlopen(req, timeout=15)
        data = json.loads(resp.read())
        
        properties = []
        for account in data.get("accountSummaries", []):
            account_name = account.get("displayName", "Unknown Account")
            for prop in account.get("propertySummaries", []):
                prop_id = prop.get("property", "").split("/")[-1]  # properties/123456 → 123456
                properties.append({
                    "propertyId": prop_id,
                    "propertyName": prop.get("displayName", ""),
                    "accountName": account_name,
                    "domain": _ga4_property_domain(prop_id, access_token)
                })
        
        return {"ok": True, "properties": properties}
    except urllib.error.HTTPError as e:
        body = e.read().decode() if e.fp else ""
        return {"ok": False, "error": f"GA4 Admin API error {e.code}: {body[:200]}", "properties": []}
    except Exception as e:
        return {"ok": False, "error": str(e), "properties": []}

def _ga4_property_domain(property_id, access_token):
    """Try to get the website URL from GA4 property metadata."""
    url = f"https://analyticsdata.googleapis.com/v1beta/properties/{property_id}/metadata"
    req = urllib.request.Request(url, headers={
        "Authorization": f"Bearer {access_token}",
        "Accept": "application/json"
    })
    try:
        resp = urllib.request.urlopen(req, timeout=10)
        data = json.loads(resp.read())
        return data.get("data", {}).get("websiteUrl", "") or data.get("websiteUrl", "")
    except:
        return ""

# ─── Cross-reference ─────────────────────────────────────────────────────────

def discover_all():
    """Discover GSC sites + GA4 properties and cross-reference with existing clients."""
    gsc = discover_gsc_sites()
    ga4 = discover_ga4_properties()
    
    # Build lookup maps by domain
    gsc_by_domain = {}
    for s in gsc.get("sites", []):
        gsc_by_domain[s["domain"]] = s
    
    ga4_by_domain = {}
    for p in ga4.get("properties", []):
        if p["domain"]:
            ga4_by_domain[p["domain"]] = p
    
    # Get existing client domains from DB
    existing_domains = set()
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        rows = conn.execute("SELECT domain, id FROM clients").fetchall()
        for r in rows:
            existing_domains.add(_extract_domain(r["domain"]))
        conn.close()
    except:
        pass
    
    # Merge: all unique domains from both GSC and GA4
    all_domains = set(gsc_by_domain.keys()) | set(ga4_by_domain.keys())
    
    candidates = []
    for domain in sorted(all_domains):
        if not domain:
            continue
        gsc_info = gsc_by_domain.get(domain, {})
        ga4_info = ga4_by_domain.get(domain, {})
        existing = domain in existing_domains

        candidates.append({
            "domain": domain,
            "name": gsc_info.get("siteUrl", ga4_info.get("propertyName", domain)),
            "businessName": _domain_to_business_name(domain),
            "in_gsc": bool(gsc_info),
            "gsc": bool(gsc_info),
            "ga4": bool(ga4_info),
            "gsc_permission": gsc_info.get("permissionLevel", ""),
            "in_ga4": bool(ga4_info),
            "ga4_property_id": ga4_info.get("propertyId", ""),
            "ga4_property_name": ga4_info.get("propertyName", ""),
            "already_added": existing
        })

    # Also include GA4 properties without a domain match
    for prop in ga4.get("properties", []):
        d = prop.get("domain", "")
        if d and (d in gsc_by_domain or d in [c["domain"] for c in candidates]):
            continue
        candidates.append({
            "domain": d,
            "name": prop.get("propertyName", ""),
            "businessName": prop.get("propertyName", "").replace(" - GA4", ""),
            "in_gsc": False,
            "gsc": False,
            "ga4": True,
            "gsc_permission": "",
            "in_ga4": True,
            "ga4_property_id": prop.get("propertyId", ""),
            "ga4_property_name": prop.get("propertyName", ""),
            "already_added": False,
            "no_domain_match": True
        })

    return {
        "ok": True,
        "gsc_ok": gsc.get("ok", False),
        "gsc_error": gsc.get("error", ""),
        "ga4_ok": ga4.get("ok", False),
        "ga4_error": ga4.get("error", ""),
        "candidates": candidates,
        "sites": [c for c in candidates if not c.get("already_added")],
        "summary": {
            "total": len(candidates),
            "with_gsc": sum(1 for c in candidates if c["in_gsc"]),
            "with_ga4": sum(1 for c in candidates if c["in_ga4"]),
            "already_added": sum(1 for c in candidates if c["already_added"])
        }
    }

# ─── Helpers ─────────────────────────────────────────────────────────────────

def _extract_domain(site_url):
    """Extract clean domain from GSC site URL or any URL. Strips www."""
    if not site_url:
        return ""
    # sc-domain:example.com → example.com
    if site_url.startswith("sc-domain:"):
        d = site_url.replace("sc-domain:", "").strip("/")
    elif "://" in site_url:
        d = site_url.split("://")[1].strip("/").split("/")[0]
    else:
        d = site_url.strip("/")
    # Normalize: strip www.
    if d.startswith("www."):
        d = d[4:]
    return d

def _domain_to_business_name(domain):
    """Convert domain to a reasonable business name."""
    # Remove TLD, capitalize
    name = domain.split(".")[0]
    # Handle multi-part: edelroofing → Edel Roofing (basic)
    import re
    # Split on camelCase or just capitalize
    words = re.sub(r'([A-Z])', r' \1', name).strip()
    if words != name:
        return words.title()
    return name.replace("-", " ").replace("_", " ").title()

# ─── CLI ─────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Discover Google account sites/properties")
    parser.add_argument("--gsc", action="store_true", help="List GSC sites only")
    parser.add_argument("--ga4", action="store_true", help="List GA4 properties only")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    args = parser.parse_args()
    
    if args.gsc:
        result = discover_gsc_sites()
    elif args.ga4:
        result = discover_ga4_properties()
    else:
        result = discover_all()
    
    if args.json:
        print(json.dumps(result, indent=2))
    else:
        if "candidates" in result:
            print(f"\nDiscovered {result['summary']['total']} domains "
                  f"({result['summary']['with_gsc']} with GSC, "
                  f"{result['summary']['with_ga4']} with GA4, "
                  f"{result['summary']['already_added']} already added)\n")
            for c in result["candidates"]:
                gsc = "✓" if c["in_gsc"] else "✗"
                ga4 = "✓" if c["in_ga4"] else "✗"
                added = " [ADDED]" if c["already_added"] else ""
                print(f"  {gsc} GSC  {ga4} GA4  {c['domain']}{added}")
        elif "sites" in result:
            for s in result["sites"]:
                print(f"  {s['siteUrl']} ({s['permissionLevel']})")
        elif "properties" in result:
            for p in result["properties"]:
                print(f"  {p['propertyId']} — {p['propertyName']} ({p.get('domain','')})")
