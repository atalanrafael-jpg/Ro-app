#!/usr/bin/env python3
"""MARSEL V22.3 — comprehensive read-only data-quality audit.

Only GET requests are used. Product-code duplicates are inventory signals and
are classified by the dedicated collision audit; they are not blocking review
findings in this layer. Missing/duplicate IDs, count mismatches, access
failures and incomplete pagination remain hard failures. SKU/number duplicates
remain review findings unless a downstream contract/classifier proves them
benign.
"""
from __future__ import annotations

import hashlib
import json
import os
import sys
import time
from collections import Counter
from pathlib import Path

import httpx

BASE = os.environ.get("ROAPP_API_BASE", "https://api.roapp.io/v2").rstrip("/")
KEY = os.environ.get("ROAPP_API_KEY", "")
TIMEOUT = float(os.environ.get("ROAPP_TIMEOUT", "30"))
PAGE_SIZE = min(int(os.environ.get("MARSEL_PAGE_SIZE", "50")), 50)
MIN_INTERVAL = max(float(os.environ.get("ROAPP_MIN_REQUEST_INTERVAL", "0.34")), 0.34)
OUT = Path(os.environ.get("MARSEL_DATA_QUALITY_OUTPUT", "marsel-data-quality-v22-readonly.json"))
MAX_PAGES = int(os.environ.get("MARSEL_MAX_PAGES", "10000"))

if not KEY:
    print("ROAPP_API_KEY is required", file=sys.stderr)
    raise SystemExit(1)

HEADERS = {"Authorization": f"Bearer {KEY}", "Accept": "application/json", "User-Agent": "MARSEL-Data-Quality-V23-READONLY"}
COLLECTIONS = {"products": "/catalog/products", "services": "/catalog/services", "orders": "/orders"}


def extract_rows(payload: object) -> list[dict]:
    if isinstance(payload, list):
        return [x for x in payload if isinstance(x, dict)]
    if isinstance(payload, dict) and isinstance(payload.get("data"), list):
        return [x for x in payload["data"] if isinstance(x, dict)]
    return []


def page_info(payload: object) -> dict:
    if not isinstance(payload, dict) or not isinstance(payload.get("paging"), dict):
        return {}
    p = payload["paging"]
    return {k: p.get(k) for k in ("page", "limit", "total_pages", "count") if k in p}


def duplicate_groups(rows: list[dict], field: str) -> dict[str, int]:
    counts = Counter(r.get(field) for r in rows if r.get(field) not in (None, ""))
    return {str(k): v for k, v in counts.items() if v > 1}


def safe_error(response: httpx.Response) -> dict:
    return {"http": response.status_code, "body": response.text[:1000]}


def audit_collection(client: httpx.Client, name: str, path: str) -> dict:
    rows, pages = [], []
    page, expected_total_pages, expected_count, last_request = 1, None, None, 0.0
    while True:
        wait = MIN_INTERVAL - (time.monotonic() - last_request)
        if wait > 0:
            time.sleep(wait)
        started = time.monotonic()
        response = client.get(BASE + path, params={"page": page, "pageSize": PAGE_SIZE}, headers=HEADERS)
        last_request = time.monotonic()
        if response.status_code != 200:
            return {"path": path, "rows_read": len(rows), "expected_count": expected_count, "count_matches_rows": False,
                    "expected_total_pages": expected_total_pages, "pages_read": len(pages), "pagination_complete": False,
                    "missing_id": 0, "duplicate_id_groups": {}, "duplicate_id_group_count": 0, "pages": pages,
                    "access_error": safe_error(response)}
        payload = response.json()
        batch, pi = extract_rows(payload), page_info(payload)
        if expected_total_pages is None:
            expected_total_pages, expected_count = pi.get("total_pages"), pi.get("count")
        pages.append({"page": page, "http": 200, "elapsed_s": round(time.monotonic() - started, 3), "batch_size": len(batch), "paging": pi})
        rows.extend(batch)
        if expected_total_pages is not None and page >= int(expected_total_pages):
            break
        if len(batch) < PAGE_SIZE:
            break
        page += 1
        if page > MAX_PAGES:
            raise RuntimeError(f"pagination safety limit exceeded for {name}")

    ids = [r.get("id") for r in rows]
    duplicate_id = duplicate_groups(rows, "id")
    result = {"path": path, "rows_read": len(rows), "expected_count": expected_count,
              "count_matches_rows": expected_count is None or int(expected_count) == len(rows),
              "expected_total_pages": expected_total_pages, "pages_read": len(pages),
              "pagination_complete": (expected_total_pages is not None and len(pages) == int(expected_total_pages)) or
                                     (expected_total_pages is None and bool(pages) and pages[-1]["batch_size"] < PAGE_SIZE),
              "missing_id": sum(v in (None, "") for v in ids), "duplicate_id_groups": duplicate_id,
              "duplicate_id_group_count": len(duplicate_id), "pages": pages}
    if name in ("products", "services"):
        for field in ("code", "sku"):
            dups = duplicate_groups(rows, field)
            result[f"duplicate_{field}_groups"] = dups
            result[f"duplicate_{field}_group_count"] = len(dups)
        result["missing_title"] = sum(r.get("title") in (None, "") for r in rows)
    if name == "orders":
        dups = duplicate_groups(rows, "number")
        result["duplicate_number_groups"] = dups
        result["duplicate_number_group_count"] = len(dups)
        result["missing_number"] = sum(r.get("number") in (None, "") for r in rows)
    return result


