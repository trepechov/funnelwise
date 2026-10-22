#!/usr/bin/env python3
"""Read-only Google Search Console server, scoped to the brand's property.

Based on the vendored `mcp-google-search-console` 2.0.2 tools, changed so the
property comes from brand.yaml connectors.gsc.site_url: tools default to it
and refuse any other site, and there is no "list every site" tool. That keeps
the scope even on the legacy personal-OAuth path, whose account may see
unrelated sites.

Auth (first that exists in the credentials folder):
  1. google-service-account.json, added to the property as a Restricted user
  2. client_secret.json + gsc_token.json (legacy OAuth refresh token)

`gsc_opportunities` is Funnelwise's language-neutral analysis for the
seo-opportunities skill; `gsc_audit` renders the upstream (Italian) HTML audit.
"""
from __future__ import annotations

import json
import sys
import urllib.parse
from collections import defaultdict
from datetime import date
from pathlib import Path
from typing import List

sys.path.insert(0, str(Path(__file__).resolve().parent))
from lib import bootstrap  # noqa: E402

bootstrap()
from gsc_audit.audit import CTR_BY_POSITION, generate_audit, previous_period  # noqa: E402
from lib.google_auth import load_service_account, refresh_token_access, service_account_token  # noqa: E402
from lib.http import get_json, post_json  # noqa: E402
from lib.mcp_stdio import Server, ToolError  # noqa: E402
from lib.workspace import Brand, load_brand  # noqa: E402

SCOPE = "https://www.googleapis.com/auth/webmasters.readonly"
BASE = "https://www.googleapis.com/webmasters/v3"
INSPECT_BASE = "https://searchconsole.googleapis.com/v1"

server = Server("funnelwise-search-console", instructions=(
    "Google Search Console data for the brand's property only (brand.yaml). site_url arguments are optional "
    "and default to that property. Search data is final after about 3 days: end comparison periods 3 days "
    "before today. For the seo-opportunities skill use gsc_opportunities."
))


def _norm(url: str) -> str:
    return url.strip().rstrip("/").lower()


def site(brand: Brand, site_url: str = "") -> str:
    own = brand.scope_id("gsc")
    if site_url and _norm(site_url) != _norm(own):
        raise ToolError(f"{site_url} is outside this brand's scope; this brand's Search Console property is {own}.")
    return own


def _host_ok(site_url: str, page_url: str) -> bool:
    host = urllib.parse.urlparse(page_url).netloc.lower()
    if site_url.startswith("sc-domain:"):
        domain = site_url[len("sc-domain:"):].lower()
        return host == domain or host.endswith("." + domain)
    return page_url.lower().startswith(site_url.lower().rstrip("/"))


def _token(brand: Brand) -> str:
    sa = brand.credential("google-service-account.json")
    if sa.is_file():
        return service_account_token(load_service_account(sa), SCOPE)
    client, tok = brand.credential("client_secret.json"), brand.credential("gsc_token.json")
    if client.is_file() and tok.is_file():
        c = json.loads(client.read_text(encoding="utf-8"))
        c = c.get("installed", c)
        t = json.loads(tok.read_text(encoding="utf-8"))
        return refresh_token_access(c["client_id"], c["client_secret"], t["refresh_token"])
    raise ToolError("No Search Console credentials yet. See reference/connector-guides/google.md.")


def _api_get(brand: Brand):
    def call(url: str) -> dict:
        return get_json(url, headers={"Authorization": f"Bearer {_token(brand)}"}, service="Search Console")
    return call


def _api_post(brand: Brand):
    def call(url: str, body: dict) -> dict:
        return post_json(url, body, headers={"Authorization": f"Bearer {_token(brand)}"}, service="Search Console")
    return call


def _search(brand: Brand, s: str, body: dict) -> List[dict]:
    enc = urllib.parse.quote(s, safe="")
    return _api_post(brand)(f"{BASE}/sites/{enc}/searchAnalytics/query", body).get("rows", [])


def _check_dates(date_from: str, date_to: str) -> None:
    try:
        a, b = date.fromisoformat(date_from), date.fromisoformat(date_to)
    except ValueError:
        raise ToolError("Dates must be YYYY-MM-DD.")
    if a > b:
        raise ToolError("date_from must be on or before date_to.")


# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------

