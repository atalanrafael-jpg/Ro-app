#!/usr/bin/env python3
"""MARSEL V20.21 — official RO App API inventory, READ ONLY.

Extracts only endpoint paths explicitly present in official documentation.
Supports ReadMe rendered HTML/text, OpenAPI/JSON, explicit api.roapp.io URLs,
/v2 and /1.1 paths, and relative paths when directly paired with an HTTP
method. No endpoint is inferred from an operation title.
Only GET probes are permitted.
"""
import hashlib
import html
import json
import os
import re
import sys
import time
from urllib.parse import urljoin, urlparse
from urllib.request import Request, urlopen

DOCS_INDEX = os.environ.get("ROAPP_DOCS_INDEX", "https://roapp.readme.io/llms.txt")
BASE = os.environ.get("ROAPP_API_BASE", "https://api.roapp.io/v2").rstrip("/")
KEY = os.environ.get("ROAPP_API_KEY", "")
OUT = os.environ.get("MARSEL_API_INVENTORY_OUTPUT", "marsel-api-inventory-v20-21.json")
TIMEOUT = int(os.environ.get("ROAPP_TIMEOUT", "30"))
MAX_DOCS = int(os.environ.get("MARSEL_MAX_DOCS", "300"))
MAX_RETRIES = int(os.environ.get("ROAPP_MAX_RETRIES", "3"))
RETRY_BASE = float(os.environ.get("ROAPP_RETRY_BASE_SECONDS", "0.75"))
MIN_INTERVAL = float(os.environ.get("ROAPP_MIN_REQUEST_INTERVAL", "0.25"))
METHODS = {"GET", "POST", "PUT", "PATCH", "DELETE"}
METHOD_RE = re.compile(r"\b(GET|POST|PUT|PATCH|DELETE)\b", re.I)
FULL_API_RE = re.compile(r"https?://api\.roapp\.io(?:/[A-Za-z0-9_./{}:\-?=&\[\],%]+)?", re.I)
VERSIONED_RE = re.compile(r"/(?:v2|1\.1)(?:/[A-Za-z0-9_./{}:\-?=&\[\],%]+)?", re.I)
RELATIVE_RE = re.compile(r"/(?!reference(?:/|$)|assets(?:/|$)|static(?:/|$)|images?(?:/|$)|css(?:/|$)|js(?:/|$)|favicon(?:/|$))[A-Za-z0-9_][A-Za-z0-9_./{}:\-?=&\[\],%]*")
HREF_RE = re.compile(r"(?:href|src)\s*=\s*[\"']([^\"']+)[\"']", re.I)
METHOD_ATTR_RE = re.compile(r"(?:data-method|data-http-method|http-method)\s*=\s*[\"'](GET|POST|PUT|PATCH|DELETE)[\"']", re.I)
PATH_ATTR_RE = re.compile(r"(?:data-path|data-api-path|data-endpoint|data-url)\s*=\s*[\"']([^\"']+)[\"']", re.I)
_last = 0.0


def fetch(url, headers=None):
    global _last
    h = headers or {"User-Agent": "MARSEL-Audit-V20.21", "Accept": "text/plain,text/markdown,text/html,application/json"}
    last = None
    for attempt in range(MAX_RETRIES + 1):
        wait = MIN_INTERVAL - (time.monotonic() - _last)
        if wait > 0:
            time.sleep(wait)
        req = Request(url, headers=h, method="GET")
        started = time.time()
        _last = time.monotonic()
        try:
            with urlopen(req, timeout=TIMEOUT) as r:
                body = r.read().decode("utf-8", "replace")
                status = r.status
                if status not in {408, 425, 429, 500, 502, 503, 504} or attempt >= MAX_RETRIES:
                    return status, body, round(time.time() - started, 3), None
                retry = r.headers.get("Retry-After")
                try:
                    delay = float(retry) if retry else RETRY_BASE * (2 ** attempt)
                except ValueError:
                    delay = RETRY_BASE * (2 ** attempt)
        except Exception as exc:
            last = f"{type(exc).__name__}: {exc}"
            if attempt >= MAX_RETRIES:
                return None, "", round(time.time() - started, 3), last
            delay = RETRY_BASE * (2 ** attempt)
        time.sleep(min(max(delay, 0), 30))
    return None, "", 0, last or "request failed"


def clean(value):
    return html.unescape(str(value)).strip().replace("\\/", "/").rstrip(".,;:")


def normalize(raw):
    raw = clean(raw)
    if raw.startswith(("http://", "https://")):
        parsed = urlparse(raw)
        if parsed.netloc.lower() != "api.roapp.io":
            return None
        raw = parsed.path or "/"
    if not raw.startswith("/"):
        return None
    raw = re.sub(r"/{2,}", "/", raw)
    if raw in {"/", "/v2", "/v2/", "/1.1", "/1.1/"}:
        return None
    return raw