def probe_company(client: httpx.Client) -> dict:
    try:
        response = client.get(BASE + "/company", headers=HEADERS)
        result = {"http": response.status_code}
        if response.status_code != 200:
            result["error"] = safe_error(response)
        return result
    except (httpx.TimeoutException, httpx.NetworkError) as exc:
        return {"http": None, "error": {"type": type(exc).__name__, "message": str(exc)[:500]}}


def main() -> int:
    started = time.monotonic()
    with httpx.Client(timeout=TIMEOUT, follow_redirects=True) as client:
        company_probe = probe_company(client)
        results = {name: audit_collection(client, name, path) for name, path in COLLECTIONS.items()}

    hard_issues, review_issues, access_failures = [], [], []
    for name, r in results.items():
        if r.get("access_error"):
            access_failures.append({"collection": name, **r["access_error"]})
            continue
        for key in ("missing_id", "duplicate_id_group_count"):
            if r.get(key):
                hard_issues.append(f"{name}.{key}={r[key]}")
        if not r.get("count_matches_rows", True):
            hard_issues.append(f"{name}.count_mismatch={r['expected_count']}!={r['rows_read']}")
        # Product-code duplication is deliberately NOT a review issue here.
        # The dedicated collision classifier is the authoritative gate for it.
        for key in ("duplicate_sku_group_count", "duplicate_number_group_count"):
            if r.get(key):
                review_issues.append(f"{name}.{key}={r[key]}")
        if not r.get("pagination_complete"):
            hard_issues.append(f"{name}.pagination_incomplete=true")

    report = {"version": "22.3", "mode": "READ_ONLY", "generated_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
              "api_base": BASE, "company_probe": company_probe,
              "method_policy": {"allowed": ["GET"], "blocked": ["POST", "PUT", "PATCH", "DELETE"]},
              "write_requests_made": 0, "ro_app_data_mutated": False, "collections": results,
              "access_failures": access_failures, "hard_issues": hard_issues, "review_issues": review_issues,
              "policy": {"code_uniqueness_established": False, "duplicate_codes_are_hard_failures": False,
                         "duplicate_code_authoritative_classifier": "product-collision-audit-v22.3"},
              "elapsed_s": round(time.monotonic() - started, 3)}
    report["summary"] = {"collections_audited": len(results), "products_rows": results["products"]["rows_read"],
                          "services_rows": results["services"]["rows_read"], "orders_rows": results["orders"]["rows_read"],
                          "access_failure_count": len(access_failures), "hard_issue_count": len(hard_issues),
                          "review_issue_count": len(review_issues), "write_requests_made": 0, "ro_app_data_mutated": False}
    report["report_sha256"] = hashlib.sha256(json.dumps(report, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    OUT.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print("=== MARSEL V22.3 / COMPREHENSIVE DATA QUALITY / READ ONLY ===")
    for k, v in report["summary"].items():
        print(f"{k.upper()}={v}")
    print(f"ACCESS_FAILURES={access_failures}")
    print(f"HARD_ISSUES={hard_issues}")
    print(f"REVIEW_ISSUES={review_issues}")
    print(f"REPORT={OUT}")
    print(f"REPORT_SHA256={report['report_sha256']}")
    ok = not access_failures and not hard_issues
    print("RESULT=PASS" if ok else "RESULT=REVIEW_REQUIRED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