@server.tool()
def gsc_site() -> dict:
    """Details of the brand's Search Console property (URL and this credential's permission level)."""
    brand = load_brand()
    s = site(brand)
    data = _api_get(brand)(f"{BASE}/sites/{urllib.parse.quote(s, safe='')}")
    return {"site_url": data.get("siteUrl", s), "permission": data.get("permissionLevel")}


@server.tool()
def gsc_query(date_from: str, date_to: str, dimensions: str = "query", row_limit: int = 100,
              query_contains: str = "", page_contains: str = "", site_url: str = "") -> dict:
    """Search performance rows (clicks, impressions, CTR, position) for the brand's property.

    Args:
        date_from: Start date, YYYY-MM-DD.
        date_to: End date, YYYY-MM-DD.
        dimensions: Comma-separated: query, page, country, device, date, searchAppearance.
        row_limit: Maximum rows (max 25000).
        query_contains: Optional filter: only queries containing this text.
        page_contains: Optional filter: only page URLs containing this text.
        site_url: Optional; must be the brand's property if given.
    """
    _check_dates(date_from, date_to)
    brand = load_brand()
    s = site(brand, site_url)
    dims = [d.strip() for d in dimensions.split(",") if d.strip()]
    body = {"startDate": date_from, "endDate": date_to, "dimensions": dims, "rowLimit": max(1, min(row_limit, 25000))}
    filters = []
    if query_contains:
        filters.append({"dimension": "query", "operator": "contains", "expression": query_contains})
    if page_contains:
        filters.append({"dimension": "page", "operator": "contains", "expression": page_contains})
    if filters:
        body["dimensionFilterGroups"] = [{"filters": filters}]
    rows = []
    for r in _search(brand, s, body):
        entry = {dim: r["keys"][i] for i, dim in enumerate(dims)}
        entry.update(clicks=r.get("clicks", 0), impressions=r.get("impressions", 0),
                     ctr=round(r.get("ctr", 0), 4), position=round(r.get("position", 0), 1))
        rows.append(entry)
    return {"site_url": s, "period": {"from": date_from, "to": date_to}, "rows": rows}


@server.tool()
def gsc_performance_overview(date_from: str, date_to: str, compare_previous: bool = True, site_url: str = "") -> dict:
    """Totals for the brand's property: clicks, impressions, CTR, average position, optionally vs the
    previous period of the same length.

    Args:
        date_from: Start date, YYYY-MM-DD.
        date_to: End date, YYYY-MM-DD.
        compare_previous: Also return the previous period of equal length.
        site_url: Optional; must be the brand's property if given.
    """
    _check_dates(date_from, date_to)
    brand = load_brand()
    s = site(brand, site_url)

    def totals(a: str, b: str) -> dict:
        rows = _search(brand, s, {"startDate": a, "endDate": b})
        r = rows[0] if rows else {}
        return {"from": a, "to": b, "clicks": r.get("clicks", 0), "impressions": r.get("impressions", 0),
                "ctr": round(r.get("ctr", 0), 4), "position": round(r.get("position", 0), 1)}

    out = {"site_url": s, "current": totals(date_from, date_to)}
    if compare_previous:
        out["previous"] = totals(*previous_period(date_from, date_to))
    return out


@server.tool()
def gsc_indexing_issues(pages: List[str], site_url: str = "") -> dict:
    """Check whether pages of the brand's site are indexed (URL Inspection API, max 20 pages per call).

    Args:
        pages: Full page URLs on the brand's site.
        site_url: Optional; must be the brand's property if given.
    """
    brand = load_brand()
    s = site(brand, site_url)
    outside = [p for p in pages if not _host_ok(s, p)]
    if outside:
        raise ToolError(f"These pages are not on {s}: {', '.join(outside[:5])}")
    results = []
    for page in pages[:20]:
        try:
            data = _api_post(brand)(f"{INSPECT_BASE}/urlInspection/index:inspect", {"inspectionUrl": page, "siteUrl": s})
            st = data.get("inspectionResult", {}).get("indexStatusResult", {})
            results.append({"url": page, "verdict": st.get("verdict", "UNKNOWN"), "coverageState": st.get("coverageState", ""),
                            "robotsTxtState": st.get("robotsTxtState", ""), "indexingState": st.get("indexingState", ""),
                            "lastCrawlTime": st.get("lastCrawlTime", ""), "pageFetchState": st.get("pageFetchState", ""),
                            "googleCanonical": st.get("googleCanonical", ""), "userCanonical": st.get("userCanonical", "")})
        except ToolError as e:
            results.append({"url": page, "error": str(e)})
    return {"site_url": s, "results": results}