def structured_walk(value, found):
    if isinstance(value, dict):
        lowered = {str(k).casefold().replace("-", "_"): v for k, v in value.items()}
        method = next((str(lowered[k]).upper() for k in ("method", "httpmethod", "http_method", "verb") if k in lowered and str(lowered[k]).upper() in METHODS), None)
        raw_path = next((lowered[k] for k in ("path", "pathname", "route", "endpoint", "url") if k in lowered and isinstance(lowered[k], str)), None)
        if method and raw_path:
            path = normalize(raw_path)
            if path:
                found.append((method, path))
        paths_obj = lowered.get("paths")
        if isinstance(paths_obj, dict):
            for raw_path, operations in paths_obj.items():
                path = normalize(raw_path)
                if path and isinstance(operations, dict):
                    for key in operations:
                        if str(key).upper() in METHODS:
                            found.append((str(key).upper(), path))
        for child in value.values():
            structured_walk(child, found)
    elif isinstance(value, list):
        for child in value:
            structured_walk(child, found)


def text_without_tags(text):
    text = re.sub(r"<(script|style)\b[^>]*>.*?</\1>", " ", text, flags=re.I | re.S)
    text = re.sub(r"<[^>]+>", " ", text)
    return re.sub(r"\s+", " ", html.unescape(text).replace("\\/", "/")).strip()


def extract(text):
    normalized = html.unescape(text).replace("\\/", "/")
    found = []

    for tag in re.findall(r"<[^>]+>", normalized):
        methods = METHOD_ATTR_RE.findall(tag)
        paths = PATH_ATTR_RE.findall(tag)
        for method in methods:
            for raw_path in paths:
                path = normalize(raw_path)
                if path:
                    found.append((method.upper(), path))

    blocks = re.findall(r"<script[^>]*>(.*?)</script>", normalized, re.I | re.S)
    if normalized.lstrip().startswith(("{", "[")):
        blocks.append(normalized)
    for block in blocks:
        try:
            parsed = json.loads(block.strip())
        except Exception:
            continue
        structured_walk(parsed, found)

    for match in FULL_API_RE.finditer(normalized):
        path = normalize(match.group(0))
        window = normalized[max(0, match.start() - 250): match.end() + 120]
        methods = list(METHOD_RE.finditer(window))
        if path:
            found.append(((methods[-1].group(1).upper() if methods else "GET"), path))

    for match in VERSIONED_RE.finditer(normalized):
        path = normalize(match.group(0))
        window = normalized[max(0, match.start() - 180): match.end() + 100]
        methods = list(METHOD_RE.finditer(window))
        if path and methods:
            found.append((methods[-1].group(1).upper(), path))

    for match in HREF_RE.finditer(normalized):
        path = normalize(match.group(1))
        window = normalized[max(0, match.start() - 300): match.end() + 150]
        methods = list(METHOD_RE.finditer(window))
        if path and methods:
            found.append((methods[-1].group(1).upper(), path))

    plain = text_without_tags(normalized)
    for match in re.finditer(r"\b(GET|POST|PUT|PATCH|DELETE)\b\s+(/[^\s<>{}\"'`]+)", plain, re.I):
        path = normalize(match.group(2))
        if path:
            found.append((match.group(1).upper(), path))

    for match in re.finditer(r"\b(GET|POST|PUT|PATCH|DELETE)\b\s*[:\-]?\s*(https?://api\.roapp\.io[^\s<>{}\"'`]+|/(?!reference(?:/|$))[^\s<>{}\"'`]+)", plain, re.I):
        path = normalize(match.group(2))
        if path:
            found.append((match.group(1).upper(), path))

    for block in re.findall(r"<(?:pre|code)\b[^>]*>(.*?)</(?:pre|code)>", normalized, re.I | re.S):
        code = text_without_tags(block)
        for match in re.finditer(r"\b(GET|POST|PUT|PATCH|DELETE)\b\s+(https?://api\.roapp\.io[^\s]+|/[^\s]+)", code, re.I):
            path = normalize(match.group(2))
            if path:
                found.append((match.group(1).upper(), path))

    return list(dict.fromkeys(found))


def has_placeholder(path):
    return bool(re.search(r"\{[^}]+\}|<[^>]+>|:[A-Za-z_][A-Za-z0-9_]*", path))


def probe_url(path):
    if path.startswith("/v2/") or path.startswith("/1.1/"):
        return "https://api.roapp.io" + path
    return BASE + path


