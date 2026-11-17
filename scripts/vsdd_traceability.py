"""JSON graph loader and stage-aware traceability coverage audit for VSDD."""
import json
import re
from pathlib import Path
from datetime import datetime, timezone

LEVEL = {
    "intake": 0, "capability-mapped": 1, "specified": 2, "architecture-ready": 3,
    "planned": 4, "implementing": 5, "verifying": 6, "converged": 7, "archived": 8,
}
ID_RE = re.compile(r"\b(?:FB|SRC|FR|AC|SYS|ARCH|SWE|T|TC)-\d{3,}\b")
PLACEHOLDER = re.compile(
    r"<[^>\n]{1,100}>|\b(?:TBD|TODO|UNRESOLVED|PENDING)\b|"
    r"\[NEEDS CLARIFICATION\]|待澄清|待确认|待补充|未填写",
    re.IGNORECASE,
)
IN_SCOPE = {"in-scope", "in scope", "范围内", "纳入范围"}
OUT_SCOPE = {"out-of-scope", "out of scope", "范围外", "不在范围内"}
DEFERRED = {"deferred", "延期", "延后处理"}
PASS = {"pass", "passed", "verified", "通过", "已通过", "已验证", "合格"}
NODE_TYPES = {
    "feature", "source", "feature-requirement", "acceptance-criterion",
    "system-requirement", "architecture-element", "software-requirement",
    "task", "code-file", "test-case",
}
ID_TYPE = {
    "FB": "feature", "SRC": "source", "FR": "feature-requirement",
    "AC": "acceptance-criterion", "SYS": "system-requirement",
    "ARCH": "architecture-element", "SWE": "software-requirement",
    "T": "task", "TC": "test-case",
}
ALLOWED_RELATIONS = {
    ("source", "feature-requirement"): {"derives", "covers"},
    ("feature", "feature-requirement"): {"decomposes-into", "contains"},
    ("feature-requirement", "acceptance-criterion"): {"has-acceptance-criteria", "constrains", "verified-by"},
    ("acceptance-criterion", "system-requirement"): {"derives", "satisfied-by"},
    ("system-requirement", "architecture-element"): {"allocated-to", "implemented-by"},
    ("system-requirement", "software-requirement"): {"allocated-to", "decomposes-into"},
    ("software-requirement", "task"): {"implemented-by", "decomposes-into"},
    ("software-requirement", "test-case"): {"verified-by", "tested-by"},
    ("task", "code-file"): {"modifies", "implemented-in", "implemented-by"},
}

def _read(path):
    return path.read_text(encoding="utf-8-sig") if path.is_file() else ""

def _rows(text):
    for line_no, line in enumerate(text.splitlines(), 1):
        value = line.strip()
        if value.startswith("|") and value.endswith("|"):
            cells = [part.strip() for part in value[1:-1].split("|")]
            if not all(re.fullmatch(r"[-:\s]+", part or " ") for part in cells):
                yield line_no, cells

def _table_ids(text, prefix):
    pattern = re.compile(r"^" + re.escape(prefix) + r"-\d{3,}$")
    return [(cells[0], line_no, cells) for line_no, cells in _rows(text)
            if cells and pattern.fullmatch(cells[0])]

def _list_id_rows(text, prefix):
    pattern = re.compile(
        r"(?m)^\s*(?:[-*]\s*)?(?:#{1,6}\s*)?(" + re.escape(prefix) +
        r"-\d{3,})\s*(?:[:：|.)]|\s|$)"
    )
    return [(match.group(1), text.count("\n", 0, match.start()) + 1, [])
            for match in pattern.finditer(text)]

def _ok(value):
    value = (value or "").strip()
    return bool(value) and not PLACEHOLDER.search(value)

def _cell(cells, index):
    return cells[index].strip() if len(cells) > index else ""

def _duplicates(rows, label, blockers):
    found = {}
    for identifier, line_no, _ in rows:
        if identifier in found:
            blockers.append(f"{label}:{line_no}: duplicate ID {identifier} (first on line {found[identifier]})")
        else:
            found[identifier] = line_no

def _source_inventory(folder, blockers):
    text = _read(folder / "source-register.md")
    rows = _table_ids(text, "SRC")
    _duplicates(rows, "source-register.md", blockers)
    entries = []
    for identifier, line_no, cells in rows:
        if len(cells) < 6:
            blockers.append(f"source-register.md:{line_no}: SRC row requires six columns")
            continue
        source_type, locator, statement, disposition, rationale = (
            _cell(cells, i) for i in range(1, 6)
        )
        if not all(_ok(value) for value in (source_type, locator, statement, disposition)):
            blockers.append(f"source-register.md:{line_no}: {identifier} has empty/placeholder fields")
        disposition = disposition.lower()
        if disposition not in IN_SCOPE | OUT_SCOPE | DEFERRED:
            blockers.append(f"source-register.md:{line_no}: {identifier} disposition must be in-scope, out-of-scope, or deferred")
        if disposition in OUT_SCOPE | DEFERRED and not _ok(rationale):
            blockers.append(f"source-register.md:{line_no}: {identifier} needs disposition rationale")
        entries.append((identifier, disposition, line_no))
    def meta(label):
        match = re.search(r"(?im)^\s*-\s*" + re.escape(label) + r":\s*(.+?)\s*$", text)
        return match.group(1).strip() if match else ""
    return {
        "ids": {row[0] for row in rows}, "entries": entries,
        "review": meta("Coverage review").lower(), "reviewer": meta("Reviewed by"),
        "record": meta("Review record"),
    }