@server.tool()
def gsc_inspect_url(page_url: str, site_url: str = "") -> dict:
    """Full URL Inspection result for one page of the brand's site.

    Args:
        page_url: Full page URL on the brand's site.
        site_url: Optional; must be the brand's property if given.
    """
    brand = load_brand()
    s = site(brand, site_url)
    if not _host_ok(s, page_url):
        raise ToolError(f"{page_url} is not on {s}.")
    data = _api_post(brand)(f"{INSPECT_BASE}/urlInspection/index:inspect", {"inspectionUrl": page_url, "siteUrl": s})
    return data.get("inspectionResult", {})


@server.tool()
def gsc_sitemaps(site_url: str = "") -> dict:
    """Sitemaps submitted for the brand's property, with errors and warnings.

    Args:
        site_url: Optional; must be the brand's property if given.
    """
    brand = load_brand()
    s = site(brand, site_url)
    data = _api_get(brand)(f"{BASE}/sites/{urllib.parse.quote(s, safe='')}/sitemaps")
    return {"site_url": s, "sitemaps": [{
        "path": sm.get("path", ""), "lastSubmitted": sm.get("lastSubmitted", ""), "isPending": sm.get("isPending", False),
        "lastDownloaded": sm.get("lastDownloaded", ""), "warnings": sm.get("warnings", 0), "errors": sm.get("errors", 0),
    } for sm in data.get("sitemap", [])]}


def expected_ctr(position: float) -> float:
    return CTR_BY_POSITION.get(max(1, min(10, int(round(position)))), 0.015)


def brand_terms(brand: Brand) -> List[str]:
    b = brand.data["brand"]
    terms = {b["name"].lower(), b["name"].lower().replace(" ", "")}
    if b.get("short"):
        terms.add(b["short"].lower())
    host = urllib.parse.urlparse(b.get("website", "")).netloc.lower().replace("www.", "")
    if host:
        terms.add(host.split(".")[0])
    return sorted(t for t in terms if len(t) >= 3)


def analyse_opportunities(query_rows: List[dict], query_page_rows: List[dict], page_rows: List[dict],
                          prev_page_rows: List[dict], terms: List[str], min_impressions: int) -> dict:
    """Pure analysis over Search Analytics rows ({keys, clicks, impressions, ctr, position})."""
    def is_brand(q: str) -> bool:
        flat = q.lower().replace(" ", "")
        return any(t.replace(" ", "") in flat for t in terms)

    total_clicks = sum(r.get("clicks", 0) for r in query_rows) or 0
    brand_clicks = sum(r.get("clicks", 0) for r in query_rows if is_brand(r["keys"][0]))

    striking = []
    ctr_gaps = []
    for r in query_rows:
        q, imp, pos, ctr = r["keys"][0], r.get("impressions", 0), r.get("position", 0), r.get("ctr", 0)
        if imp < min_impressions or is_brand(q):
            continue
        if 4 <= pos <= 20:
            # Clicks gained if the query moved to position 3.
            gain = imp * expected_ctr(3) - r.get("clicks", 0)
            striking.append({"query": q, "position": round(pos, 1), "impressions": imp, "clicks": r.get("clicks", 0),
                             "potential_extra_clicks": max(0, round(gain))})
        if pos <= 10:
            exp = expected_ctr(pos)
            if ctr < exp * 0.6:
                ctr_gaps.append({"query": q, "position": round(pos, 1), "impressions": imp,
                                 "ctr": round(ctr, 4), "expected_ctr": exp,
                                 "missed_clicks": round(imp * exp - r.get("clicks", 0))})
    striking.sort(key=lambda x: -x["potential_extra_clicks"])
    ctr_gaps.sort(key=lambda x: -x["missed_clicks"])

    # Which page ranks for which gap query (title/meta rewrite target).
    best_page = {}
    by_query = defaultdict(list)
    for r in query_page_rows:
        q, page = r["keys"][0], r["keys"][1]
        by_query[q].append({"page": page, "impressions": r.get("impressions", 0), "clicks": r.get("clicks", 0),
                            "position": round(r.get("position", 0), 1)})
    for q, pages in by_query.items():
        best_page[q] = max(pages, key=lambda p: p["impressions"])["page"]
    for item in striking + ctr_gaps:
        item["page"] = best_page.get(item["query"])

    cannibal = []
    for q, pages in by_query.items():
        total = sum(p["impressions"] for p in pages)
        if total < min_impressions or is_brand(q):
            continue
        strong = [p for p in pages if p["impressions"] >= 0.2 * total]
        if len(strong) >= 2:
            cannibal.append({"query": q, "impressions": total, "pages": sorted(strong, key=lambda p: -p["impressions"])})
    cannibal.sort(key=lambda x: -x["impressions"])

    prev = {r["keys"][0]: r for r in prev_page_rows}
    declining = []
    for r in page_rows:
        p = prev.get(r["keys"][0])
        if p and p.get("clicks", 0) >= 10 and r.get("clicks", 0) < 0.7 * p["clicks"]:
            declining.append({"page": r["keys"][0], "clicks": r.get("clicks", 0), "previous_clicks": p["clicks"],
                              "change_pct": round((r.get("clicks", 0) - p["clicks"]) / p["clicks"] * 100, 1),
                              "position": round(r.get("position", 0), 1), "previous_position": round(p.get("position", 0), 1)})
    declining.sort(key=lambda x: x["clicks"] - x["previous_clicks"])

    return {
        "brand_terms": terms,
        "non_brand_click_share": None if not total_clicks else round(1 - brand_clicks / total_clicks, 4),
        "striking_distance": striking[:25],
        "striking_distance_count": len(striking),
        "ctr_below_expected": ctr_gaps[:25],
        "cannibalisation": cannibal[:15],
        "declining_pages": declining[:15],
        "expected_ctr_curve": CTR_BY_POSITION,
    }


