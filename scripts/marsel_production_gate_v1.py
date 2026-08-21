#!/usr/bin/env python3
"""MARSEL production gate — fail closed, READ ONLY.

Validates independently produced evidence for Issue #19. It never performs
backup, restore, reconciliation, or WRITE operations and can never authorize
production mutation. Evidence must be fresh, explicit and internally safe.
"""
from __future__ import annotations
import json, os, re, sys, time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
MAX_AGE_HOURS=float(os.getenv("MARSEL_EVIDENCE_MAX_AGE_HOURS","24"))
REQUIRED={"backup":"backup_evidence.json","restore":"restore_evidence.json","wix_roapp_reconciliation":"wix_roapp_reconciliation.json","readonly_inventory":"marsel-unified-evidence.json","duplicate_reference":"duplicate_reference_evidence.json","dry_run":"write_dry_run.json","idempotency":"idempotency_evidence.json","rollback":"rollback_evidence.json"}
SECRET_PATTERNS=[re.compile(r"ROAPP_API_KEY\s*=\s*['\"][^'\"]{12,}['\"]"),re.compile(r"Bearer\s+[A-Za-z0-9._\-]{20,}"),re.compile(r"GMAIL_CLIENT_SECRET\s*=\s*['\"][^'\"]{8,}['\"]"),re.compile(r"OPENAI_API_KEY\s*=\s*['\"][^'\"]{12,}['\"]")]
def fail(msg): print(f"PRODUCTION_GATE_FAIL={msg}"); raise SystemExit(1)
def load(path):
    try: value=json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc: fail(f"invalid_json:{path}:{exc}")
    if not isinstance(value,dict): fail(f"evidence_not_object:{path}")
    return value
def passed(doc): return doc.get("status") in {"PASS","VERIFIED","PASSED"} or doc.get("result")=="PASS"
def readonly(doc): return doc.get("readonly") is True and int(doc.get("write_requests_made",0) or 0)==0 and doc.get("ro_app_data_mutated") is False
def evidence_fresh(path): return (time.time()-path.stat().st_mtime) <= MAX_AGE_HOURS*3600
def scan_tree():
    hits=[]
    for path in ROOT.rglob("*"):
        if not path.is_file() or ".git" in path.parts or path.suffix in {".png",".jpg",".jpeg",".zip",".pyc"}: continue
        try: text=path.read_text(encoding="utf-8",errors="ignore")
        except OSError: continue
        for pattern in SECRET_PATTERNS:
            if pattern.search(text): hits.append(str(path.relative_to(ROOT)))
    return sorted(set(hits))
def main():
    if os.getenv("MARSEL_WRITE_APPROVED","false").lower()=="true": fail("write_approval_is_not_authorized_by_automated_gate")
    hits=scan_tree()
    if hits: fail("credential_like_material_in_worktree="+",".join(hits))
    evidence_dir=Path(os.getenv("MARSEL_EVIDENCE_DIR",".")); docs={}; missing=[]; stale=[]
    for name,filename in REQUIRED.items():
        path=evidence_dir/filename
        if not path.exists(): missing.append(filename); continue
        if not evidence_fresh(path): stale.append(filename); continue
        docs[name]=load(path)
    if missing: fail("missing_evidence="+",".join(missing))
    if stale: fail("stale_evidence="+",".join(stale))
    for name,doc in docs.items():
        if not passed(doc): fail(f"gate_not_passed:{name}")
    for name in ("readonly_inventory","duplicate_reference","dry_run","idempotency"):
        if not readonly(docs[name]): fail(f"readonly_safety_failed:{name}")
    if docs["rollback"].get("tested") is not True or docs["rollback"].get("reversible") is not True: fail("rollback_not_tested_and_reversible")
    if docs["dry_run"].get("writes_executed",0) not in (0,False,None): fail("dry_run_executed_write")
    if docs["idempotency"].get("idempotent") is not True: fail("idempotency_not_verified")
    print("PRODUCTION_WRITE_AUTHORIZED=false"); print("PRODUCTION_GATE=PASS_PREWRITE_ONLY"); print("WRITE_REQUESTS_MADE=0"); print("RO_APP_DATA_MUTATED=false"); return 0
if __name__=="__main__": raise SystemExit(main())