def _declared_nodes(folder, project_root, change_id, blockers, stage):
    result = {}
    paths = {
        "feature": ("feature-brief.md", None),
        "source": ("source-register.md", "SRC"),
        "feature-requirement": ("feature-spec.md", "FR"),
        "acceptance-criterion": ("feature-spec.md", "AC"),
        "system-requirement": ("system-requirements.md", "SYS"),
        "architecture-element": ("architecture.md", "ARCH"),
        "software-requirement": ("software-requirements.md", "SWE"),
        "test-case": ("verification.md", "TC"),
    }
    brief = _read(folder / "feature-brief.md")
    feature_ids = re.findall(r"(?im)^\s*-\s*Feature ID[：:]\s*(FB-\d{3,})\s*$", brief)
    if len(feature_ids) > 1:
        blockers.append("feature-brief.md must declare exactly one FB ID")
    for identifier in feature_ids:
        result[identifier] = {"type": "feature", "artifact": "feature-brief.md", "anchor": identifier}

    sources = _source_inventory(folder, blockers)
    for identifier, _disposition, _line in sources["entries"]:
        result[identifier] = {"type": "source", "artifact": "source-register.md", "anchor": identifier}

    level = LEVEL.get(stage, 0)
    for node_type, (filename, prefix) in paths.items():
        if node_type in {"feature", "source"}:
            continue
        if node_type in {"feature-requirement", "acceptance-criterion"} and level < LEVEL["specified"]:
            continue
        if node_type in {"system-requirement", "architecture-element"} and level < LEVEL["architecture-ready"]:
            continue
        if node_type in {"software-requirement", "test-case"} and level < LEVEL["planned"]:
            continue
        text = _read(folder / filename)
        if node_type in {"feature-requirement", "acceptance-criterion"}:
            rows = _list_id_rows(text, prefix)
        else:
            rows = _table_ids(text, prefix)
        _duplicates(rows, filename + " " + node_type, blockers)
        for identifier, _line, _cells0 in rows:
            result[identifier] = {
                "type": node_type,
                "artifact": filename,
                "anchor": identifier,
            }

    tasks_text = _read(folder / "tasks.md") if level >= LEVEL["planned"] else ""
    task_rows = _table_ids(tasks_text, "T")
    for line_no, line in enumerate(tasks_text.splitlines(), 1):
        match = re.match(r"^\s*[-*]\s*\[[ xX]\]\s*(T-\d{3,})\b", line)
        if match:
            task_rows.append((match.group(1), line_no, []))
    _duplicates(task_rows, "tasks.md", blockers)
    for identifier, _line, _ in task_rows:
        result[identifier] = {
            "type": "task", "artifact": "tasks.md", "anchor": identifier,
        }
    return result, sources

def _expected_for(node, stage):
    level = LEVEL.get(stage, 0)
    kind = node.get("type")
    expected = {"in": set(), "out": set()}
    if kind == "source" and node.get("scope", "in-scope") in IN_SCOPE and level >= LEVEL["specified"]:
        expected["out"].add("feature-requirement")
    elif kind == "feature" and level >= LEVEL["specified"]:
        expected["out"].add("feature-requirement")
    elif kind == "feature-requirement" and level >= LEVEL["specified"]:
        expected["in"].update({"source", "feature"})
        expected["out"].add("acceptance-criterion")
    elif kind == "acceptance-criterion" and level >= LEVEL["specified"]:
        expected["in"].add("feature-requirement")
        if level >= LEVEL["architecture-ready"]:
            expected["out"].add("system-requirement")
    elif kind == "system-requirement" and level >= LEVEL["architecture-ready"]:
        expected["in"].add("acceptance-criterion")
        expected["out"].add("architecture-element")
        if level >= LEVEL["planned"]:
            expected["out"].add("software-requirement")
    elif kind == "architecture-element" and level >= LEVEL["architecture-ready"]:
        expected["in"].add("system-requirement")
    elif kind == "software-requirement" and level >= LEVEL["planned"]:
        expected["in"].add("system-requirement")
        expected["out"].update({"task", "test-case"})
    elif kind == "task" and level >= LEVEL["planned"]:
        expected["in"].add("software-requirement")
        if level >= LEVEL["verifying"]:
            expected["out"].add("code-file")
    elif kind == "test-case" and level >= LEVEL["planned"]:
        expected["in"].add("software-requirement")
    elif kind == "code-file" and level >= LEVEL["verifying"]:
        expected["in"].add("task")
    return expected

