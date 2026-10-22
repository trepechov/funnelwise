#!/usr/bin/env python3
"""Read-only Google Analytics 4 server (GA4 Data API v1beta).

Replaces the earlier `npx mcp-google-analytics` wrapper: no Node needed, and
the property is fixed by brand.yaml connectors.ga4.property_id. Tools take no
property argument, so a report can never reach another property the
credential happens to see. There are deliberately no Measurement Protocol
"send event" tools: they would write fake events into the brand's analytics.

Auth: the Google service-account key in the credentials folder, added as a
Viewer on the GA4 property.
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import List, Optional

sys.path.insert(0, str(Path(__file__).resolve().parent))
from lib import bootstrap  # noqa: E402

bootstrap()
from lib.google_auth import load_service_account, service_account_token  # noqa: E402
from lib.http import get_json, post_json  # noqa: E402
from lib.mcp_stdio import Server, ToolError  # noqa: E402
from lib.workspace import Brand, load_brand  # noqa: E402

SCOPE = "https://www.googleapis.com/auth/analytics.readonly"
BASE = "https://analyticsdata.googleapis.com/v1beta"

server = Server("funnelwise-ga4", instructions=(
    "Google Analytics 4 reports for the brand's property only (set in brand.yaml). Dates accept YYYY-MM-DD, "
    "'today', 'yesterday' or 'NdaysAgo'. Use ga_get_metadata to find valid dimension and metric names."
))


def _property(brand: Brand) -> str:
    pid = brand.scope_id("ga4")
    pid = pid.replace("properties/", "")
    if not pid.isdigit():
        raise ToolError(f"brand.yaml connectors.ga4.property_id must be the numeric GA4 property ID (got {pid}).")
    return pid


def _headers(brand: Brand) -> dict:
    info = load_service_account(brand.credential("google-service-account.json"))
    return {"Authorization": f"Bearer {service_account_token(info, SCOPE)}"}


def _flatten(data: dict) -> dict:
    dims = [h["name"] for h in data.get("dimensionHeaders", [])]
    mets = [(h["name"], h.get("type", "")) for h in data.get("metricHeaders", [])]
    rows = []
    for r in data.get("rows", []):
        row = {d: v.get("value") for d, v in zip(dims, r.get("dimensionValues", []))}
        for (name, typ), v in zip(mets, r.get("metricValues", [])):
            raw = v.get("value")
            try:
                row[name] = int(raw) if typ == "TYPE_INTEGER" else float(raw)
            except (TypeError, ValueError):
                row[name] = raw
        rows.append(row)
    out = {"rows": rows, "row_count": data.get("rowCount", len(rows))}
    if data.get("totals"):
        out["totals"] = _flatten({"dimensionHeaders": data.get("dimensionHeaders", []),
                                  "metricHeaders": data.get("metricHeaders", []), "rows": data["totals"]})["rows"]
    if data.get("metadata", {}).get("dataLossFromOtherRow"):
        out["note"] = "Some rows were grouped into (other) because of GA4 cardinality limits."
    return out


@server.tool()
def ga_run_report(date_from: str, date_to: str, metrics: List[str], dimensions: Optional[List[str]] = None,
                  limit: int = 100, order_by_metric: str = "", descending: bool = True,
                  dimension_filter: Optional[dict] = None) -> dict:
    """Run a GA4 report for the brand's property: metrics over a period, optionally broken down by dimensions.

    Args:
        date_from: Start date: YYYY-MM-DD, 'yesterday', '28daysAgo', …
        date_to: End date: YYYY-MM-DD, 'today', 'yesterday', …
        metrics: GA4 metric names, e.g. ["activeUsers", "sessions", "engagementRate", "keyEvents"].
        dimensions: Optional GA4 dimension names, e.g. ["sessionDefaultChannelGroup"] or ["country"].
        limit: Maximum rows (1–10000).
        order_by_metric: Optional metric to sort by.
        descending: Sort direction for order_by_metric.
        dimension_filter: Optional raw GA4 FilterExpression, e.g.
            {"filter": {"fieldName": "sessionDefaultChannelGroup", "stringFilter": {"value": "Organic Search"}}}
    """
    if not metrics:
        raise ToolError("At least one metric is needed.")
    brand = load_brand()
    pid = _property(brand)
    body = {
        "dateRanges": [{"startDate": date_from, "endDate": date_to}],
        "metrics": [{"name": m} for m in metrics],
        "dimensions": [{"name": d} for d in (dimensions or [])],
        "limit": max(1, min(limit, 10000)),
        "metricAggregations": ["TOTAL"],
    }
    if order_by_metric:
        body["orderBys"] = [{"metric": {"metricName": order_by_metric}, "desc": descending}]
    if dimension_filter:
        body["dimensionFilter"] = dimension_filter
    data = post_json(f"{BASE}/properties/{pid}:runReport", body, headers=_headers(brand), service="Google Analytics")
    return {"property_id": pid, "period": {"from": date_from, "to": date_to}, **_flatten(data)}


@server.tool()
def ga_run_realtime_report(metrics: List[str], dimensions: Optional[List[str]] = None, limit: int = 20) -> dict:
    """Realtime GA4 report (last 30 minutes) for the brand's property.

    Args:
        metrics: e.g. ["activeUsers"].
        dimensions: Optional, e.g. ["country"] or ["unifiedScreenName"].
        limit: Maximum rows.
    """
    brand = load_brand()
    pid = _property(brand)
    body = {"metrics": [{"name": m} for m in metrics], "dimensions": [{"name": d} for d in (dimensions or [])],
            "limit": max(1, min(limit, 10000))}
    data = post_json(f"{BASE}/properties/{pid}:runRealtimeReport", body, headers=_headers(brand), service="Google Analytics")
    return {"property_id": pid, **_flatten(data)}


@server.tool()
def ga_get_metadata(search: str = "") -> dict:
    """List the dimensions and metrics available on the brand's GA4 property (including custom ones).

    Args:
        search: Optional case-insensitive filter on the API name or display name, e.g. "session".
    """
    brand = load_brand()
    pid = _property(brand)
    data = get_json(f"{BASE}/properties/{pid}/metadata", headers=_headers(brand), service="Google Analytics")
    s = search.lower()

    def keep(item: dict) -> bool:
        return not s or s in item.get("apiName", "").lower() or s in item.get("uiName", "").lower()

    return {
        "dimensions": [{"name": d["apiName"], "label": d.get("uiName")} for d in data.get("dimensions", []) if keep(d)],
        "metrics": [{"name": m["apiName"], "label": m.get("uiName"), "type": m.get("type")}
                    for m in data.get("metrics", []) if keep(m)],
    }


if __name__ == "__main__":
    server.run()
