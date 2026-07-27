#!/usr/bin/env python3
"""Patch reply-quality nodes into the effective and draft A/B workflows.

Run inside the Dify API container after copying the checked-in A/B DSL files:

    python patch_reply_quality_production.py --dry-run
    python patch_reply_quality_production.py --apply

Only the nodes and edges owned by the reply-quality change are updated. Older
published workflow rows remain untouched. On apply, the original effective and
draft graphs are written to ``--backup-path`` before the transaction commits.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
from collections import Counter
from pathlib import Path

import psycopg2
import psycopg2.extras
import yaml

A_APP_ID = "33fde774-aeed-4026-a7f7-a0e339e1c030"
B_APP_ID = "707dd6d2-059f-47c9-aaac-4638e74969c6"

A_NODE_IDS = {
    "6001-file-gate",
    "6001-file-check",
    "6002",
    "6002-bug-if",
    "6002-bug-route",
    "6098",
    "6100",
    "6100-merge",
    "6100-no-image",
    "6111",
    "6111-faq-gate",
    "6201",
    "6220",
    "6212",
    "6221",
    "6231",
    "6230",
}
A_EDGE_IDS = {
    "e-6001-file-check",
    "e-file-check-gate",
    "e-file-gate-has-6100",
    "e-file-gate-default-no-image",
    "e-6100-merge",
    "e-no-image-merge",
    "e-image-merge-6002",
    "e-6002-bug-route",
    "e-bug-route-if",
    "e-bug-if-bug-switch",
    "e-bug-if-default-6003",
    "e-6111-faq-gate",
    "e-6111-gate-6098",
}
A_REMOVE_EDGE_IDS = {
    "e-6001-6002",
    "e-6001-file-gate",
    "e-6001-6100",
    "e-6002-6003",
    "e-6100-6002",
    "e-6111-6098",
}

B_NODE_IDS = {
    "6098",
    "60985",
    "6099",
    "6177-assigner",
    "62405",
    "62406",
    "62407",
    "62408",
    "62409",
    "62410",
    "62411",
    "6240-parse",
    "6240build",
    "6241",
    "6242",
    "6243",
    "6243-pre",
    "6243b",
    "6901",
}
B_EDGE_IDS = {
    "e-6098-60985",
    "e-60985-6099",
    "e-6171bbugreset-6250",
    "e-6177a-denyout",
    "e-6240-fail-6250if",
    "e-6241-denial-6243",
    "e-62405-62406",
    "e-62406-62407",
    "e-62406-fail-6250",
    "e-62407-62408",
    "e-62408-default-6250",
    "e-62408-hit-62409",
    "e-62409-62410",
    "e-62410-62411",
    "e-62411-6098",
    "e-6601-default-62405",
}
B_REMOVE_NODE_IDS = {
    "6177-denial-confirm-state",
    "6177-deny-out",
    "6240-search-state",
    "6241-route",
    "6240-pre",
    "6240-pre-parse",
    "6240-prebuild",
    "6241-pre",
    "6242-pre",
    "6242b-pre",
    "6242c-pre",
}
B_REMOVE_EDGE_IDS = {
    "e-6098-6099",
    "e-6177confirm-6244",
    "e-6177denyout-6098",
    "e-6240state-6240build",
    "e-6241-default-6241route",
    "e-6241route-6250",
    "e-6241route-6250if",
    "e-6241route-denial-6177confirm",
    "e-6241route-denial-6243",
    "e-6240pre-6240preparse",
    "e-6240prebuild-6240pre",
    "e-6240preparse-6241pre",
    "e-6241pre-default-6250",
    "e-6241pre-hit-6242pre",
    "e-6242bpre-6242cpre",
    "e-6242cpre-6098",
    "e-6242pre-6242bpre",
    "e-6601-default-6240build",
    "e-6601-default-6240prebuild",
    "e-6601-default-6240state",
    "e-6601-default-6250",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--a-yml", default="/tmp/charge_charging_A.reply.yml")
    parser.add_argument("--b-yml", default="/tmp/charge_charging_B.reply.yml")
    parser.add_argument(
        "--backup-path", default="/tmp/reply-quality-workflow-backup.json"
    )
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--dry-run", action="store_true")
    mode.add_argument("--apply", action="store_true")
    return parser.parse_args()


def load_workflow(path: str) -> dict:
    document = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    return document["workflow"]


def as_mapping(value: object) -> dict:
    if isinstance(value, str):
        return json.loads(value)
    if isinstance(value, dict):
        return copy.deepcopy(value)
    raise TypeError(f"unexpected graph type: {type(value)!r}")


def graph_hash(graph: dict) -> str:
    payload = json.dumps(
        graph, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def source_items(graph: dict, key: str) -> dict[str, dict]:
    return {str(item["id"]): copy.deepcopy(item) for item in graph.get(key, [])}


def validate_graph(graph: dict) -> None:
    nodes = graph.get("nodes", [])
    edges = graph.get("edges", [])
    node_ids = [str(node.get("id")) for node in nodes]
    edge_ids = [str(edge.get("id")) for edge in edges]
    duplicate_nodes = [item for item, count in Counter(node_ids).items() if count > 1]
    duplicate_edges = [item for item, count in Counter(edge_ids).items() if count > 1]
    if duplicate_nodes or duplicate_edges:
        raise RuntimeError(
            f"duplicate graph ids: nodes={duplicate_nodes} edges={duplicate_edges}"
        )

    node_map = {str(node["id"]): node for node in nodes}
    dangling = [
        str(edge.get("id"))
        for edge in edges
        if str(edge.get("source")) not in node_map
        or str(edge.get("target")) not in node_map
    ]
    if dangling:
        raise RuntimeError(f"dangling graph edges: {dangling}")

    branch_counts = Counter(
        (str(edge.get("source")), str(edge.get("sourceHandle")))
        for edge in edges
        if node_map[str(edge.get("source"))].get("data", {}).get("type")
        in {"if-else", "question-classifier"}
    )
    duplicate_branches = [key for key, count in branch_counts.items() if count > 1]
    if duplicate_branches:
        raise RuntimeError(f"duplicate branch outputs: {duplicate_branches}")

    incoming = {node_id: 0 for node_id in node_ids}
    outgoing = {node_id: [] for node_id in node_ids}
    for edge in edges:
        source, target = str(edge["source"]), str(edge["target"])
        outgoing[source].append(target)
        incoming[target] += 1
    queue = [node_id for node_id, count in incoming.items() if count == 0]
    visited = 0
    while queue:
        source = queue.pop()
        visited += 1
        for target in outgoing[source]:
            incoming[target] -= 1
            if incoming[target] == 0:
                queue.append(target)
    if visited != len(node_ids):
        cyclic = sorted(node_id for node_id, count in incoming.items() if count > 0)
        raise RuntimeError(f"workflow graph contains a directed cycle: {cyclic}")


def validate_dataset_refs(cursor, graph: dict) -> None:
    dataset_ids = {
        str(dataset_id)
        for node in graph.get("nodes", [])
        for dataset_id in node.get("data", {}).get("dataset_ids", [])
    }
    if not dataset_ids:
        return
    cursor.execute(
        "SELECT id::text AS id FROM datasets WHERE id::text = ANY(%s)",
        (list(dataset_ids),),
    )
    found = {str(row["id"]) for row in cursor.fetchall()}
    missing = sorted(dataset_ids - found)
    if missing:
        raise RuntimeError(f"workflow references missing datasets: {missing}")


def patch_graph(
    current: dict,
    source: dict,
    *,
    node_ids: set[str],
    edge_ids: set[str],
    remove_node_ids: set[str] | None = None,
    remove_edge_ids: set[str] | None = None,
) -> dict:
    remove_node_ids = remove_node_ids or set()
    remove_edge_ids = remove_edge_ids or set()
    source_nodes = source_items(source, "nodes")
    source_edges = source_items(source, "edges")
    missing_nodes = node_ids - source_nodes.keys()
    missing_edges = edge_ids - source_edges.keys()
    if missing_nodes or missing_edges:
        raise RuntimeError(
            f"source DSL incomplete: missing_nodes={sorted(missing_nodes)} "
            f"missing_edges={sorted(missing_edges)}"
        )

    result = copy.deepcopy(current)
    kept_nodes = [
        node
        for node in result.get("nodes", [])
        if str(node.get("id")) not in node_ids | remove_node_ids
    ]
    kept_nodes.extend(
        copy.deepcopy(node)
        for node in source.get("nodes", [])
        if str(node.get("id")) in node_ids
    )
    result["nodes"] = kept_nodes

    kept_edges = [
        edge
        for edge in result.get("edges", [])
        if str(edge.get("id")) not in edge_ids | remove_edge_ids
        and str(edge.get("source")) not in remove_node_ids
        and str(edge.get("target")) not in remove_node_ids
    ]
    kept_edges.extend(
        copy.deepcopy(edge)
        for edge in source.get("edges", [])
        if str(edge.get("id")) in edge_ids
    )
    result["edges"] = kept_edges
    return result


def target_workflows(cursor, app_id: str) -> list[tuple[str, str]]:
    cursor.execute("SELECT workflow_id FROM apps WHERE id=%s", (app_id,))
    app = cursor.fetchone()
    if not app or not app["workflow_id"]:
        raise RuntimeError(f"app {app_id} has no effective workflow")
    cursor.execute(
        "SELECT id FROM workflows WHERE app_id=%s AND version='draft'", (app_id,)
    )
    draft = cursor.fetchone()
    targets = [(str(app["workflow_id"]), "effective")]
    if draft and str(draft["id"]) != str(app["workflow_id"]):
        targets.append((str(draft["id"]), "draft"))
    return targets


def main() -> None:
    args = parse_args()
    source_a = load_workflow(args.a_yml)["graph"]
    source_b = load_workflow(args.b_yml)["graph"]
    specs = {
        A_APP_ID: {
            "source": source_a,
            "nodes": A_NODE_IDS,
            "edges": A_EDGE_IDS,
            "remove_nodes": set(),
            "remove_edges": A_REMOVE_EDGE_IDS,
        },
        B_APP_ID: {
            "source": source_b,
            "nodes": B_NODE_IDS,
            "edges": B_EDGE_IDS,
            "remove_nodes": B_REMOVE_NODE_IDS,
            "remove_edges": B_REMOVE_EDGE_IDS,
        },
    }
    connection = psycopg2.connect(
        host=os.environ.get("DB_HOST", "db"),
        port=int(os.environ.get("DB_PORT", "5432")),
        user=os.environ.get("DB_USERNAME", "postgres"),
        password=os.environ.get("DB_PASSWORD", ""),
        dbname=os.environ.get("DB_DATABASE", "dify"),
    )
    backups: list[dict] = []
    changes: list[dict] = []
    try:
        with connection.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cursor:
            for app_id, spec in specs.items():
                for workflow_id, kind in target_workflows(cursor, app_id):
                    cursor.execute(
                        "SELECT graph, version FROM workflows WHERE id=%s FOR UPDATE",
                        (workflow_id,),
                    )
                    row = cursor.fetchone()
                    if not row:
                        raise RuntimeError(f"workflow not found: {workflow_id}")
                    before = as_mapping(row["graph"])
                    after = patch_graph(
                        before,
                        spec["source"],
                        node_ids=spec["nodes"],
                        edge_ids=spec["edges"],
                        remove_node_ids=spec["remove_nodes"],
                        remove_edge_ids=spec["remove_edges"],
                    )
                    validate_graph(after)
                    validate_dataset_refs(cursor, after)
                    before_hash = graph_hash(before)
                    after_hash = graph_hash(after)
                    backups.append(
                        {
                            "app_id": app_id,
                            "workflow_id": workflow_id,
                            "kind": kind,
                            "version": str(row["version"]),
                            "graph": before,
                        }
                    )
                    changes.append(
                        {
                            "app_id": app_id,
                            "workflow_id": workflow_id,
                            "kind": kind,
                            "before": before_hash,
                            "after": after_hash,
                            "changed": before_hash != after_hash,
                            "nodes": len(after.get("nodes", [])),
                            "edges": len(after.get("edges", [])),
                        }
                    )
                    if args.apply and before_hash != after_hash:
                        cursor.execute(
                            "UPDATE workflows SET graph=%s, updated_at=NOW() WHERE id=%s",
                            (json.dumps(after, ensure_ascii=False), workflow_id),
                        )
            if args.apply:
                Path(args.backup_path).write_text(
                    json.dumps(backups, ensure_ascii=False), encoding="utf-8"
                )
                connection.commit()
            else:
                connection.rollback()
    finally:
        connection.close()
    print(json.dumps({"apply": args.apply, "changes": changes}, ensure_ascii=False))


if __name__ == "__main__":
    main()