def audit_graph(graph, declared, folder, project_root, stage):
    blockers = []
    if not isinstance(graph, dict):
        return ["traceability.json root must be an object"], {"nodes": {}, "edges": {}, "counts": {}}
    if graph.get("schemaVersion") != "1.0":
        blockers.append("traceability.json schemaVersion must be 1.0")
    nodes = graph.get("nodes")
    edges = graph.get("edges")
    if not isinstance(nodes, list) or not isinstance(edges, list):
        return blockers + ["traceability.json must contain nodes[] and edges[]"], {"nodes": {}, "edges": {}, "counts": {}}
    node_by_id = {}
    for index, node in enumerate(nodes):
        if not isinstance(node, dict):
            blockers.append(f"nodes[{index}] must be an object")
            continue
        identifier, kind = node.get("id"), node.get("type")
        if not isinstance(identifier, str) or not identifier.strip():
            blockers.append(f"nodes[{index}] needs a non-empty id")
            continue
        if identifier in node_by_id:
            blockers.append(f"Duplicate node ID: {identifier}")
            continue
        node_by_id[identifier] = node
        if kind not in NODE_TYPES:
            blockers.append(f"{identifier}: unsupported node type {kind}")
        elif identifier.startswith("FILE:"):
            if kind != "code-file":
                blockers.append(f"{identifier}: FILE node must have type code-file")
        else:
            prefix = identifier.split("-", 1)[0]
            if ID_TYPE.get(prefix) != kind:
                blockers.append(f"{identifier}: ID prefix implies {ID_TYPE.get(prefix)}, not {kind}")
        if not _ok(node.get("title")):
            blockers.append(f"{identifier}: title is empty or a placeholder")
        if kind == "source":
            disposition = node.get("scope", "in-scope").lower()
            if disposition not in IN_SCOPE | OUT_SCOPE | DEFERRED:
                blockers.append(f"{identifier}: source scope must be in-scope, out-of-scope or deferred")
        if kind == "code-file":
            file_path = node.get("path") or identifier.removeprefix("FILE:")
            relative = Path(file_path)
            if relative.is_absolute() or ".." in relative.parts:
                blockers.append(f"{identifier}: unsafe repository path")
            elif stage in {"verifying", "converged", "archived"} and not (project_root / relative).is_file():
                blockers.append(f"{identifier}: code file does not exist: {file_path}")
        else:
            artifact = node.get("artifact")
            if not isinstance(artifact, str) or not artifact.strip():
                blockers.append(f"{identifier}: artifact path is required")
            else:
                relative = Path(artifact)
                if relative.is_absolute() or ".." in relative.parts:
                    blockers.append(f"{identifier}: unsafe artifact path {artifact}")
                elif artifact not in {
                    "feature-brief.md","source-register.md","feature-spec.md","system-requirements.md",
                    "architecture.md","software-requirements.md","tasks.md","verification.md"
                }:
                    blockers.append(f"{identifier}: artifact must point to a known change artifact relative to the change folder: {artifact}")
        if identifier in declared:
            expected = declared[identifier]
            if expected["type"] != kind:
                blockers.append(f"{identifier}: graph type {kind} does not match artifact type {expected['type']}")
            if kind != "code-file" and node.get("artifact") != expected["artifact"]:
                blockers.append(f"{identifier}: artifact path must be {expected['artifact']}")
            if kind != "code-file" and node.get("anchor") != identifier:
                blockers.append(f"{identifier}: anchor must match its stable ID")

    declared_ids = set(declared)
    graph_ids = {identifier for identifier in node_by_id if not identifier.startswith("FILE:")}
    for missing in sorted(declared_ids - graph_ids):
        blockers.append(f"{missing}: declared in Markdown but missing from traceability.json nodes[]")
    for extra in sorted(graph_ids - declared_ids):
        blockers.append(f"{extra}: node exists in traceability.json but not in its authoritative Markdown artifact")

    edge_by_id, edge_keys, valid_edges = {}, {}, []
    edge_issues = {}
    for index, edge in enumerate(edges):
        if not isinstance(edge, dict):
            blockers.append(f"edges[{index}] must be an object")
            continue
        raw_edge_id = edge.get("id")
        edge_id = raw_edge_id if isinstance(raw_edge_id, str) and raw_edge_id else f"edges[{index}]"
        if edge_id in edge_by_id:
            blockers.append(f"Duplicate edge ID: {edge_id}")
            edge_issues[edge_id] = "broken"
        edge_by_id[edge_id] = edge
        if not isinstance(raw_edge_id, str) or not re.fullmatch(r"TR-\d{3,}", raw_edge_id):
            blockers.append(f"{edge_id}: edge ID must use TR-xxx")
            edge_issues[edge_id] = "broken"
        source, target = edge.get("source"), edge.get("target")
        relation = edge.get("type")
        status = edge.get("status")
        if not all(isinstance(value, str) and value.strip() for value in (source, target, relation, status)):
            blockers.append(f"{edge_id}: source, target, type and status are required")
            edge_issues[edge_id] = "broken"
            continue
        key = (source, target, relation)
        if key in edge_keys:
            blockers.append(f"{edge_id}: duplicate relation {source} -> {target} ({relation})")
            edge_issues[edge_id] = "broken"
            edge_issues[edge_keys[key]] = "broken"
        else:
            edge_keys[key] = edge_id
        if source not in node_by_id or target not in node_by_id:
            blockers.append(f"{edge_id}: dangling edge {source} -> {target}; endpoint node is missing")
            edge_issues[edge_id] = "broken"
            continue
        pair = (node_by_id[source].get("type"), node_by_id[target].get("type"))
        if pair not in ALLOWED_RELATIONS or relation not in ALLOWED_RELATIONS[pair]:
            blockers.append(f"{edge_id}: invalid relation type {relation} for {pair[0]} -> {pair[1]}")
            edge_issues[edge_id] = "broken"
            continue
        if status not in {"proposed", "confirmed", "verified", "blocked", "invalidated", "waived"}:
            blockers.append(f"{edge_id}: unsupported edge status {status}")
            edge_issues[edge_id] = "broken"
            continue
        evidence = edge.get("evidence")
        evidence_invalid = False
        if not isinstance(evidence, list):
            blockers.append(f"{edge_id}: evidence must be an array")
            evidence_invalid = True
        elif LEVEL.get(stage, 0) >= LEVEL["specified"] and not evidence:
            blockers.append(f"{edge_id}: evidence[] must contain a source/rationale from specified onward")
            evidence_invalid = True
        else:
            for ei, item in enumerate(evidence):
                if not isinstance(item, dict) or not _ok(item.get("artifact")) or not _ok(item.get("note")):
                    blockers.append(f"{edge_id}: evidence[{ei}] must contain artifact and note")
                    evidence_invalid = True
        if evidence_invalid:
            edge_issues[edge_id] = "incomplete"
        if status in {"invalidated", "blocked"} or (LEVEL.get(stage,0) >= LEVEL["converged"] and status not in {"confirmed","verified","waived"}):
            edge_issues[edge_id] = "incomplete"
        if edge_issues.get(edge_id) != "broken":
            valid_edges.append({"id": edge_id, "source": source, "target": target, "type": relation, "status": status})

    outgoing, incoming = {}, {}
    broken_nodes, incomplete_edge_nodes = set(), set()
    for edge in edges:
        if not isinstance(edge, dict):
            continue
        edge_id = edge.get("id") or f"edges[{edges.index(edge)}]"
        issue = edge_issues.get(edge_id)
        destination = broken_nodes if issue == "broken" else incomplete_edge_nodes if issue == "incomplete" else None
        if destination is not None:
            if edge.get("source") in node_by_id:
                destination.add(edge["source"])
            if edge.get("target") in node_by_id:
                destination.add(edge["target"])
    for edge in valid_edges:
        outgoing.setdefault(edge["source"], []).append(edge)
        incoming.setdefault(edge["target"], []).append(edge)

    node_states, node_reasons, node_checks = {}, {}, {}
    for identifier, node in node_by_id.items():
        expected = _expected_for(node, stage)
        actual_in = {node_by_id[e["source"]].get("type") for e in incoming.get(identifier, [])}
        actual_out = {node_by_id[e["target"]].get("type") for e in outgoing.get(identifier, [])}
        missing_in = expected["in"] - actual_in
        missing_out = expected["out"] - actual_out
        node_checks[identifier] = {
            "expectedIncoming": sorted(expected["in"]),
            "expectedOutgoing": sorted(expected["out"]),
            "actualIncoming": sorted(actual_in),
            "actualOutgoing": sorted(actual_out),
            "missingIncoming": sorted(missing_in),
            "missingOutgoing": sorted(missing_out),
        }
        reasons = []
        if identifier in broken_nodes:
            state = "broken"
            reasons.append("has a dangling or semantically invalid edge")
        elif identifier in incomplete_edge_nodes:
            state = "incomplete"
            reasons.append("has a blocked, invalidated or unconfirmed-at-convergence edge")
        elif node.get("status") in {"blocked", "invalidated"}:
            state = "incomplete"
            reasons.append("node lifecycle status is " + str(node.get("status")))
        elif node.get("type") == "source" and str(node.get("scope", "in-scope")).lower() in OUT_SCOPE | DEFERRED:
            state = "excluded"
            reasons.append("source is explicitly out-of-scope or deferred")
        elif not outgoing.get(identifier) and not incoming.get(identifier):
            if expected["in"] or expected["out"]:
                state = "orphan"
                reasons.append("no incoming or outgoing trace links")
            else:
                state = "pending"
                reasons.append("trace links are not required at the current stage")
        elif missing_in or missing_out:
            state = "incomplete"
            if missing_in:
                reasons.append("missing incoming: " + ", ".join(sorted(missing_in)))
            if missing_out:
                reasons.append("missing outgoing: " + ", ".join(sorted(missing_out)))
        else:
            state = "complete"
            reasons.append("all stage-required link types are present")
        node_states[identifier] = state
        node_reasons[identifier] = reasons
        if stage in {"specified","architecture-ready","planned","implementing","verifying","converged"}:
            if state == "orphan":
                blockers.append(f"{identifier}: isolated/orphan node has no valid trace links")
            elif state == "incomplete":
                blockers.append(f"{identifier}: incomplete trace coverage ({'; '.join(reasons)})")
            elif state == "broken":
                blockers.append(f"{identifier}: broken trace link")

    if LEVEL.get(stage, 0) >= LEVEL["verifying"]:
        verification_text = _read(folder / "verification.md")
        for identifier in sorted(x for x,n in node_by_id.items() if n.get("type") == "test-case"):
            match = next(((line,cells) for line,cells in _table_ids(verification_text,"TC") if line and cells[0]==identifier),None)
            if not match:
                blockers.append(f"{identifier}: missing verification.md row")
                node_states[identifier] = "incomplete"
                node_reasons[identifier] = ["missing verification record"]
                continue
            line, cells = match
            values = [_cell(cells, i) for i in range(3, 9)]
            labels = ("environment/configuration", "command/procedure", "expected criteria", "actual result", "status", "evidence")
            for value, label in zip(values, labels):
                if not _ok(value):
                    blockers.append(f"verification.md:{line}: {identifier} has no {label}")
                    node_states[identifier] = "incomplete"
                    node_reasons.setdefault(identifier, []).append(f"missing {label}")
            if LEVEL.get(stage,0) >= LEVEL["converged"] and values[4].lower().strip() not in PASS:
                if not (values[4].lower().strip() in {"waived","豁免"} and "APPROVAL:" in values[5]):
                    blockers.append(f"verification.md:{line}: {identifier} must pass or have an approved APPROVAL: waiver")
                    node_states[identifier] = "incomplete"
                    node_reasons.setdefault(identifier, []).append("verification not passed or formally waived")

    summary = {
        "stage": stage,
        "counts": {
            "nodes": len(node_by_id), "edges": len(edges),
            "complete": sum(1 for x in node_states.values() if x == "complete"),
            "incomplete": sum(1 for x in node_states.values() if x == "incomplete"),
            "orphan": sum(1 for x in node_states.values() if x == "orphan"),
            "broken": sum(1 for x in node_states.values() if x == "broken"),
            "excluded": sum(1 for x in node_states.values() if x == "excluded"),
            "pending": sum(1 for x in node_states.values() if x == "pending"),
        },
        "nodes": node_states,
        "reasons": node_reasons,
        "nodeChecks": node_checks,
        "edges": {key: edge_issues.get(key, "complete") for key in edge_by_id},
        "missingGraphNodes": [
            {"id": ident, **declared[ident]}
            for ident in sorted(set(declared) - {key for key in node_by_id if not key.startswith("FILE:")})
        ],
        "unregisteredGraphNodes": [
            {"id": ident, "type": node.get("type"), "title": node.get("title", ""), "artifact": node.get("artifact", "")}
            for ident, node in sorted(node_by_id.items())
            if ident not in declared and not ident.startswith("FILE:")
        ],
    }
    return sorted(set(blockers)), summary

