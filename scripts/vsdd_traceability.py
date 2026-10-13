"""VSDD static checks for declared-ID consistency, traceability coverage and spec review."""
import csv
import re
from pathlib import Path

LEVEL = {"intake": 0, "capability-mapped": 1, "specified": 2, "architecture-ready": 3,
         "planned": 4, "implementing": 5, "verifying": 6, "converged": 7, "archived": 8}
ID_RE = re.compile(r"\b(?:FB|SRC|FR|AC|SYS|ARCH|SWE|T|TC)-\d{3,}\b")
PLACEHOLDER = re.compile(r"<[^>\n]{1,100}>|\b(?:TBD|TODO|UNRESOLVED|PENDING)\b|\[NEEDS CLARIFICATION\]|待澄清|待确认|待补充|未填写", re.I)
IN_SCOPE = {"in-scope", "in scope", "范围内", "纳入范围"}
OUT_SCOPE = {"out-of-scope", "out of scope", "范围外", "不在范围内"}
DEFERRED = {"deferred", "延期", "延后处理"}
PASS = {"pass", "passed", "verified", "通过", "已通过", "已验证", "合格"}

def _read(folder, name):
    p = folder / name
    return p.read_text(encoding="utf-8-sig") if p.is_file() else ""

def _rows(text):
    for n, line in enumerate(text.splitlines(), 1):
        s = line.strip()
        if s.startswith("|") and s.endswith("|"):
            cells = [x.strip() for x in s[1:-1].split("|")]
            if not all(re.fullmatch(r"[-:\s]+", x or " ") for x in cells):
                yield n, cells

def _table_ids(text, prefix):
    rx = re.compile(r"^" + re.escape(prefix) + r"-\d{3,}$")
    return [(c[0], n, c) for n, c in _rows(text) if c and rx.fullmatch(c[0])]

def _list_ids(text, prefix):
    rx = re.compile(r"(?m)^\s*(?:[-*]\s*)?(?:#{1,6}\s*)?(" + re.escape(prefix) + r"-\d{3,})\s*(?:[:：|.)]|\s|$)")
    return set(rx.findall(text))

def _list_id_rows(text, prefix):
    rx = re.compile(r"(?m)^\s*(?:[-*]\s*)?(?:#{1,6}\s*)?(" + re.escape(prefix) + r"-\d{3,})\s*(?:[:：|.)]|\s|$)")
    return [(m.group(1), text.count("\n", 0, m.start()) + 1, []) for m in rx.finditer(text)]

def _ok(value):
    value = (value or "").strip()
    return bool(value) and not PLACEHOLDER.search(value)

def _cell(cells, n):
    return cells[n].strip() if len(cells) > n else ""

def _duplicates(rows, label, blockers):
    seen = {}
    for ident, line, _ in rows:
        if ident in seen:
            blockers.append(f"{label}:{line}: duplicate ID {ident} (first on line {seen[ident]})")
        else:
            seen[ident] = line

def _sources(folder, blockers):
    text = _read(folder, "source-register.md")
    rows = _table_ids(text, "SRC")
    _duplicates(rows, "source-register.md", blockers)
    entries = []
    for ident, line, cells in rows:
        if len(cells) < 6:
            blockers.append(f"source-register.md:{line}: each SRC row needs six columns")
            continue
        typ, locator, statement, disposition, reason = (_cell(cells, n) for n in range(1, 6))
        if not all(_ok(v) for v in (typ, locator, statement, disposition)):
            blockers.append(f"source-register.md:{line}: {ident} has empty/placeholder fields")
        d = disposition.lower()
        if d not in IN_SCOPE | OUT_SCOPE | DEFERRED:
            blockers.append(f"source-register.md:{line}: {ident} disposition must be in-scope, out-of-scope, or deferred")
        if d in OUT_SCOPE | DEFERRED and not _ok(reason):
            blockers.append(f"source-register.md:{line}: {ident} needs a disposition rationale")
        entries.append((ident, d, line))
    def meta(label):
        m = re.search(r"(?im)^\s*-\s*" + re.escape(label) + r":\s*(.+?)\s*$", text)
        return m.group(1).strip() if m else ""
    return {"ids": {r[0] for r in rows}, "entries": entries, "review": meta("Coverage review").lower(),
            "reviewer": meta("Reviewed by"), "record": meta("Review record")}