@server.tool()
def gsc_opportunities(date_from: str, date_to: str, min_impressions: int = 50) -> dict:
    """SEO opportunity analysis for the brand's property, as data for the seo-opportunities skill:
    striking-distance queries (position 4–20, with clicks gained at position 3), queries whose CTR is far below
    what their position should get (title/meta rewrite candidates, with the ranking page), cannibalisation
    (2+ pages splitting one query), pages losing clicks vs the previous period, and non-brand click share.
    Brand queries are excluded from the opportunity lists.

    Args:
        date_from: Start date, YYYY-MM-DD (use 28+ days for stable numbers).
        date_to: End date, YYYY-MM-DD (3 days before today: the last days are incomplete).
        min_impressions: Ignore queries with fewer impressions in the period.
    """
    _check_dates(date_from, date_to)
    brand = load_brand()
    s = site(brand)
    base = {"startDate": date_from, "endDate": date_to}
    prev_from, prev_to = previous_period(date_from, date_to)
    queries = _search(brand, s, {**base, "dimensions": ["query"], "rowLimit": 5000})
    query_pages = _search(brand, s, {**base, "dimensions": ["query", "page"], "rowLimit": 10000})
    pages = _search(brand, s, {**base, "dimensions": ["page"], "rowLimit": 1000})
    prev_pages = _search(brand, s, {"startDate": prev_from, "endDate": prev_to, "dimensions": ["page"], "rowLimit": 1000})
    result = analyse_opportunities(queries, query_pages, pages, prev_pages, brand_terms(brand), min_impressions)
    return {"site_url": s, "period": {"from": date_from, "to": date_to},
            "previous_period": {"from": prev_from, "to": prev_to}, "queries_analysed": len(queries), **result}


@server.tool()
def gsc_audit(date_from: str, date_to: str) -> dict:
    """Render the full HTML SEO audit (charts, issues, 30/60/90-day roadmap) for the brand's property into the
    brand folder's reports/. Note: this upstream report is written in Italian; for a report in the brand's
    language use the seo-opportunities skill.

    Args:
        date_from: Start date, YYYY-MM-DD.
        date_to: End date, YYYY-MM-DD.
    """
    _check_dates(date_from, date_to)
    brand = load_brand()
    s = site(brand)
    b = brand.data["brand"]
    branding = {"brand_name": b["name"]}
    if b.get("colors", {}).get("primary"):
        branding["colors"] = {"primary": b["colors"]["primary"], "primary_dark": b["colors"]["primary"]}
    if b.get("logo"):
        branding["logo"] = str((brand.dir / b["logo"]).expanduser())
    path = generate_audit(_api_get(brand), _api_post(brand), s, date_from, date_to, str(brand.reports_dir()), branding)
    return {"report_path": path, "site_url": s, "language": "it"}


if __name__ == "__main__":
    server.run()