def load_and_check(folder, project_root, stage):
    blockers = []
    graph_path = folder / "traceability.json"
    if not graph_path.is_file():
        return ["missing artifact: traceability.json"], {"nodes": {}, "edges": {}, "counts": {}}
    try:
        graph = json.loads(graph_path.read_text(encoding="utf-8-sig"))
    except (json.JSONDecodeError, OSError) as exc:
        return [f"traceability.json is not valid JSON: {exc}"], {"nodes": {}, "edges": {}, "counts": {}}
    change_id = folder.name
    declared, sources = _declared_nodes(folder, project_root, change_id, blockers, stage)
    if not isinstance(graph, dict):
        return ["traceability.json root must be a JSON object"], {"nodes": {}, "edges": {}, "counts": {}}
    if graph.get("changeId") != change_id:
        blockers.append(f"traceability.json changeId must be {change_id}")
    nodes = graph.get("nodes", [])
    if isinstance(nodes, list):
        for node in nodes:
            if isinstance(node, dict) and node.get("type") == "source":
                source = next((item for item in sources["entries"] if item[0] == node.get("id")), None)
                if source:
                    scope = str(node.get("scope", "")).lower()
                    if scope != source[1]:
                        blockers.append(f"{node.get('id')}: graph scope must match source-register.md disposition {source[1]}")
    if LEVEL.get(stage, 0) >= LEVEL["specified"]:
        if sources["review"] not in {"confirmed", "reviewed", "已确认", "已评审"}:
            blockers.append("source-register.md Coverage review must be confirmed before specified")
        if not _ok(sources["reviewer"]):
            blockers.append("source-register.md must record Reviewed by")
        if not _ok(sources["record"]):
            blockers.append("source-register.md must record Review record")
        _check_completeness(folder, blockers, stage)
    audit_blockers, summary = audit_graph(graph, declared, folder, project_root, stage)
    blockers.extend(audit_blockers)
    summary["sourceReview"] = {
        "status": sources["review"] or "pending",
        "reviewerRecorded": _ok(sources["reviewer"]),
        "reviewRecordRecorded": _ok(sources["record"]),
    }
    return sorted(set(blockers)), summary