def _check_completeness(folder, blockers, level):
    if level < LEVEL["specified"]:
        return
    text = _read(folder, "feature-spec.md")
    required = {"normal", "boundary", "invalid-input", "state-transition", "failure",
                "recovery", "timing-performance", "interface-semantics", "safety-security-diagnostics"}
    rows = {}
    for line, cells in _rows(text):
        if cells and cells[0].lower() in required:
            key = cells[0].lower()
            if key in rows:
                blockers.append(f"feature-spec.md:{line}: duplicate completeness dimension {key}")
            rows[key] = (line, cells)
    for key in sorted(required - set(rows)):
        blockers.append(f"feature-spec.md: missing completeness row: {key}")
    fr, ac = _list_ids(text, "FR"), _list_ids(text, "AC")
    for key, (line, cells) in rows.items():
        status = _cell(cells, 1).lower()
        refs = ID_RE.findall(_cell(cells, 2))
        reason, record = _cell(cells, 3), _cell(cells, 4)
        if status in {"", "unresolved", "待确认", "待澄清"}:
            blockers.append(f"feature-spec.md:{line}: completeness dimension {key} unresolved")
        elif status in {"applicable", "适用"}:
            if not any(x.startswith("FR-") for x in refs) or not any(x.startswith("AC-") for x in refs):
                blockers.append(f"feature-spec.md:{line}: applicable {key} must link FR and AC IDs")
            for ref in refs:
                if ref.startswith("FR-") and ref not in fr:
                    blockers.append(f"feature-spec.md:{line}: {key} references undeclared {ref}")
                if ref.startswith("AC-") and ref not in ac:
                    blockers.append(f"feature-spec.md:{line}: {key} references undeclared {ref}")
        elif status in {"not-applicable", "not applicable", "不适用"}:
            if not _ok(reason):
                blockers.append(f"feature-spec.md:{line}: not-applicable {key} needs a rationale")
        else:
            blockers.append(f"feature-spec.md:{line}: invalid applicability for {key}: {status}")
        if not _ok(record):
            blockers.append(f"feature-spec.md:{line}: {key} needs a review record reference")

