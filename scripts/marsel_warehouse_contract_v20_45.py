#!/usr/bin/env python3
"""MARSEL warehouse contract audit — READ ONLY.

Canonical version 20.48. The warehouse-list contract is verified only against
the documented RO App v2 endpoint. No branch/location endpoint is inferred or
used: the documented warehouse endpoint makes branch_id optional and type
explicitly defaults to product. Undocumented compatibility probes are retained
only as diagnostics and can never produce PASS.
"""
from __future__ import annotations
import hashlib, json, os, time
from urllib.parse import urlencode
from urllib.request import Request, urlopen

KEY = os.getenv("ROAPP_API_KEY", "")
API_BASE = os.getenv("ROAPP_API_BASE", "https://api.roapp.io/v2").rstrip("/")
API_ROOT = API_BASE.removesuffix("/v2")
TIMEOUT = float(os.getenv("ROAPP_WAREHOUSE_TIMEOUT", os.getenv("ROAPP_TIMEOUT", "15")))
MAX_RETRIES = max(int(os.getenv("ROAPP_MAX_RETRIES", "2")), 0)
MIN_INTERVAL = max(float(os.getenv("ROAPP_MIN_REQUEST_INTERVAL", "0.34")), 0.34)
WAREHOUSE_DOC = "https://roappua.readme.io/reference/get-warehouses"
STOCK_DOC = "https://roappua.readme.io/reference/get-stock"


def get(url: str):
    last_error = None
    for attempt in range(MAX_RETRIES + 1):
        if attempt:
            time.sleep(min(2 ** (attempt - 1), 4))
        time.sleep(MIN_INTERVAL)
        req = Request(url, headers={"Authorization": f"Bearer {KEY}", "Accept": "application/json", "User-Agent": "MARSEL-Warehouse-Contract-V20.48"}, method="GET")
        started = time.time()
        try:
            with urlopen(req, timeout=TIMEOUT) as r:
                body = r.read().decode("utf-8", errors="replace")
                if r.status in {408, 429, 500, 502, 503, 504} and attempt < MAX_RETRIES:
                    continue
                return r.status, body, round(time.time() - started, 3), None
        except Exception as exc:
            status = getattr(exc, "code", None)
            body = ""
            try:
                body = exc.read().decode("utf-8", errors="replace")
            except Exception:
                pass
            last_error = f"{type(exc).__name__}: {exc}"
            if status in {408, 429, 500, 502, 503, 504} and attempt < MAX_RETRIES:
                continue
            if status is None and attempt < MAX_RETRIES:
                continue
            return status, body, round(time.time() - started, 3), last_error
    return None, "", 0, last_error or "GET request failed"


def parse_json(body: str):
    try:
        return json.loads(body), True
    except (json.JSONDecodeError, TypeError):
        return None, False


def extract_rows(payload):
    if isinstance(payload, list):
        return [x for x in payload if isinstance(x, dict)]
    if not isinstance(payload, dict):
        return []
    preferred = ("data", "warehouses", "warehouse", "items", "results", "records", "collection")
    seen, found = set(), []
    def walk(value, depth=0):
        if depth > 5 or id(value) in seen:
            return
        if isinstance(value, (dict, list)):
            seen.add(id(value))
        if isinstance(value, list):
            rows = [x for x in value if isinstance(x, dict)]
            if rows and any(row.get("id") is not None or row.get("warehouse_id") is not None for row in rows):
                found.extend(rows)
                return
            for item in value:
                walk(item, depth + 1)
            return
        if not isinstance(value, dict):
            return
        for key in preferred:
            if key in value:
                walk(value[key], depth + 1)
        for key, child in value.items():
            if key not in preferred and isinstance(child, (dict, list)):
                walk(child, depth + 1)
    walk(payload)
    unique, signatures = [], set()
    for row in found:
        sig = json.dumps(row, sort_keys=True, ensure_ascii=False, default=str)
        if sig not in signatures:
            signatures.add(sig)
            unique.append(row)
    return unique


def warehouse_id(row):
    if not isinstance(row, dict):
        return None
    for key in ("id", "warehouse_id"):
        value = row.get(key)
        if isinstance(value, (int, str)) and str(value).strip():
            return str(value).strip()
    return None


def probe(path: str, query: dict | None, source: str, documented: bool):
    url = f"{path}" + (f"?{urlencode(query)}" if query else "")
    status, body, elapsed, error = get(url)
    payload, valid_json = parse_json(body) if status == 200 else (None, False)
    rows = extract_rows(payload) if valid_json else []
    row_keys = sorted({key for row in rows for key in row.keys()})
    ids = [wid for wid in (warehouse_id(row) for row in rows) if wid]
    return {"method": "GET", "endpoint_path": path, "path": url.replace(API_ROOT, ""), "url": url, "source": source, "documented_contract": documented, "query": query or {}, "http": status, "elapsed_s": elapsed, "json_valid": valid_json, "error": error, "response_top_level_type": type(payload).__name__ if valid_json else None, "response_keys": sorted(payload.keys()) if isinstance(payload, dict) else None, "rows_discovered": len(rows), "row_schema_keys": row_keys, "warehouse_ids_in_response": ids}, rows