def _check_completeness(folder, blockers, stage):
    if LEVEL.get(stage, 0) < LEVEL["specified"]:
        return
    text = _read(folder / "feature-spec.md")
    required = {"normal", "boundary", "invalid-input", "state-transition", "failure",
                "recovery", "timing-performance", "interface-semantics", "safety-security-diagnostics"}
    rows = {}
    for line, cells in _rows(text):
        if cells and cells[0].lower() in required:
            key = cells[0].lower()
            if key in rows:
                blockers.append(f"feature-spec.md:{line}: duplicate completeness dimension {key}")
            rows[key] = (line,cells)
    for key in sorted(required-set(rows)):
        blockers.append(f"feature-spec.md: missing completeness row: {key}")
    fr = {r[0] for r in _list_id_rows(text,"FR")}
    ac = {r[0] for r in _list_id_rows(text,"AC")}
    for key,(line,cells) in rows.items():
        status = _cell(cells,1).lower()
        refs = ID_RE.findall(_cell(cells,2))
        reason, record = _cell(cells,3), _cell(cells,4)
        if status in {"","unresolved","待确认","待澄清"}:
            blockers.append(f"feature-spec.md:{line}: completeness dimension {key} unresolved")
        elif status in {"applicable","适用"}:
            if not any(x.startswith("FR-") for x in refs) or not any(x.startswith("AC-") for x in refs):
                blockers.append(f"feature-spec.md:{line}: applicable {key} must link FR and AC IDs")
            for ref in refs:
                if ref.startswith("FR-") and ref not in fr:
                    blockers.append(f"feature-spec.md:{line}: {key} references undeclared {ref}")
                if ref.startswith("AC-") and ref not in ac:
                    blockers.append(f"feature-spec.md:{line}: {key} references undeclared {ref}")
        elif status in {"not-applicable","not applicable","不适用"}:
            if not _ok(reason):
                blockers.append(f"feature-spec.md:{line}: not-applicable {key} needs rationale")
        else:
            blockers.append(f"feature-spec.md:{line}: invalid applicability for {key}: {status}")
        if not _ok(record):
            blockers.append(f"feature-spec.md:{line}: {key} needs review-record reference")

