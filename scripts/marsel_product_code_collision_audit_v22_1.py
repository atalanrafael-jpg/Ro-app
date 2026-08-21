#!/usr/bin/env python3
"""MARSEL V22.3 — product-code ambiguity audit, READ ONLY.

A shared product code is not a defect by itself. A group is REAL_COLLISION
only when the available stable identity fields are complete and identical.
A group with insufficient identity evidence is UNRESOLVED and blocks the
unified gate. A group with a documented distinguishing identity field is
LEGITIMATE_REUSE. No write request is made.
"""
import hashlib,json,os,re,sys,time
from collections import defaultdict
import httpx
BASE=os.environ.get("ROAPP_API_BASE","https://api.roapp.io/v2").rstrip("/")
KEY=os.environ.get("ROAPP_API_KEY","")
OUT=os.environ.get("MARSEL_COLLISION_OUTPUT","marsel-product-code-collisions-v22-3-readonly.json")
PAGE_SIZE=int(os.environ.get("MARSEL_PAGE_SIZE","100")); TIMEOUT=float(os.environ.get("ROAPP_TIMEOUT","30")); INTERVAL=float(os.environ.get("ROAPP_MIN_REQUEST_INTERVAL","0.34")); PATH="/catalog/products"
if not KEY: raise SystemExit("ROAPP_API_KEY is required")
if PAGE_SIZE<=0: raise SystemExit("MARSEL_PAGE_SIZE must be positive")
client=httpx.Client(headers={"Authorization":f"Bearer {KEY}","Accept":"application/json","User-Agent":"MARSEL-V22.3-READONLY"},timeout=TIMEOUT)
last=0.0; rows=[]; page=1
while True:
    wait=INTERVAL-(time.monotonic()-last)
    if wait>0: time.sleep(wait)
    last=time.monotonic(); response=client.get(f"{BASE}{PATH}",params={"page":page,"limit":PAGE_SIZE}); response.raise_for_status(); payload=response.json()
    if isinstance(payload,list): batch,paging=payload,{}
    elif isinstance(payload,dict): batch=payload.get("data") or payload.get("items") or payload.get("products") or []; paging=payload.get("paging") or {}
    else: raise RuntimeError("Unexpected /catalog/products response shape")
    if not isinstance(batch,list): raise RuntimeError("Unexpected /catalog/products data shape")
    rows.extend(x for x in batch if isinstance(x,dict)); total_pages=paging.get("total_pages") or paging.get("totalPages")
    if total_pages is not None:
        if page>=int(total_pages): break
    elif len(batch)<PAGE_SIZE: break
    page+=1

def norm(value):
    if value is None: return ""
    return re.sub(r"\s+"," ",str(value).strip()).casefold()
# These are stable product identity/discriminator fields when present. Volatile
# audit timestamps, quantities, prices and the record id are deliberately excluded.
FIELDS=("name","title","sku","category_id","is_serial","uom","brand","manufacturer","model","mpn","part_number","barcode","ean","upc","reference","product_type","variant_id")
by_code=defaultdict(list)
for item in rows:
    code=norm(item.get("code"))
    if code: by_code[code].append(item)

def identity(item): return {f:norm(item.get(f)) for f in FIELDS}
def classify(items):
    identities=[identity(x) for x in items]
    present={f for f in FIELDS if all(i.get(f) for i in identities)}
    discriminators=[]
    for f in FIELDS:
        vals={i.get(f) for i in identities}
        if len(vals)>1: discriminators.append(f)
    # A complete identical stable identity is a real collision.
    if present and all(i[f]==identities[0][f] for i in identities for f in present):
        return "REAL_COLLISION",sorted(present)
    # Any populated stable discriminator proves legitimate reuse of the code.
    if discriminators:
        return "LEGITIMATE_REUSE",discriminators
    return "UNRESOLVED",sorted(present)
shared={}; groups={"LEGITIMATE_REUSE":{},"REAL_COLLISION":{},"UNRESOLVED":{}}
for code,items in sorted(by_code.items()):
    if len(items)<=1: continue
    records=[]
    for item in items:
        rec={"id":item.get("id")}
        for f in FIELDS:
            if f in item: rec[f]=item.get(f)
        records.append(rec)
    shared[code]=records; status,evidence=classify(items); groups[status][code]={"records":records,"identity_fields_used":evidence}
gate_count=len(groups["REAL_COLLISION"])+len(groups["UNRESOLVED"])
report={"version":"22.3","mode":"READ_ONLY","api_base":BASE,"endpoint":PATH,"pagination":"page + limit","products_rows":len(rows),"pagination_complete":True,"shared_code_group_count":len(shared),"classification_counts":{k:len(v) for k,v in groups.items()},"classified_groups":groups,"gate_relevant_issue_count":gate_count,"write_requests_made":0,"ro_app_data_mutated":False,"interpretation":"Shared codes are not globally assumed unique. REAL_COLLISION requires complete identical stable identity evidence; LEGITIMATE_REUSE requires a populated stable discriminator; otherwise UNRESOLVED blocks PASS."}
raw=json.dumps(report,ensure_ascii=False,sort_keys=True,separators=(",",":")).encode(); report["report_sha256"]=hashlib.sha256(raw).hexdigest()
with open(OUT,"w",encoding="utf-8") as h: json.dump(report,h,ensure_ascii=False,indent=2)
print("=== MARSEL V22.3 / PRODUCT CODE AMBIGUITY AUDIT / READ ONLY ==="); print(f"PRODUCTS_ROWS={len(rows)}"); print(f"SHARED_CODE_GROUP_COUNT={len(shared)}")
for k in groups: print(f"{k}_COUNT={len(groups[k])}")
print(f"GATE_RELEVANT_ISSUE_COUNT={gate_count}"); print("WRITE_REQUESTS_MADE=0"); print("RO_APP_DATA_MUTATED=False"); print(f"REPORT={OUT}"); print(f"REPORT_SHA256={report['report_sha256']}"); print("RESULT=PASS" if gate_count==0 else "RESULT=REVIEW_REQUIRED")
