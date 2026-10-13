#!/usr/bin/env python3
"""VSDD workflow CLI; Python 3.10+, standard library only."""
import argparse, csv, json, os, re, shutil, sys
from datetime import datetime, timezone
from pathlib import Path

VERSION = "0.2.0"
STAGES = ["intake", "capability-mapped", "specified", "architecture-ready", "planned", "implementing", "verifying", "converged", "archived"]
ARTIFACTS = ["feature-brief.md","capability-map.md","feature-spec.md","system-requirements.md","architecture.md","software-requirements.md","tasks.md","traceability.csv","verification.md","change-record.md","adr.md"]
REQUIRED = {
 "intake":["feature-brief.md"],
 "capability-mapped":["feature-brief.md","capability-map.md"],
 "specified":["feature-brief.md","capability-map.md","feature-spec.md"],
 "architecture-ready":["feature-brief.md","capability-map.md","feature-spec.md","system-requirements.md","architecture.md"],
 "planned":["feature-brief.md","capability-map.md","feature-spec.md","system-requirements.md","architecture.md","software-requirements.md","tasks.md","traceability.csv"],
 "implementing":["feature-brief.md","capability-map.md","feature-spec.md","system-requirements.md","architecture.md","software-requirements.md","tasks.md","traceability.csv"],
 "verifying":["feature-brief.md","capability-map.md","feature-spec.md","system-requirements.md","architecture.md","software-requirements.md","tasks.md","traceability.csv","verification.md"],
 "converged":["feature-brief.md","capability-map.md","feature-spec.md","system-requirements.md","architecture.md","software-requirements.md","tasks.md","traceability.csv","verification.md","change-record.md"],
 "archived":["change-record.md","verification.md"]}