def check_traceability(folder, project_root, stage):
    return load_and_check(folder, project_root, stage)

def traceability_blockers(folder, project_root, stage):
    return load_and_check(folder, project_root, stage)[0]


NODE_ARTIFACT = {
    "feature": "feature-brief.md", "source": "source-register.md",
    "feature-requirement": "feature-spec.md", "acceptance-criterion": "feature-spec.md",
    "system-requirement": "system-requirements.md", "architecture-element": "architecture.md",
    "software-requirement": "software-requirements.md", "task": "tasks.md",
    "code-file": "implementation files", "test-case": "verification.md",
}
NODE_STAGE = {
    "feature": "specified", "source": "specified",
    "feature-requirement": "specified", "acceptance-criterion": "specified",
    "system-requirement": "architecture-ready", "architecture-element": "architecture-ready",
    "software-requirement": "planned", "task": "planned",
    "code-file": "verifying", "test-case": "planned",
}
TYPE_LABEL_ZH = {
    "feature": "Feature", "source": "输入来源", "feature-requirement": "Feature 需求",
    "acceptance-criterion": "验收标准", "system-requirement": "系统需求",
    "architecture-element": "架构元素", "software-requirement": "软件需求",
    "task": "实现任务", "code-file": "代码文件", "test-case": "测试用例",
}

def _reachable_nodes(start, graph_nodes, graph_edges, direction="downstream", limit=0):
    by_id = {n.get("id"): n for n in graph_nodes if isinstance(n, dict) and n.get("id")}
    adjacency = {}
    for edge in graph_edges:
        if not isinstance(edge, dict):
            continue
        source, target = edge.get("source"), edge.get("target")
        if source not in by_id or target not in by_id:
            continue
        current, neighbor = (source, target) if direction == "downstream" else (target, source)
        adjacency.setdefault(current, []).append(neighbor)
    depths, queue, result = {start: 0}, [start], []
    while queue:
        current = queue.pop(0)
        depth = depths[current]
        if limit and depth >= limit:
            continue
        for neighbor in adjacency.get(current, []):
            if neighbor in depths:
                continue
            depths[neighbor] = depth + 1
            queue.append(neighbor)
            node = by_id[neighbor]
            result.append({
                "id": neighbor, "type": node.get("type"),
                "typeLabel": TYPE_LABEL_ZH.get(node.get("type"), node.get("type")),
                "title": node.get("title", neighbor),
                "artifact": node.get("artifact") or node.get("path", ""),
                "distance": depth + 1,
            })
    return result

def _repair_plan(node_type, missing_in=(), missing_out=(), fallback_artifact=None):
    own_artifact = NODE_ARTIFACT.get(node_type, fallback_artifact or "traceability.json")
    related_types = set(missing_in) | set(missing_out)
    artifacts = [own_artifact]
    for related in sorted(related_types):
        candidate = NODE_ARTIFACT.get(related)
        if candidate and candidate not in artifacts:
            artifacts.append(candidate)
    if "traceability.json" not in artifacts:
        artifacts.append("traceability.json")
    stages = [NODE_STAGE.get(node_type, "specified")]
    stages.extend(NODE_STAGE.get(t, "specified") for t in related_types)
    stage = max(stages, key=lambda x: LEVEL.get(x, 0))
    if missing_in or missing_out:
        details = []
        if missing_in:
            details.append("补齐上游关系：" + "、".join(TYPE_LABEL_ZH.get(x, x) for x in sorted(missing_in)))
        if missing_out:
            details.append("补齐下游关系：" + "、".join(TYPE_LABEL_ZH.get(x, x) for x in sorted(missing_out)))
        action = "；".join(details) + "。检查双方需求语义、关系类型和证据后更新追溯图。"
    else:
        action = "检查该节点是否应纳入本次变更；若适用，补齐有效上游和下游关系；若确实不适用，应记录正式范围处置，不要删除需求来消除告警。"
    return {"stage": stage, "artifacts": artifacts, "action": action}

