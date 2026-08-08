#!/usr/bin/env python3
"""MARSEL V20.20 — official RO App API inventory, READ ONLY.

Endpoint extraction supports explicit METHOD+URL pairs, HTML href/src API
links, relative /v2 and /1.1 paths, structured JSON/OpenAPI data, ReadMe
method/path attributes, and nearby method/path documentation.
Only GET probes are permitted; no write request is ever made.
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
OUT = os.environ.get("MARSEL_API_INVENTORY_OUTPUT", "marsel-api-inventory-v20-20.json")
TIMEOUT = int(os.environ.get("ROAPP_TIMEOUT", "30"))
MAX_DOCS = int(os.environ.get("MARSEL_MAX_DOCS", "300"))
MAX_RETRIES = int(os.environ.get("ROAPP_MAX_RETRIES", "3"))
RETRY_BASE = float(os.environ.get("ROAPP_RETRY_BASE_SECONDS", "0.75"))
MIN_INTERVAL = float(os.environ.get("ROAPP_MIN_REQUEST_INTERVAL", "0.25"))

METHOD_RE = re.compile(r"\b(GET|POST|PUT|PATCH|DELETE)\b", re.I)
METHOD_PATH_RE = re.compile(r"\b(GET|POST|PUT|PATCH|DELETE)\b\s*(?:[:\-]\s*)?(https?://api\.roapp\.io(?:/[A-Za-z0-9_./{}:\-?=&\[\]]*)?|/(?:v2|1\.1)(?:/[A-Za-z0-9_./{}:\-?=&\[\]]*)?)", re.I)
FULL_API_URL_RE = re.compile(r"https?://api\.roapp\.io(?:/[A-Za-z0-9_./{}:\-?=&\[\]]*)?", re.I)
PATH_RE = re.compile(r"/(?:v2|1\.1)(?:/[A-Za-z0-9_./{}:\-?=&\[\]]*)?", re.I)
HREF_RE = re.compile(r"(?:href|src)\s*=\s*[\"']([^\"']+)[\"']", re.I)
METHOD_ATTR_RE = re.compile(r"(?:data-method|data-http-method|http-method)\s*=\s*[\"'](GET|POST|PUT|PATCH|DELETE)[\"']", re.I)
PATH_ATTR_RE = re.compile(r"(?:data-path|data-api-path|data-endpoint|data-url)\s*=\s*[\"']([^\"']+)[\"']", re.I)
TITLE_METHODS = {"get":"GET","create":"POST","add":"POST","update":"PUT","delete":"DELETE","merge":"POST","change":"PATCH"}
BASE_ONLY = {"/v2","/1.1","/v2/","/1.1/"}
STRUCTURED_METHOD_KEYS = {"method", "httpmethod", "http_method", "verb"}
STRUCTURED_PATH_KEYS = {"path", "pathname", "route", "endpoint", "url"}
_last_request_at = 0.0


def fetch(url, headers=None):
    global _last_request_at
    req_headers = headers or {"User-Agent":"MARSEL-Audit-V20.20","Accept":"text/plain, text/markdown, text/html, application/json"}
    last_error = None
    for attempt in range(MAX_RETRIES + 1):
        wait = MIN_INTERVAL - (time.monotonic() - _last_request_at)
        if wait > 0: time.sleep(wait)
        req = Request(url, headers=req_headers, method="GET")
        started = time.time()
        try:
            _last_request_at = time.monotonic()
            with urlopen(req, timeout=TIMEOUT) as response:
                body = response.read().decode("utf-8", errors="replace")
                status = response.status
                if status not in {408,425,429,500,502,503,504} or attempt >= MAX_RETRIES:
                    return status, body, round(time.time()-started,3), None
                retry_after = response.headers.get("Retry-After")
                try: delay = float(retry_after) if retry_after else RETRY_BASE*(2**attempt)
                except ValueError: delay = RETRY_BASE*(2**attempt)
                time.sleep(min(max(delay,0.0),30.0))
        except Exception as exc:
            last_error = f"{type(exc).__name__}: {exc}"
            if attempt >= MAX_RETRIES: return None,"",round(time.time()-started,3),last_error
            time.sleep(min(RETRY_BASE*(2**attempt),30.0))
    return None,"",0,last_error or "request failed"


def clean_url(url): return url.rstrip(".,;:")


def title_method(title):
    first = title.strip().split(None,1)[0].casefold() if title.strip() else ""
    return TITLE_METHODS.get(first)


def normalize_path(raw):
    raw = clean_url(html.unescape(str(raw)).strip().replace("\\/","/"))
    if raw.startswith(("http://","https://")):
        parsed = urlparse(raw)
        if parsed.netloc.lower() != "api.roapp.io": return None
        raw = parsed.path
    if raw.startswith(("/v2/","/1.1/")) and raw not in BASE_ONLY:
        raw = raw.replace("/v2/v2/","/v2/").replace("/1.1/1.1/","/1.1/")
        return raw
    return None


def _structured_walk(value, found):
    if isinstance(value, dict):
        lowered = {str(k).casefold().replace("-", "_"): v for k, v in value.items()}
        method = next((str(lowered[k]).upper() for k in STRUCTURED_METHOD_KEYS if k in lowered and str(lowered[k]).upper() in {"GET","POST","PUT","PATCH","DELETE"}), None)
        raw_path = next((lowered[k] for k in STRUCTURED_PATH_KEYS if k in lowered and isinstance(lowered[k], str)), None)
        if method and raw_path:
            path = normalize_path(raw_path)
            if path:
                found.append((method, path))
        # OpenAPI-style {"paths": {"/v2/...": {"get": {...}}}}
        paths_obj = lowered.get("paths")
        if isinstance(paths_obj, dict):
            for raw_path, operations in paths_obj.items():
                path = normalize_path(raw_path)
                if not path or not isinstance(operations, dict):
                    continue
                for key in operations:
                    method_name = str(key).upper()
                    if method_name in {"GET","POST","PUT","PATCH","DELETE"}:
                        found.append((method_name, path))
        for child in value.values():
            _structured_walk(child, found)
    elif isinstance(value, list):
        for child in value:
            _structured_walk(child, found)


def extract_structured_method_paths(text):
    """Extract only explicit method/path pairs present in structured data.

    No endpoint is constructed or inferred here. Paths are accepted only when
    the source itself contains a concrete /v2/... or /1.1/... value.
    """
    normalized = html.unescape(text).replace("\\/", "/")
    found = []

    # HTML attributes commonly used by rendered API documentation.
    for tag in re.findall(r"<[^>]+>", normalized):
        methods = METHOD_ATTR_RE.findall(tag)
        paths = PATH_ATTR_RE.findall(tag)
        for method in methods:
            for raw_path in paths:
                path = normalize_path(raw_path)
                if path:
                    found.append((method.upper(), path))

    # Parse JSON and JSON-like script blocks when they are valid JSON.
    script_blocks = re.findall(r"<script[^>]*>(.*?)</script>", normalized, re.I | re.S)
    candidates = script_blocks + [normalized] if normalized.lstrip().startswith(("{", "[")) else script_blocks
    for block in candidates:
        candidate = block.strip()
        if not candidate:
            continue
        try:
            parsed = json.loads(candidate)
        except (json.JSONDecodeError, TypeError, ValueError):
            continue
        _structured_walk(parsed, found)

    return list(dict.fromkeys(found))


def extract_explicit_method_paths(text):
    normalized = html.unescape(text).replace("\\/","/")
    found = extract_structured_method_paths(normalized)
    for m in METHOD_PATH_RE.finditer(normalized):
        p = normalize_path(m.group(2))
        if p: found.append((m.group(1).upper(),p))
    for m in FULL_API_URL_RE.finditer(normalized):
        p = normalize_path(m.group(0))
        if not p: continue
        window = normalized[max(0,m.start()-1200):m.end()+300]
        methods = list(METHOD_RE.finditer(window))
        found.append(((methods[-1].group(1).upper() if methods else "GET"),p))
    for m in HREF_RE.finditer(normalized):
        p = normalize_path(m.group(1))
        if not p: continue
        window = normalized[max(0,m.start()-1200):m.end()+300]
        methods = list(METHOD_RE.finditer(window))
        found.append(((methods[-1].group(1).upper() if methods else "GET"),p))
    for m in PATH_RE.finditer(normalized):
        p = normalize_path(m.group(0))
        if not p: continue
        window = normalized[max(0,m.start()-1000):m.end()+250]
        methods = list(METHOD_RE.finditer(window))
        found.append(((methods[-1].group(1).upper() if methods else "GET"),p))
    lines = normalized.splitlines()
    for i,line in enumerate(lines):
        methods = METHOD_RE.findall(line)
        if len(methods) != 1: continue
        for nxt in lines[i+1:i+16]:
            candidates = [normalize_path(x) for x in PATH_RE.findall(nxt)]
            candidates = [x for x in candidates if x]
            if candidates:
                found.extend((methods[0].upper(),p) for p in candidates)
                break
    return list(dict.fromkeys(found))


def extract_methods(text): return sorted({m.group(1).upper() for m in METHOD_RE.finditer(text)})

def has_placeholder(path): return bool(re.search(r"\{[^}]+\}|<[^>]+>|:[A-Za-z_][A-Za-z0-9_]*",path))

def sha256_json(value): return hashlib.sha256(json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(",",":")).encode()).hexdigest()

def page_variants(url): return list(dict.fromkeys([url] + ([url[:-3]] if url.endswith(".md") else [])))


def main():
    if not KEY: print("ROAPP_API_KEY is required",file=sys.stderr); return 2
    if not 0 <= MIN_INTERVAL <= 10: print("ROAPP_MIN_REQUEST_INTERVAL must be between 0 and 10 seconds",file=sys.stderr); return 2
    status,index_text,_,error = fetch(DOCS_INDEX)
    if status != 200: print(f"DOCS_INDEX_HTTP={status}",file=sys.stderr); print(error or "documentation index unavailable",file=sys.stderr); return 1
    links=[]; seen=set()
    for m in re.finditer(r"\[([^\]]+)\]\(([^)]+/reference/[^)]+)\)",index_text):
        title,href=m.groups(); url=urljoin(DOCS_INDEX,clean_url(href))
        if url not in seen: seen.add(url); links.append({"title":html.unescape(title).strip(),"url":url})
    links=links[:MAX_DOCS]
    operations=[]
    for link in links:
        bodies=[]; sources=[]; doc_status=None; doc_elapsed=0; doc_error=None
        for variant in page_variants(link["url"]):
            st,text,de,err=fetch(variant); sources.append({"url":variant,"http":st,"elapsed_s":de,"error":err})
            if st==200: bodies.append(text); doc_status=200; doc_elapsed=max(doc_elapsed,de)
            elif doc_status is None: doc_status,doc_error=st,err
        combined="\n".join(bodies)
        pairs=extract_explicit_method_paths(combined) if bodies else []
        methods=sorted({m for m,_ in pairs}); paths=sorted({p for _,p in pairs})
        if not methods and bodies: methods=extract_methods(combined)
        inferred=title_method(link["title"]); method_source="document_body"
        if not methods and inferred: methods=[inferred]; method_source="operation_title"
        elif not methods: method_source="unresolved"
        operations.append({"title":link["title"],"documentation_url":link["url"],"documentation_variants":sources,"documentation_http":doc_status,"documentation_elapsed_s":doc_elapsed,"documentation_error":doc_error,"methods":methods,"method_source":method_source,"paths":paths,"get_probe":None})
    probe_cache={}; headers={"Authorization":f"Bearer {KEY}","Accept":"application/json","User-Agent":"MARSEL-Audit-V20.20"}
    for op in operations:
        if "GET" not in op["methods"]: continue
        concrete=[p for p in op["paths"] if not has_placeholder(p)]
        if not concrete: op["get_probe"]={"status":"NOT_PROBED","reason":"no concrete GET path extracted"}; continue
        probes=[]
        for path in concrete:
            if path not in probe_cache:
                url=BASE+path if path.startswith("/") else BASE+"/"+path
                st,body,pe,pe_err=fetch(url,headers=headers)
                item={"path":path,"http":st,"elapsed_s":pe,"json":None,"error":pe_err}
                if st==200:
                    try:
                        parsed=json.loads(body); item["json"]={"type":type(parsed).__name__,"keys":sorted(parsed.keys())[:50] if isinstance(parsed,dict) else None}
                    except json.JSONDecodeError: item["error"]="HTTP 200 but response is not JSON"
                probe_cache[path]=item
            probes.append(probe_cache[path])
        op["get_probe"]={"status":"PROBED","results":probes}
    def ps(op):
        value=op.get("get_probe"); return value.get("status") if isinstance(value,dict) else None
    dg=sum("GET" in o["methods"] for o in operations); dng=sum(any(m!="GET" for m in o["methods"]) for o in operations)
    resolved=sum(bool(o["paths"]) for o in operations); gp=sum(1 for o in operations if "GET" in o["methods"] and ps(o)=="PROBED")
    gn=sum(1 for o in operations if "GET" in o["methods"] and ps(o)=="NOT_PROBED"); gu=sum(1 for o in operations if "GET" in o["methods"] and ps(o) is None)
    probe_http=[r["http"] for o in operations if ps(o)=="PROBED" for r in o["get_probe"].get("results",[])]
    report={"version":"20.20","readonly":True,"write_requests_made":0,"ro_app_data_mutated":False,"request_policy":{"allowed_method":"GET","min_interval_seconds":MIN_INTERVAL,"max_retries":MAX_RETRIES},"method_policy":{"allowed":["GET"],"forbidden":["POST","PUT","PATCH","DELETE"]},"documentation":{"index":DOCS_INDEX,"index_http":status,"reference_links":len(links),"parse_errors":sum(1 for o in operations if o["documentation_http"]!=200)},"operations":operations,"summary":{"reference_links":len(links),"documented_operations":len(operations),"documented_get_operations":dg,"documented_non_get_operations":dng,"operations_with_extracted_paths":resolved,"operations_without_extracted_paths":len(operations)-resolved,"get_operations_probed":gp,"get_operations_not_probed":gn,"get_operations_with_unresolved_probe_state":gu,"get_probe_http_counts":{str(k):probe_http.count(k) for k in sorted(set(probe_http),key=lambda x:(x is None,x if x is not None else -1))},"write_requests_made":0,"ro_app_data_mutated":False}}
    report["summary"]["inventory_sha256"]=sha256_json(report["operations"])
    with open(OUT,"w",encoding="utf-8") as f: json.dump(report,f,ensure_ascii=False,indent=2)
    print("=== MARSEL V20.20 / OFFICIAL API INVENTORY / READ ONLY ===")
    for k,v in [("DOCS_INDEX_HTTP",status),("REFERENCE_LINKS",len(links)),("DOCUMENTED_OPERATIONS",len(operations)),("DOCUMENTED_GET_OPERATIONS",dg),("OPERATIONS_WITH_EXTRACTED_PATHS",resolved),("OPERATIONS_WITHOUT_EXTRACTED_PATHS",len(operations)-resolved),("GET_OPERATIONS_PROBED",gp),("GET_OPERATIONS_NOT_PROBED",gn),("GET_OPERATIONS_WITH_UNRESOLVED_PROBE_STATE",gu)]: print(f"{k}={v}")
    print("WRITE_REQUESTS_MADE=0"); print(f"INVENTORY_SHA256={report['summary']['inventory_sha256']}"); print(f"REPORT={OUT}"); print("RESULT=READ_ONLY; NO RO APP DATA CREATED, UPDATED OR DELETED")
    return 0

if __name__=="__main__": raise SystemExit(main())