MARKERS = ["UNRESOLVED","[NEEDS CLARIFICATION]","{{","TODO: APPROVAL REQUIRED"]
TEMPLATE = {
"feature-brief.md":"# Feature brief: {name}\n\n## Outcome\nDescribe user/business value and source.\n\n## Scope\n- In scope:\n- Out of scope:\n\n## Constraints and assumptions\nSeparate confirmed facts from assumptions.\n\n## Open questions\n- None / list questions with owner and due date.\n",
"capability-map.md":"# Capability map: {name}\n\n| Candidate capability | Evidence/location | Decision (reuse/extend/create/reject) | Rationale / gap | Owner |\n|---|---|---|---|---|\n",
"feature-spec.md":"# Feature specification: {name}\n\n## Source and status\n- Source(s):\n- Status: proposed / approved\n\n## Scenarios\n### FR-001: <scenario name>\n**Given** <context> **When** <event> **Then** <observable outcome>\n\n## Acceptance criteria\n- AC-001: measurable pass/fail condition linked to FR-001.\n\n## Open decisions\n",
"system-requirements.md":"# System requirements: {name}\n\n| ID | Requirement (shall) | Source Feature/AC | Rationale | Verification method | Status |\n|---|---|---|---|---|---|\n| SYS-001 | <observable system behavior> | FR-001 | <why> | test/analysis/inspection | proposed |\n",
"architecture.md":"# Architecture: {name}\n\n## Context and constraints\n## Components and responsibilities\n## Interfaces and data flow\n## Allocation\n| System requirement | Component/interface | Rationale |\n|---|---|---|\n## Risks and alternatives\n",
"software-requirements.md":"# Software requirements: {name}\n\n| ID | Software requirement (shall) | Allocated SYS ID | Component | Verification | Status |\n|---|---|---|---|---|---|\n| SWE-001 | <testable software behavior> | SYS-001 | <component> | TC-001 | proposed |\n",
"tasks.md":"# Tasks: {name}\n\n- [ ] T-001 Implement <small vertical slice>; requirement: SWE-001; code path hypothesis: <inspect repository>; test: TC-001.\n",
"verification.md":"# Verification: {name}\n\n| Test/evidence ID | Requirement/AC | Environment/configuration | Command/procedure | Actual result | Pass/fail/block | Evidence link |\n|---|---|---|---|---|---|---|\n",
"change-record.md":"# Change record: {name}\n\n## Summary\n## Decisions and approvals (reference real records; never invent)\n## Changed artifacts/code\n## Verification evidence\n## Remaining gaps and disposition\n",
"adr.md":"# ADR: <decision title>\n\n- Status: proposed / accepted / rejected / superseded\n- Context and source: \n- Decision: \n- Alternatives and trade-offs: \n- Consequences: \n",
}
def now(): return datetime.now(timezone.utc).replace(microsecond=0).isoformat()
def slug_ok(s): return bool(re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*",s)) and s not in {"archive",".",".."}
def root(args): return Path(args.root).resolve()
def state_path(folder): return folder/"state.json"
def load_state(folder): return json.loads(state_path(folder).read_text(encoding="utf-8"))
def save_state(folder,state): state["updated_at"]=now(); state_path(folder).write_text(json.dumps(state,indent=2)+"\n",encoding="utf-8")
def bundle_root():
    configured = os.environ.get("VSDD_HOME")
    if configured:
        return Path(configured).expanduser().resolve()
    return Path(__file__).resolve().parent.parent

def copy_tree_merge(src, dst, overwrite=True):
    """递归同步随包资源，不删除项目自有文件。"""
    if not src.exists():
        return 0
    dst.mkdir(parents=True, exist_ok=True)
    copied = 0
    for item in src.iterdir():
        target = dst / item.name
        if item.is_dir():
            copied += copy_tree_merge(item, target, overwrite=overwrite)
        elif overwrite or not target.exists():
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(item, target)
            copied += 1
    return copied

def init(args):
    r = root(args)
    v = r / ".vsdd"
    for rel in ["specs/features", "specs/capabilities", "specs/system",
                "specs/architecture", "specs/software", "specs/history",
                "changes/archive", "templates"]:
        (v / rel).mkdir(parents=True, exist_ok=True)
    (r / ".agents").mkdir(parents=True, exist_ok=True)

    skill_source = bundle_root() / ".agents"
    if not skill_source.exists():
        raise ValueError(f"Packaged Skills directory not found: {skill_source}")
    skills_count = copy_tree_merge(skill_source, r / ".agents", overwrite=True)

    template_source = bundle_root() / ".vsdd" / "templates"
    if template_source.exists():
        templates_count = copy_tree_merge(template_source, v / "templates",
                                          overwrite=bool(getattr(args, "update_templates", False)))
    else:
        templates_count = 0

    constitution = v / "constitution.md"
    source_constitution = bundle_root() / ".vsdd" / "constitution.md"
    if not constitution.exists() and source_constitution.exists():
        shutil.copy2(source_constitution, constitution)
    config = v / "config.json"
    source_config = bundle_root() / ".vsdd" / "config.json"
    if not config.exists() and source_config.exists():
        shutil.copy2(source_config, config)

    print(f"[OK] 已初始化 VSDD：{r}")
    print(f"[OK] 已递归同步 .agents/ 下所有打包文件（包含所有 Skills）：{skills_count} 个")
    print(f"[OK] 已同步模板：{templates_count} 个文件" +
          ("（已覆盖更新）" if getattr(args, "update_templates", False)
           else "（保留项目已存在的模板）"))
    print("[NEXT] 在支持 Agent Skills 的工具中使用 .agents/skills/vsdd-orchestrate/SKILL.md")
    return 0

def new(args):
 s=args.slug
 if not slug_ok(s): raise ValueError("Change ID must be kebab-case, e.g. add-speed-warning")
 r=root(args); v=r/".vsdd"
 if not v.exists(): raise ValueError("Run init first")
 f=v/"changes"/s
 if f.exists(): raise ValueError(f"Change already exists: {f}")
 f.mkdir(parents=True)
 for n,t in TEMPLATE.items(): (f/n).write_text(t.replace("{name}",s.replace("-"," ").title()),encoding="utf-8")
 (f/"traceability.csv").write_text("source_id,target_id,relationship,status,evidence\n",encoding="utf-8")
 (f/"state.json").write_text(json.dumps({"schema_version":"1.0","change_id":s,"stage":"intake","created_at":now(),"updated_at":now(),"owner":"unassigned","approvals":{},"notes":["Scaffold only; no approval or verification is implied."]},indent=2)+"\n",encoding="utf-8")
 print(f"[OK] Created {f}"); return 0
def active(r):
 b=r/".vsdd/changes"
 return sorted(p for p in b.iterdir() if p.is_dir() and p.name!="archive" and (p/"state.json").exists()) if b.exists() else []
def validate_folder(f,stage=None):
 blockers=[]; state={}
 try: state=load_state(f)
 except Exception as e: blockers.append(f"state.json: {e}")
 st=stage or state.get("stage","intake")
 if st not in STAGES: blockers.append(f"unknown stage: {st}"); return blockers
 for n in REQUIRED[st]:
  p=f/n
  if not p.exists(): blockers.append(f"missing artifact: {n}"); continue
  text=p.read_text(encoding="utf-8")
  if not text.strip(): blockers.append(f"empty artifact: {n}")
  if st!="archived" and any(m in text for m in MARKERS): blockers.append(f"placeholder/unresolved marker in {n}")
 if (f/"traceability.csv").exists() and st in ["planned","implementing","verifying","converged"]:
  with (f/"traceability.csv").open(newline="",encoding="utf-8-sig") as h:
   for i,row in enumerate(csv.DictReader(h),2):
    if not row.get("source_id") or not row.get("target_id") or not row.get("relationship"): blockers.append(f"traceability.csv:{i}: source_id, target_id, and relationship are required")
 return blockers
def status(args):
 for f in active(root(args)):
  try: st=load_state(f).get("stage","?")
  except Exception: st="INVALID"
  blockers=validate_folder(f)
  print(f"{f.name}: {st}"+(f" — {len(blockers)} blocker(s)" if blockers else ""))
 return 0
def validate(args):
 folders=[root(args)/".vsdd/changes"/args.slug] if args.slug else active(root(args)); failed=False
 for f in folders:
  if not f.is_dir(): print(f"[ERROR] Unknown change: {f}"); failed=True; continue
  bs=validate_folder(f)
  print(f"{f.name}: "+("PASS" if not bs else "BLOCKED"))
  for b in bs: print("  - "+b)
  failed |= bool(bs)
 return int(failed)
def advance(args):
 f=root(args)/".vsdd/changes"/args.slug
 if not f.is_dir(): raise ValueError(f"Unknown change: {args.slug}")
 state=load_state(f); cur=state.get("stage","intake")
 if args.to not in STAGES or STAGES.index(args.to)!=STAGES.index(cur)+1: raise ValueError(f"Only one-step transitions allowed: {cur} -> {args.to}")
 bs=validate_folder(f,args.to)
 if bs: print("[DENIED] Fix blockers:"); [print(" - "+b) for b in bs]; return 1
 gate=args.to in ["specified","architecture-ready","planned","converged"]
 if gate and not args.approval: raise ValueError(f"Human approval reference required for gate {args.to}: --approval REVIEW-ID")
 if gate: state.setdefault("approvals",{})[args.to]={"reference":args.approval,"recorded_at":now(),"recorded_by":args.recorded_by or "unspecified"}
 state["stage"]=args.to; save_state(f,state); print(f"[OK] {cur} -> {args.to}"); return 0
def trace(args):
 f=root(args)/".vsdd/changes"/args.slug/"traceability.csv"; count=0
 with f.open(newline="",encoding="utf-8-sig") as h:
  for row in csv.DictReader(h):
   if args.id in (row.get("source_id"),row.get("target_id")):
    count+=1; print(f"{row.get('source_id')} --{row.get('relationship')}[{row.get('status')}]--> {row.get('target_id')} | {row.get('evidence','')}")
 if not count: print(f"No traceability edges for {args.id}"); return 1
 return 0
def sync(args):
 f=root(args)/".vsdd/changes"/args.slug; state=load_state(f)
 if state.get("stage")!="converged" or not state.get("approvals",{}).get("converged"): raise ValueError("Only converged changes with recorded convergence approval can sync")
 if not args.approval: raise ValueError("Baseline sync requires a real approval reference")
 mapping={"feature-spec.md":Path("features")/(args.slug+".md"),"capability-map.md":Path("capabilities")/(args.slug+".md"),"system-requirements.md":Path("system")/(args.slug+".md"),"architecture.md":Path("architecture")/(args.slug+".md"),"software-requirements.md":Path("software")/(args.slug+".md")}
 chosen=args.artifact or ["feature-spec.md","system-requirements.md","architecture.md","software-requirements.md"]
 for name in chosen:
  if name not in mapping: raise ValueError(f"Unsupported artifact: {name}")
  src=f/name; dst=root(args)/".vsdd/specs"/mapping[name]
  if not src.exists(): raise ValueError(f"Missing artifact: {name}")
  if dst.exists():
   if not args.overwrite: raise ValueError(f"Baseline exists: {dst}; review delta and pass --overwrite")
   backup=root(args)/".vsdd/specs/history"/now().replace(":","").replace("-","")/mapping[name]; backup.parent.mkdir(parents=True,exist_ok=True); shutil.copy2(dst,backup)
  dst.parent.mkdir(parents=True,exist_ok=True); shutil.copy2(src,dst)
 print(f"[OK] Synced {len(chosen)} artifacts; inspect diffs and retain approval records."); return 0
def archive(args):
 f=root(args)/".vsdd/changes"/args.slug; s=load_state(f)
 if s.get("stage")!="converged" or not s.get("approvals",{}).get("converged"): raise ValueError("Only converged changes with convergence approval can be archived")
 target=root(args)/".vsdd/changes/archive"/(datetime.now().strftime("%Y-%m-%d")+"-"+args.slug)
 if target.exists(): raise ValueError(f"Archive exists: {target}")
 target.parent.mkdir(parents=True,exist_ok=True); shutil.move(str(f),str(target)); print(f"[OK] Archived to {target}"); return 0
def main():
 p=argparse.ArgumentParser(description="VSDD — Verifiable Spec-Driven Development"); p.add_argument("--version",action="version",version=VERSION); sub=p.add_subparsers(dest="cmd",required=True)
 for name,fn in [("init",init),("new",new),("status",status),("validate",validate),("advance",advance),("trace",trace),("sync",sync),("archive",archive)]:
  q=sub.add_parser(name); q.add_argument("--root",default=".")
  if name=="new": q.add_argument("slug")
  if name=="validate": q.add_argument("slug",nargs="?")
  if name=="advance": q.add_argument("slug"); q.add_argument("--to",required=True,choices=STAGES[1:]); q.add_argument("--approval"); q.add_argument("--recorded-by")
  if name=="trace": q.add_argument("slug"); q.add_argument("--id",required=True)
  if name=="sync": q.add_argument("slug"); q.add_argument("--approval",required=True); q.add_argument("--artifact",action="append"); q.add_argument("--overwrite",action="store_true")
  if name=="archive": q.add_argument("slug")
  q.set_defaults(fn=fn)
 args=p.parse_args()
 try: return args.fn(args)
 except (ValueError,OSError,KeyError) as e: print(f"[ERROR] {e}",file=sys.stderr); return 2
if __name__=="__main__": raise SystemExit(main())
