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
                prop_name = prop.get("displayName", "")
                domain = _ga4_property_domain(prop_id, access_token)
                # Fallback: extract domain from property name if metadata API didn't return one
                if not domain:
                    domain = _extract_domain(prop_name)
                properties.append({
                    "propertyId": prop_id,
                    "propertyName": prop_name,
                    "accountName": account_name,
                    "domain": domain
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

def _normalize(name):
    """Normalize a name for fuzzy matching: lowercase, strip suffixes, remove non-alnum."""
    import re
    name = name.lower().strip()
    # Remove TLDs
    for tld in [".com", ".net", ".org", ".edu", ".io", ".co"]:
        name = name.replace(tld, "")
    # Remove common suffixes
    for suffix in [" - ga4", " - ga", " ga4", " website", " - gsc", " sc-domain:", " - monsterinsights", "/ ga4"]:
        name = name.replace(suffix, "")
    # Keep only alphanumeric
    return re.sub(r'[^a-z0-9]', '', name)


def _match_score(gsc_domain, ga4_name):
    """Return 0-1 score for how well a GSC domain matches a GA4 property name."""
    g = _normalize(gsc_domain)
    n = _normalize(ga4_name)
    if not g or not n:
        return 0
    # Exact normalized match
    if g == n:
        return 1.0
    # One contains the other
    if g in n or n in g:
        return 0.9
    # Check if domain keyword appears in name (e.g. "rankrgv" in "rankrgv - ga4")
    g_words = set(_normalize(gsc_domain).split('.')) if '.' in gsc_domain else set([g])
    n_words = set(_normalize(ga4_name).split('-')) if '-' in ga4_name else set([n])
    g_core = g.split('.')[0]  # rankrgv from rankrgv.com
    if g_core in n or n in g_core:
        return 0.85
    return 0


def discover_all():
    """Discover GSC sites + GA4 properties, fuzzy-match by name, cross-reference with existing clients."""
    gsc = discover_gsc_sites()
    ga4 = discover_ga4_properties()

    gsc_sites = gsc.get("sites", [])
    ga4_props = ga4.get("properties", [])

    # Deduplicate GSC sites by domain (keep highest permission)
    permission_order = {"siteOwner": 3, "siteFullUser": 2, "siteRestrictedUser": 1, "siteUnverifiedUser": 0}
    gsc_deduped = {}
    for s in gsc_sites:
        d = s["domain"]
        if d not in gsc_deduped or permission_order.get(s.get("permissionLevel",""), 0) > permission_order.get(gsc_deduped[d].get("permissionLevel",""), 0):
            gsc_deduped[d] = s
    gsc_sites = list(gsc_deduped.values())

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

    # Track which GA4 props have been matched
    matched_ga4 = set()

    # First pass: match GSC sites to GA4 properties by name similarity
    candidates = []
    for s in gsc_sites:
        domain = s["domain"]
        best_ga4 = None
        best_score = 0
        for i, p in enumerate(ga4_props):
            if i in matched_ga4:
                continue
            score = _match_score(domain, p.get("propertyName", ""))
            if score > best_score:
                best_score = score
                best_ga4 = i

        # Threshold: 0.7 means "pretty sure it's the same"
        if best_ga4 is not None and best_score >= 0.7:
            matched_ga4.add(best_ga4)
            ga4_info = ga4_props[best_ga4]
        else:
            ga4_info = None

        existing = domain in existing_domains
        candidates.append({
            "domain": domain,
            "name": s.get("siteUrl", domain),
            "businessName": _domain_to_business_name(domain),
            "gsc": True,
            "ga4": bool(ga4_info),
            "gsc_permission": s.get("permissionLevel", ""),
            "ga4_property_id": ga4_info.get("propertyId", "") if ga4_info else "",
            "ga4_property_name": ga4_info.get("propertyName", "") if ga4_info else "",
            "already_added": existing,
            "match_confidence": round(best_score, 2) if ga4_info else 0
        })

    # Second pass: unmatched GA4 properties — try to merge with existing candidate by domain
    for i, p in enumerate(ga4_props):
        if i in matched_ga4:
            continue
        domain = _extract_domain(p.get("domain", "")) if p.get("domain") else ""
        # Check if an existing candidate already has this domain
        merged = False
        for c in candidates:
            if c["domain"] and _extract_domain(c["domain"]) == domain:
                # Merge: this GA4 property is an extra property for the same domain
                c["ga4"] = True
                if not c.get("ga4_property_id"):
                    c["ga4_property_id"] = p.get("propertyId", "")
                    c["ga4_property_name"] = p.get("propertyName", "")
                merged = True
                break
        if not merged:
            candidates.append({
                "domain": p.get("domain", ""),
                "name": p.get("propertyName", ""),
                "businessName": p.get("propertyName", "").replace(" - GA4", "").strip(),
                "gsc": False,
                "ga4": True,
                "gsc_permission": "",
                "ga4_property_id": p.get("propertyId", ""),
                "ga4_property_name": p.get("propertyName", ""),
                "already_added": domain in existing_domains if domain else False,
                "match_confidence": 0
            })

    # Sort: already added last, then by name
    candidates.sort(key=lambda c: (c.get("already_added", False), c.get("businessName", "").lower()))

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
            "with_gsc": sum(1 for c in candidates if c["gsc"]),
            "with_ga4": sum(1 for c in candidates if c["ga4"]),
            "already_added": sum(1 for c in candidates if c["already_added"])
        }
    }

# ─── Helpers ─────────────────────────────────────────────────────────────────

def _extract_domain(site_url):
    """Extract clean domain from GSC site URL, GA4 property name, or any URL. Strips www."""
    if not site_url:
        return ""
    name = site_url.strip()
    # sc-domain:example.com → example.com
    if name.startswith("sc-domain:"):
        d = name.replace("sc-domain:", "").strip("/")
    elif "://" in name:
        d = name.split("://")[1].strip("/").split("/")[0]
    elif "." in name and " " not in name and "-" not in name:
        # Looks like a bare domain: www.edelroofing.com or edelroofing.com
        d = name
    else:
        # GA4 property name like "RankRGV Website" or "Texas Cheap Flights Website" — no domain
        return ""
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