def build_audit_report(folder, project_root, stage):
    """Build a machine-readable report with repair guidance and downstream impact analysis."""
    blockers, summary = load_and_check(folder, project_root, stage)
    graph_path = folder / "traceability.json"
    try:
        graph = json.loads(graph_path.read_text(encoding="utf-8-sig")) if graph_path.is_file() else {}
    except (json.JSONDecodeError, OSError):
        graph = {}
    if not isinstance(graph, dict):
        graph = {}
    raw_nodes = graph.get("nodes", []) if isinstance(graph.get("nodes"), list) else []
    raw_edges = graph.get("edges", []) if isinstance(graph.get("edges"), list) else []
    by_id = {n.get("id"): n for n in raw_nodes if isinstance(n, dict) and isinstance(n.get("id"), str)}
    issues = []
    represented_blockers = set()

    def add_issue(code, severity, state, message, node_id=None, edge_id=None,
                  node_type=None, artifact=None, missing_in=None, missing_out=None,
                  affected=None, recommendation=None, source=None):
        issues.append({
            "code": code, "severity": severity, "state": state,
            "nodeId": node_id, "edgeId": edge_id, "nodeType": node_type,
            "artifact": artifact or (NODE_ARTIFACT.get(node_type) if node_type else None),
            "message": message,
            "missingLinks": {
                "incoming": sorted(set(missing_in or [])),
                "outgoing": sorted(set(missing_out or [])),
            },
            "affectedDownstream": affected or [],
            "recommendation": recommendation or {}, "source": source or {},
        })

    for node_id, state in sorted(summary.get("nodes", {}).items()):
        if state not in {"broken", "orphan", "incomplete"}:
            continue
        node = by_id.get(node_id, {})
        node_type = node.get("type")
        check = summary.get("nodeChecks", {}).get(node_id, {})
        missing_in, missing_out = check.get("missingIncoming", []), check.get("missingOutgoing", [])
        reasons = summary.get("reasons", {}).get(node_id, [])
        code = {"broken": "broken-node", "orphan": "orphan-node", "incomplete": "incomplete-node"}[state]
        recommendation = _repair_plan(node_type, missing_in, missing_out, node.get("artifact"))
        affected = _reachable_nodes(node_id, raw_nodes, raw_edges, "downstream")
        add_issue(
            code, "error" if state in {"broken", "orphan"} else "warning", state,
            "；".join(reasons) or f"{node_id} needs traceability review",
            node_id=node_id, node_type=node_type, artifact=node.get("artifact"),
            missing_in=missing_in, missing_out=missing_out, affected=affected,
            recommendation=recommendation,
            source={"artifact": node.get("artifact"), "anchor": node.get("anchor", node_id)},
        )
        represented_blockers.add(node_id)

    for missing in summary.get("missingGraphNodes", []):
        node_id, node_type = missing.get("id"), missing.get("type")
        add_issue(
            "missing-graph-node", "error", "broken",
            f"{node_id} 已在 Markdown 中声明，但没有登记到 traceability.json 的 nodes[]。",
            node_id=node_id, node_type=node_type, artifact=missing.get("artifact"),
            recommendation=_repair_plan(node_type, fallback_artifact=missing.get("artifact")),
            source={"artifact": missing.get("artifact"), "anchor": missing.get("anchor", node_id)},
        )
        represented_blockers.add(node_id)

    for extra in summary.get("unregisteredGraphNodes", []):
        node_id, node_type = extra.get("id"), extra.get("type")
        add_issue(
            "unregistered-graph-node", "error", "broken",
            f"{node_id} 存在于 JSON 图中，但在对应权威 Markdown 工件中找不到声明。",
            node_id=node_id, node_type=node_type, artifact=extra.get("artifact"),
            recommendation=_repair_plan(node_type, fallback_artifact=extra.get("artifact")),
            source={"artifact": extra.get("artifact"), "anchor": node_id},
        )
        represented_blockers.add(node_id)

    edge_issue_states = summary.get("edges", {})
    for index, edge in enumerate(raw_edges):
        if not isinstance(edge, dict):
            add_issue(
                "malformed-edge", "error", "broken", f"edges[{index}] 不是合法对象。",
                edge_id=f"edges[{index}]", artifact="traceability.json",
                recommendation={"stage": stage, "artifacts": ["traceability.json"], "action": "修正或删除该非法关系记录。"},
            )
            continue
        edge_id = edge.get("id") or f"edges[{index}]"
        edge_state = edge_issue_states.get(edge_id, "complete")
        if edge_state == "complete":
            continue
        source_id, target_id = edge.get("source"), edge.get("target")
        source_node, target_node = by_id.get(source_id, {}), by_id.get(target_id, {})
        if edge_state == "broken":
            code, severity = "broken-edge", "error"
            message = f"关系 {edge_id} 的端点或关系定义无效：{source_id} → {target_id}。"
        else:
            code, severity = "incomplete-edge", "warning"
            message = f"关系 {edge_id} 缺少证据、已阻塞/失效，或未达到当前阶段要求的确认状态。"
        recommendation = _repair_plan(source_node.get("type") or target_node.get("type"), fallback_artifact="traceability.json")
        recommendation["artifacts"] = list(dict.fromkeys(
            [x for x in (source_node.get("artifact"), target_node.get("artifact"), "traceability.json") if x]
        ))
        impacted = _reachable_nodes(source_id, raw_nodes, raw_edges, "downstream") if source_id in by_id else []
        add_issue(
            code, severity, edge_state, message,
            node_id=source_id if source_id in by_id else target_id, edge_id=edge_id,
            node_type=source_node.get("type") or target_node.get("type"),
            artifact="traceability.json", affected=impacted,
            recommendation=recommendation,
            source={"source": source_id, "target": target_id, "relationship": edge.get("type")},
        )
        represented_blockers.add(edge_id)

    for blocker in blockers:
        first = blocker.split(":", 1)[0].strip()
        if first in represented_blockers:
            continue
        artifact = next((candidate for candidate in (
            "source-register.md", "feature-spec.md", "feature-brief.md",
            "system-requirements.md", "architecture.md", "software-requirements.md",
            "tasks.md", "verification.md", "traceability.json",
        ) if candidate in blocker), None)
        repair_stage = {
            "source-register.md": "specified", "feature-brief.md": "specified",
            "feature-spec.md": "specified", "system-requirements.md": "architecture-ready",
            "architecture.md": "architecture-ready", "software-requirements.md": "planned",
            "tasks.md": "planned", "verification.md": "verifying",
            "traceability.json": stage,
        }.get(artifact, stage)
        add_issue(
            "artifact-review-blocker", "warning", "incomplete", blocker,
            artifact=artifact or "change artifacts",
            recommendation={
                "stage": repair_stage, "artifacts": [artifact] if artifact else [],
                "action": "打开对应工件，修复该检查项并重新运行 vsdd audit。",
            },
            source={"artifact": artifact},
        )

    severity_order = {"error": 0, "warning": 1, "info": 2}
    issues.sort(key=lambda item: (
        severity_order.get(item["severity"], 9), item.get("code", ""),
        item.get("nodeId") or "", item.get("edgeId") or "", item.get("message", ""),
    ))
    for number, issue in enumerate(issues, 1):
        issue["issueId"] = f"AUD-{number:03d}"

    counts = summary.get("counts", {})
    report_graph_nodes = [dict(node) for node in raw_nodes if isinstance(node, dict)]
    report_node_ids = {n.get("id") for n in report_graph_nodes}
    for missing in summary.get("missingGraphNodes", []):
        node_id = missing.get("id")
        if node_id and node_id not in report_node_ids:
            report_graph_nodes.append({
                "id": node_id, "type": missing.get("type"), "title": node_id,
                "artifact": missing.get("artifact"), "anchor": missing.get("anchor", node_id),
                "auditSynthetic": True,
            })
    report_graph = {
        "schemaVersion": graph.get("schemaVersion", "1.0"),
        "changeId": graph.get("changeId", folder.name),
        "nodes": report_graph_nodes, "edges": raw_edges,
    }
    return {
        "reportVersion": "1.0", "changeId": folder.name, "stage": stage,
        "generatedAt": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "result": "blocked" if blockers else "pass",
        "summary": {
            "totalIssues": len(issues),
            "errors": sum(1 for issue in issues if issue["severity"] == "error"),
            "warnings": sum(1 for issue in issues if issue["severity"] == "warning"),
            "nodes": counts.get("nodes", 0), "edges": counts.get("edges", 0),
            "complete": counts.get("complete", 0), "incomplete": counts.get("incomplete", 0),
            "orphan": counts.get("orphan", 0), "broken": counts.get("broken", 0),
            "excluded": counts.get("excluded", 0), "pending": counts.get("pending", 0),
            "affectedDownstreamNodes": len({item["id"] for issue in issues for item in issue.get("affectedDownstream", [])}),
        },
        "issues": issues, "blockers": blockers, "graph": report_graph,
    }

