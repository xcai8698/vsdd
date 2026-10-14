"""JSON graph loader and stage-aware traceability coverage audit for VSDD."""
import json
import re
from pathlib import Path

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

    edge_by_id, edge_keys, valid_edges = {}, set(), []
    edge_issues = {}
    for index, edge in enumerate(edges):
        if not isinstance(edge, dict):
            blockers.append(f"edges[{index}] must be an object")
            continue
        edge_id = edge.get("id") or f"edges[{index}]"
        if edge_id in edge_by_id:
            blockers.append(f"Duplicate edge ID: {edge_id}")
        edge_by_id[edge_id] = edge
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
        edge_keys.add(key)
        if source not in node_by_id or target not in node_by_id:
            blockers.append(f"{edge_id}: dangling edge {source} -> {target}; endpoint node is missing")
            edge_issues[edge_id] = "broken"
            continue
        pair = (node_by_id[source].get("type"), node_by_id[target].get("type"))
        if pair not in ALLOWED_RELATIONS or relation not in ALLOWED_RELATIONS[pair]:
            blockers.append(f"{edge_id}: invalid relation type {relation} for {pair[0]} -> {pair[1]}")
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
        if not re.fullmatch(r"TR-\d{3,}", str(edge_id)) and not str(edge_id).startswith("edges["):
            blockers.append(f"{edge_id}: edge ID must use TR-xxx")
        if status not in {"proposed", "confirmed", "verified", "blocked", "invalidated", "waived"}:
            blockers.append(f"{edge_id}: unsupported edge status {status}")
        if status in {"invalidated", "blocked"} or (LEVEL.get(stage,0) >= LEVEL["converged"] and status not in {"confirmed","verified","waived"}):
            edge_issues[edge_id] = "incomplete"
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

    node_states, node_reasons = {}, {}
    for identifier, node in node_by_id.items():
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
            state = "orphan"
            reasons.append("no incoming or outgoing trace links")
        else:
            expected = _expected_for(node, stage)
            actual_in = {node_by_id[e["source"]].get("type") for e in incoming.get(identifier, [])}
            actual_out = {node_by_id[e["target"]].get("type") for e in outgoing.get(identifier, [])}
            missing_in = expected["in"] - actual_in
            missing_out = expected["out"] - actual_out
            if missing_in or missing_out:
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
        },
        "nodes": node_states,
        "reasons": node_reasons,
        "edges": {key: edge_issues.get(key, "complete") for key in edge_by_id},
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