def sha256_json(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def main():
    if not KEY:
        print("ROAPP_API_KEY is required", file=sys.stderr)
        return 2
    status, index_text, _, error = fetch(DOCS_INDEX)
    print(f"DOCS_INDEX_HTTP={status}")
    if status != 200:
        print(error or "documentation index unavailable", file=sys.stderr)
        return 1

    links, seen = [], set()
    for match in re.finditer(r"\[([^\]]+)\]\(([^)]+/reference/[^)]+)\)", index_text):
        title, href = match.groups()
        url = urljoin(DOCS_INDEX, clean(href))
        if url not in seen:
            seen.add(url)
            links.append({"title": html.unescape(title).strip(), "url": url})
    links = links[:MAX_DOCS]

    operations = []
    for link in links:
        sources, bodies = [], []
        doc_status, doc_error = None, None
        variants = list(dict.fromkeys([link["url"], link["url"][:-3] if link["url"].endswith(".md") else link["url"]]))
        for variant in variants:
            st, body, elapsed, err = fetch(variant)
            sources.append({"url": variant, "http": st, "elapsed_s": elapsed, "error": err})
            if st == 200:
                bodies.append(body)
                doc_status = 200
            elif doc_status is None:
                doc_status, doc_error = st, err
        pairs = extract("\n".join(bodies)) if bodies else []
        methods = sorted({method for method, _ in pairs})
        paths = sorted({path for _, path in pairs})
        operations.append({
            "title": link["title"],
            "documentation_url": link["url"],
            "documentation_variants": sources,
            "documentation_http": doc_status,
            "documentation_error": doc_error,
            "methods": methods,
            "method_source": "document_body" if methods else "unresolved",
            "paths": paths,
            "get_probe": None,
        })

    probe_cache = {}
    headers = {"Authorization": f"Bearer {KEY}", "Accept": "application/json", "User-Agent": "MARSEL-Audit-V20.21"}
    for operation in operations:
        if "GET" not in operation["methods"]:
            continue
        concrete = [path for path in operation["paths"] if not has_placeholder(path)]
        if not concrete:
            operation["get_probe"] = {"status": "NOT_PROBED", "reason": "no concrete GET path extracted"}
            continue
        results = []
        for path in concrete:
            if path not in probe_cache:
                url = probe_url(path)
                st, body, elapsed, err = fetch(url, headers=headers)
                item = {"path": path, "url": url, "http": st, "elapsed_s": elapsed, "json": None, "error": err}
                if st == 200:
                    try:
                        parsed = json.loads(body)
                        item["json"] = {"type": type(parsed).__name__, "keys": sorted(parsed.keys())[:50] if isinstance(parsed, dict) else None}
                    except Exception:
                        item["error"] = "HTTP 200 but response is not JSON"
                probe_cache[path] = item
            results.append(probe_cache[path])
        operation["get_probe"] = {"status": "PROBED", "results": results}

    documented_get = sum("GET" in op["methods"] for op in operations)
    documented_non_get = sum(any(method != "GET" for method in op["methods"]) for op in operations)
    resolved = sum(bool(op["paths"]) for op in operations)
    probed = sum(1 for op in operations if "GET" in op["methods"] and op["get_probe"] and op["get_probe"]["status"] == "PROBED")
    not_probed = documented_get - probed

    report = {
        "version": "20.21",
        "readonly": True,
        "write_requests_made": 0,
        "ro_app_data_mutated": False,
        "request_policy": {"allowed_method": "GET", "min_interval_seconds": MIN_INTERVAL, "max_retries": MAX_RETRIES},
        "method_policy": {"allowed": ["GET"], "forbidden": ["POST", "PUT", "PATCH", "DELETE"]},
        "documentation": {"index": DOCS_INDEX, "index_http": status, "reference_links": len(links)},
        "operations": operations,
        "summary": {
            "reference_links": len(links),
            "documented_operations": len(operations),
            "documented_get_operations": documented_get,
            "documented_non_get_operations": documented_non_get,
            "operations_with_extracted_paths": resolved,
            "operations_without_extracted_paths": len(operations) - resolved,
            "get_operations_probed": probed,
            "get_operations_not_probed": not_probed,
            "get_operations_with_unresolved_probe_state": 0,
            "write_requests_made": 0,
            "ro_app_data_mutated": False,
        },
    }
    report["summary"]["inventory_sha256"] = sha256_json(report["operations"])
    with open(OUT, "w", encoding="utf-8") as handle:
        json.dump(report, handle, ensure_ascii=False, indent=2, sort_keys=True)

    summary = report["summary"]
    for key in ("reference_links", "documented_operations", "documented_get_operations", "operations_with_extracted_paths", "operations_without_extracted_paths", "get_operations_probed", "get_operations_not_probed", "inventory_sha256"):
        print(f"{key.upper()}={summary[key]}")
    print("WRITE_REQUESTS_MADE=0")
    print("RESULT=READ_ONLY; NO RO APP DATA CREATED, UPDATED OR DELETED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