def render_audit_markdown(report):
    summary = report.get("summary", {})
    lines = [
        f"# VSDD Traceability Audit — {report.get('changeId')}", "",
        f"- Stage: {report.get('stage')}",
        f"- Result: **{str(report.get('result', 'unknown')).upper()}**",
        f"- Generated: {report.get('generatedAt', '')}",
        f"- Issues: {summary.get('totalIssues', 0)} (errors: {summary.get('errors', 0)}, warnings: {summary.get('warnings', 0)})",
        f"- Graph: {summary.get('nodes', 0)} nodes / {summary.get('edges', 0)} edges", "", "## Findings",
    ]
    if not report.get("issues"):
        lines.append("No structural or stage-gate issues were detected.")
    for issue in report.get("issues", []):
        location = issue.get("nodeId") or issue.get("edgeId") or issue.get("artifact") or "Project"
        lines.extend([
            "", f"### {issue.get('issueId')} · {issue.get('severity', '').upper()} · {issue.get('code')}",
            f"- Object: {location}", f"- State: {issue.get('state')}",
            f"- Finding: {issue.get('message')}",
        ])
        missing = issue.get("missingLinks", {})
        if missing.get("incoming") or missing.get("outgoing"):
            lines.append(f"- Missing incoming: {', '.join(missing.get('incoming', [])) or '—'}")
            lines.append(f"- Missing outgoing: {', '.join(missing.get('outgoing', [])) or '—'}")
        impact = issue.get("affectedDownstream", [])
        if impact:
            lines.append("- Affected downstream: " + ", ".join(x["id"] for x in impact))
        rec = issue.get("recommendation", {})
        if rec:
            lines.append(f"- Repair at: {rec.get('stage', report.get('stage'))}")
            if rec.get("artifacts"):
                lines.append("- Artifacts: " + ", ".join(rec["artifacts"]))
            if rec.get("action"):
                lines.append("- Suggested action: " + rec["action"])
    return "\n".join(lines) + "\n"

def traverse_graph(graph, start_id, direction="both", max_depth=0):
    """Return edges reached from a selected node by following upstream/downstream links."""
    nodes = {n.get("id"): n for n in graph.get("nodes", []) if isinstance(n, dict) and n.get("id")}
    edges = [e for e in graph.get("edges", []) if isinstance(e, dict)]
    if start_id not in nodes:
        raise ValueError(f"Unknown trace node: {start_id}")
    visited = {start_id: 0}
    queue = [start_id]
    reached = []
    seen = set()
    while queue:
        current = queue.pop(0)
        depth = visited[current]
        if max_depth and depth >= max_depth:
            continue
        for edge in edges:
            next_id = None
            if direction in {"both","upstream"} and edge.get("target") == current:
                next_id = edge.get("source")
            if direction in {"both","downstream"} and edge.get("source") == current:
                next_id = edge.get("target")
            if next_id is None:
                continue
            key = (edge.get("id"), edge.get("source"), edge.get("target"))
            if key not in seen:
                seen.add(key)
                reached.append(edge)
            if next_id in nodes and next_id not in visited:
                visited[next_id] = depth + 1
                queue.append(next_id)
    return nodes, reached, visited