def main():
    if not KEY:
        raise SystemExit("ROAPP_API_KEY is required")
    branch_id = os.getenv("ROAPP_BRANCH_ID", "").strip()
    queries = [{"type": "product"}]
    if branch_id:
        queries.insert(0, {"branch_id": branch_id, "type": "product"})

    probes = []
    rows = []
    for query in queries:
        list_probe, candidate_rows = probe(f"{API_BASE}/warehouse/", query, WAREHOUSE_DOC, True)
        probes.append(list_probe)
        if candidate_rows:
            rows.extend(candidate_rows)
        if list_probe["http"] == 200 and list_probe["json_valid"] and list_probe["rows_discovered"] > 0:
            break

    ids = []
    for row in rows:
        wid = warehouse_id(row)
        if wid and wid not in ids:
            ids.append(wid)

    stock_probes = []
    for wid in ids:
        url = f"{API_ROOT}/warehouse/goods/{wid}"
        status, body, elapsed, error = get(url)
        parsed, valid_json = parse_json(body) if status == 200 else (None, False)
        stock_probes.append({"method": "GET", "endpoint_path": "/warehouse/goods/{warehouse_id}", "path": "/warehouse/goods/{warehouse_id}", "warehouse_id": wid, "url": url, "source": STOCK_DOC, "documented_contract": True, "http": status, "elapsed_s": elapsed, "json_valid": valid_json, "error": error, "response_top_level_type": type(parsed).__name__ if valid_json else None, "response_keys": sorted(parsed.keys()) if isinstance(parsed, dict) else None})
    probes.extend(stock_probes)

    list_successes = [p for p in probes if p.get("documented_contract") and p.get("endpoint_path") == "/v2/warehouse/" and p.get("http") == 200 and p.get("json_valid") and p.get("rows_discovered", 0) > 0 and bool(p.get("warehouse_ids_in_response"))]
    confirmed_live_gets = [p for p in probes if p.get("documented_contract") and p.get("http") == 200 and p.get("json_valid") and (p.get("rows_discovered", 0) > 0 or p.get("endpoint_path") == "/warehouse/goods/{warehouse_id}")]
    result = "PASS" if list_successes else "NOT_VERIFIED"
    report = {"version": "20.48", "mode": "READ_ONLY", "result": result, "readonly": True, "write_requests_made": 0, "ro_app_data_mutated": False, "official_documentation": {"warehouse_list": WAREHOUSE_DOC, "stock": STOCK_DOC, "authentication": "Bearer token", "warehouse_list_contract": {"method": "GET", "path": "/v2/warehouse/", "branch_id": "optional string", "type": "optional string; default product; allowed product|asset", "pagination": "not documented on the warehouse-list page"}}, "warehouse_count": len(ids), "warehouse_ids_discovered": ids, "branch_id_used": branch_id or None, "probes": probes, "confirmed_live_gets": confirmed_live_gets, "warehouse_list_live_gets": list_successes, "diagnostic_only_undocumented_probes": [p for p in probes if not p.get("documented_contract")], "retry_policy": {"max_retries": MAX_RETRIES, "timeout_seconds": TIMEOUT, "retryable_http": [408, 429, 500, 502, 503, 504]}}
    raw = json.dumps(report, ensure_ascii=False, indent=2).encode()
    report["report_sha256"] = hashlib.sha256(raw).hexdigest()
    out = os.getenv("WAREHOUSE_CONTRACT_OUTPUT", "marsel-unified-warehouse-contract.json")
    with open(out, "w", encoding="utf-8") as fh:
        json.dump(report, fh, ensure_ascii=False, indent=2)
    print(f"WAREHOUSE_CONTRACT_RESULT={result}")
    print(f"WAREHOUSE_COUNT={len(ids)}")
    print(f"BRANCH_ID_USED={branch_id or 'NONE'}")
    print("WAREHOUSE_EXPLICIT_GET_CONTRACTS=1")
    print(f"WAREHOUSE_LIST_CONFIRMED_LIVE_GETS={len(list_successes)}")
    print(f"WAREHOUSE_CONFIRMED_LIVE_GETS={len(confirmed_live_gets)}")
    print("WRITE_REQUESTS_MADE=0")
    print("RO_APP_DATA_MUTATED=false")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
