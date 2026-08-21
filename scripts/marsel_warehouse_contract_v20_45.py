#!/usr/bin/env python3
"""MARSEL warehouse contract audit — READ ONLY.

Canonical warehouse-list verification. The documented warehouse-list GET is
checked directly first. Undocumented compatibility endpoints are diagnostic
only and can never produce PASS. No branch/location endpoint is used as a
substitute for the warehouse-list contract, and stock GETs cannot substitute
for a successful warehouse-list GET.
"""
from __future__ import annotations
import hashlib, json, os, time
from urllib.parse import urlencode
from urllib.request import Request, urlopen
KEY=os.getenv("ROAPP_API_KEY","")
API_BASE=os.getenv("ROAPP_API_BASE","https://api.roapp.io/v2").rstrip("/")
API_ROOT=API_BASE.removesuffix("/v2")
TIMEOUT=float(os.getenv("ROAPP_WAREHOUSE_TIMEOUT",os.getenv("ROAPP_TIMEOUT","15")))
MAX_RETRIES=max(int(os.getenv("ROAPP_MAX_RETRIES","2")),0)
MIN_INTERVAL=max(float(os.getenv("ROAPP_MIN_REQUEST_INTERVAL","0.34")),0.34)
WAREHOUSE_DOC="https://roappua.readme.io/reference/get-warehouses"
STOCK_DOC="https://roappua.readme.io/reference/get-stock"
def get(url):
    last_error=None
    for attempt in range(MAX_RETRIES+1):
        if attempt: time.sleep(min(2**(attempt-1),4))
        time.sleep(MIN_INTERVAL)
        req=Request(url,headers={"Authorization":f"Bearer {KEY}","Accept":"application/json","User-Agent":"MARSEL-Warehouse-Contract-V20.49"},method="GET")
        started=time.time()
        try:
            with urlopen(req,timeout=TIMEOUT) as r:
                return r.status,r.read().decode("utf-8",errors="replace"),round(time.time()-started,3),None
        except Exception as exc:
            status=getattr(exc,"code",None); body=""
            try: body=exc.read().decode("utf-8",errors="replace")
            except Exception: pass
            last_error=f"{type(exc).__name__}: {exc}"
            if status in {408,429,500,502,503,504} and attempt<MAX_RETRIES: continue
            if status is None and attempt<MAX_RETRIES: continue
            return status,body,round(time.time()-started,3),last_error
    return None,"",0,last_error or "GET request failed"
def parse_json(body):
    try: return json.loads(body),True
    except (json.JSONDecodeError,TypeError): return None,False
def extract_rows(payload):
    if isinstance(payload,list): return [x for x in payload if isinstance(x,dict)]
    if not isinstance(payload,dict): return []
    found=[]
    def walk(value,depth=0):
        if depth>5:return
        if isinstance(value,list):
            rows=[x for x in value if isinstance(x,dict)]
            if rows and any(x.get("id") is not None or x.get("warehouse_id") is not None for x in rows): found.extend(rows); return
            for item in value: walk(item,depth+1)
        elif isinstance(value,dict):
            for key in ("data","warehouses","warehouse","items","results","records","collection"):
                if key in value: walk(value[key],depth+1)
    walk(payload)
    unique=[]; seen=set()
    for row in found:
        sig=json.dumps(row,sort_keys=True,ensure_ascii=False,default=str)
        if sig not in seen: seen.add(sig); unique.append(row)
    return unique
def warehouse_id(row):
    if not isinstance(row,dict): return None
    for key in ("id","warehouse_id"):
        value=row.get(key)
        if isinstance(value,(int,str)) and str(value).strip(): return str(value).strip()
    return None
def probe(path,query,source,documented):
    url=path+(f"?{urlencode(query)}" if query else "")
    status,body,elapsed,error=get(url); payload,valid=parse_json(body) if status==200 else (None,False); rows=extract_rows(payload) if valid else []
    return {"method":"GET","path":url.replace(API_ROOT,""),"url":url,"source":source,"documented_contract":documented,"query":query or {},"http":status,"elapsed_s":elapsed,"json_valid":valid,"error":error,"response_top_level_type":type(payload).__name__ if valid else None,"response_keys":sorted(payload.keys()) if isinstance(payload,dict) else None,"rows_discovered":len(rows)},rows
def main():
    if not KEY: raise SystemExit("ROAPP_API_KEY is required")
    probes=[]; rows=[]
    p,r=probe(f"{API_BASE}/warehouse/",{"type":"product"},WAREHOUSE_DOC,True); probes.append(p); rows.extend(r)
    if not rows:
        p,r=probe(f"{API_BASE}/warehouse/",None,WAREHOUSE_DOC,True); p["reason"]="documented endpoint default-parameter verification"; probes.append(p); rows.extend(r)
    ids=[]
    for row in rows:
        wid=warehouse_id(row)
        if wid and wid not in ids: ids.append(wid)
    for wid in ids:
        url=f"{API_ROOT}/warehouse/goods/{wid}"; status,body,elapsed,error=get(url); parsed,valid=parse_json(body) if status==200 else (None,False)
        probes.append({"method":"GET","path":"/warehouse/goods/{warehouse_id}","warehouse_id":wid,"url":url,"source":STOCK_DOC,"documented_contract":True,"http":status,"elapsed_s":elapsed,"json_valid":valid,"error":error,"response_top_level_type":type(parsed).__name__ if valid else None,"response_keys":sorted(parsed.keys()) if isinstance(parsed,dict) else None})
    list_ok=any(p.get("documented_contract") and p.get("path")=="/v2/warehouse/" and p.get("http")==200 and p.get("json_valid") and p.get("rows_discovered",0)>0 for p in probes)
    stock_ok=any(p.get("documented_contract") and p.get("path")=="/warehouse/goods/{warehouse_id}" and p.get("http")==200 and p.get("json_valid") for p in probes)
    result="PASS" if list_ok and ids else "REVIEW_REQUIRED"
    report={"version":"20.49","mode":"READ_ONLY","result":result,"readonly":True,"write_requests_made":0,"ro_app_data_mutated":False,"official_documentation":{"warehouse_list":WAREHOUSE_DOC,"stock":STOCK_DOC},"warehouse_count":len(ids),"warehouse_ids_discovered":ids,"probes":probes,"confirmed_live_gets":[p for p in probes if p.get("documented_contract") and p.get("http")==200 and p.get("json_valid")],"warehouse_list_contract_verified":list_ok,"stock_corroboration":stock_ok,"diagnostic_only_undocumented_probes":[],"no_write_guarantee":{"write_requests_made":0,"ro_app_data_mutated":False}}
    raw=json.dumps(report,ensure_ascii=False,sort_keys=True,separators=(",",":")).encode(); report["report_sha256"]=hashlib.sha256(raw).hexdigest(); out=os.getenv("WAREHOUSE_CONTRACT_OUTPUT","marsel-unified-warehouse-contract.json")
    with open(out,"w",encoding="utf-8") as fh: json.dump(report,fh,ensure_ascii=False,indent=2)
    print(f"WAREHOUSE_CONTRACT_RESULT={result}"); print(f"WAREHOUSE_COUNT={len(ids)}"); print(f"WAREHOUSE_LIST_CONTRACT_VERIFIED={list_ok}"); print(f"WAREHOUSE_CONFIRMED_LIVE_GETS={len(report['confirmed_live_gets'])}"); print("WRITE_REQUESTS_MADE=0"); print("RO_APP_DATA_MUTATED=false")
if __name__=="__main__": raise SystemExit(main())