def check_traceability(folder, project_root, stage):
    blockers, level = [], LEVEL.get(stage, 0)
    names = ("feature-brief.md", "source-register.md", "feature-spec.md", "system-requirements.md",
             "architecture.md", "software-requirements.md", "tasks.md", "verification.md")
    docs = {n: _read(folder, n) for n in names}
    fb_matches = re.findall(r"(?im)^\s*-\s*Feature ID[：:]\s*(FB-\d{3,})\s*$", docs["feature-brief.md"])
    fb = set(fb_matches)
    if len(fb_matches) > 1:
        blockers.append("feature-brief.md must declare exactly one FB ID")
    src = _sources(folder, blockers)
    fr_rows = _list_id_rows(docs["feature-spec.md"], "FR")
    ac_rows = _list_id_rows(docs["feature-spec.md"], "AC")
    _duplicates(fr_rows, "feature-spec.md FR", blockers)
    _duplicates(ac_rows, "feature-spec.md AC", blockers)
    fr, ac = {x[0] for x in fr_rows}, {x[0] for x in ac_rows}
    sys_rows, arch_rows = _table_ids(docs["system-requirements.md"], "SYS"), _table_ids(docs["architecture.md"], "ARCH")
    swe_rows, tc_rows = _table_ids(docs["software-requirements.md"], "SWE"), _table_ids(docs["verification.md"], "TC")
    task_rows = []
    for line, text in enumerate(docs["tasks.md"].splitlines(), 1):
        m = re.match(r"^\s*[-*]\s*\[[ xX]\]\s*(T-\d{3,})\b", text)
        if m:
            task_rows.append((m.group(1), line, []))
    for label, rows in (("system-requirements.md", sys_rows), ("architecture.md", arch_rows),
                        ("software-requirements.md", swe_rows), ("tasks.md", task_rows), ("verification.md", tc_rows)):
        _duplicates(rows, label, blockers)
    sys_ids, arch, swe, tasks, tc = ({r[0] for r in rows} for rows in
                                      (sys_rows, arch_rows, swe_rows, task_rows, tc_rows))
    declared = fb | src["ids"] | fr | ac | sys_ids | arch | swe | tasks | tc
    for ref in sorted(set(ID_RE.findall("\n".join(docs.values()))) - declared):
        blockers.append(f"Reference to undeclared ID {ref} in change artifacts")

    edges, path = [], folder / "traceability.csv"
    if not path.is_file():
        blockers.append("missing artifact: traceability.csv")
    else:
        with path.open(newline="", encoding="utf-8-sig") as stream:
            reader = csv.DictReader(stream)
            required = {"source_id", "target_id", "relationship", "status", "evidence"}
            if not required.issubset(set(reader.fieldnames or [])):
                blockers.append("traceability.csv needs source_id,target_id,relationship,status,evidence columns")
            else:
                seen = set()
                for line, row in enumerate(reader, 2):
                    a, b = ((row.get(k) or "").strip() for k in ("source_id", "target_id"))
                    rel, status, evidence = ((row.get(k) or "").strip() for k in ("relationship", "status", "evidence"))
                    if not a or not b or not rel or not status:
                        blockers.append(f"traceability.csv:{line}: source_id, target_id, relationship, status are required")
                        continue
                    if level >= LEVEL["specified"] and not _ok(evidence):
                        blockers.append(f"traceability.csv:{line}: edge {a} -> {b} needs evidence/rationale")
                    if (a, b, rel) in seen:
                        blockers.append(f"traceability.csv:{line}: duplicate edge {a} -> {b} ({rel})")
                    seen.add((a, b, rel))
                    for endpoint in (a, b):
                        if endpoint in declared:
                            continue
                        pm = re.fullmatch(r"(FILE|TEST):(.+)", endpoint)
                        if not pm:
                            blockers.append(f"traceability.csv:{line}: unknown endpoint {endpoint}")
                            continue
                        relpath = Path(pm.group(2))
                        if relpath.is_absolute() or ".." in relpath.parts:
                            blockers.append(f"traceability.csv:{line}: unsafe path {endpoint}")
                            continue
                        resolved = (project_root / relpath).resolve()
                        try:
                            resolved.relative_to(project_root.resolve())
                        except ValueError:
                            blockers.append(f"traceability.csv:{line}: path escapes project root: {endpoint}")
                            continue
                        if level >= LEVEL["verifying"] and not resolved.is_file():
                            blockers.append(f"traceability.csv:{line}: mapped file does not exist: {endpoint}")
                    edges.append({"a": a, "b": b, "status": status, "line": line})
    out, inc = {}, {}
    for edge in edges:
        out.setdefault(edge["a"], set()).add(edge["b"])
        inc.setdefault(edge["b"], set()).add(edge["a"])
    def require(ident, options, direction, label):
        links = out.get(ident, set()) if direction == "out" else inc.get(ident, set())
        if not links.intersection(options):
            blockers.append(f"{ident}: missing {direction}going trace to {label}")

    summary = {"stage": stage, "counts": {"FB":len(fb), "SRC":len(src["ids"]), "FR":len(fr), "AC":len(ac),
        "SYS":len(sys_ids), "ARCH":len(arch), "SWE":len(swe), "T":len(tasks), "TC":len(tc), "edges":len(edges)}}
    if level < LEVEL["specified"]:
        summary["note"] = "Full coverage checks begin at specified stage."
        return sorted(set(blockers)), summary

    if not fb: blockers.append("feature-brief.md must declare Feature ID FB-xxx")
    if not src["ids"]: blockers.append("source-register.md must inventory all input obligations as SRC-xxx")
    for sid, disposition, _ in src["entries"]:
        if disposition in IN_SCOPE: require(sid, fr, "out", "FR-*")
    for ident in fr:
        require(ident, fb, "in", "FB-*")
        require(ident, ac, "out", "AC-*")
        require(ident, src["ids"], "in", "SRC-*")
    for ident in ac: require(ident, fr, "in", "FR-*")
    if not fr: blockers.append("feature-spec.md has no declared FR-* requirements")
    if not ac: blockers.append("feature-spec.md has no declared AC-* acceptance criteria")
    if src["review"] not in {"confirmed", "reviewed", "已确认", "已评审"}:
        blockers.append("source-register.md Coverage review must be confirmed before specified")
    if not _ok(src["reviewer"]): blockers.append("source-register.md must record Reviewed by")
    if not _ok(src["record"]): blockers.append("source-register.md must record Review record")
    _check_completeness(folder, blockers, level)

    if level >= LEVEL["architecture-ready"]:
        if not sys_ids: blockers.append("system-requirements.md has no SYS-* requirements")
        if not arch: blockers.append("architecture.md must declare ARCH-* elements")
        for ident in ac: require(ident, sys_ids, "out", "SYS-*")
        for ident in sys_ids:
            require(ident, ac, "in", "AC-*")
            require(ident, arch, "out", "ARCH-*")
        for ident in arch: require(ident, sys_ids, "in", "SYS-*")

    if level >= LEVEL["planned"]:
        if not swe: blockers.append("software-requirements.md has no SWE-* requirements")
        if not tasks: blockers.append("tasks.md has no T-* tasks")
        if not tc: blockers.append("verification.md must declare TC-* test cases")
        for ident in sys_ids: require(ident, swe, "out", "SWE-*")
        for ident in swe:
            require(ident, sys_ids, "in", "SYS-*")
            require(ident, tasks, "out", "T-*")
            require(ident, tc, "out", "TC-*")
        for ident in tasks: require(ident, swe, "in", "SWE-*")
        for ident in tc: require(ident, swe, "in", "SWE-*")

    if level >= LEVEL["verifying"]:
        for ident in tasks:
            if not any(x.startswith("FILE:") for x in out.get(ident, set())):
                blockers.append(f"{ident}: must trace to a real repository file using FILE:path")
        for ident, line, cells in tc_rows:
            if len(cells) < 7:
                blockers.append(f"verification.md:{line}: TC row needs seven columns (incl. environment, procedure, result, status, evidence)")
                continue
            vals = [_cell(cells, i) for i in range(2, 7)]
            for value, name in zip(vals, ("environment/configuration", "command/procedure", "actual result", "status", "evidence")):
                if not _ok(value): blockers.append(f"verification.md:{line}: {ident} has no {name}")
            if level >= LEVEL["converged"] and vals[3].lower() not in PASS:
                if not (vals[3].lower() in {"waived", "豁免"} and "APPROVAL:" in vals[4]):
                    blockers.append(f"verification.md:{line}: {ident} must pass or include an APPROVAL: waiver reference")
        if level >= LEVEL["converged"]:
            for edge in edges:
                if edge["status"].lower() in {"proposed", "blocked", "invalidated", "待复核", "已失效"}:
                    blockers.append(f"traceability.csv:{edge['line']}: edge {edge['a']} -> {edge['b']} remains {edge['status']}")

    summary["coverage"] = {
        "source_obligations": len(src["entries"]),
        "in_scope_sources_mapped": sum(1 for sid, d, _ in src["entries"] if d not in IN_SCOPE or out.get(sid, set()) & fr),
        "FR_with_AC": sum(1 for x in fr if out.get(x, set()) & ac),
        "AC_with_SYS": sum(1 for x in ac if out.get(x, set()) & sys_ids),
        "SYS_with_ARCH": sum(1 for x in sys_ids if out.get(x, set()) & arch),
        "SYS_with_SWE": sum(1 for x in sys_ids if out.get(x, set()) & swe),
        "SWE_with_task": sum(1 for x in swe if out.get(x, set()) & tasks),
        "SWE_with_test": sum(1 for x in swe if out.get(x, set()) & tc),
        "task_with_file": sum(1 for x in tasks if any(y.startswith("FILE:") for y in out.get(x, set()))),
    }
    return sorted(set(blockers)), summary

def traceability_blockers(folder, project_root, stage):
    return check_traceability(folder, project_root, stage)[0]
