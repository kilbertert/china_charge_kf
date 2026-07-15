"""Command-line entry point for dify_workflow_toolkit.

Subcommands:
  - validate <yml>            Parse + structurally validate a yml
  - deploy <yml> --app-id ... Deploy via SSH + DB update + restart
  - verify <yml> --app-id ... Run an embedded test plan against the live endpoint
  - test-code <yml>           Run the inline code test (no LLM call)

Typical usage:
  python -m dify_workflow_toolkit validate examples/health_consult_v2.yml
  python -m dify_workflow_toolkit deploy examples/health_consult_v2.yml \
      --ssh-host 124.243.178.156 --ssh-user root --ssh-password 'xxx' \
      --app-id d2623d9a-ac8e-40b6-9ba8-ded2f99f874a
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

import yaml

from dify_workflow_toolkit import (
    Deployer,
    SSHClient,
    TestCase,
    ValidationError,
    Verifier,
    validate_yaml,
)
from dify_workflow_toolkit.verifier import format_report


def _add_ssh_args(p: argparse.ArgumentParser) -> None:
    p.add_argument("--ssh-host", required=True, help="Dify host (ip or hostname)")
    p.add_argument("--ssh-port", type=int, default=22)
    p.add_argument("--ssh-user", default="root")
    p.add_argument(
        "--ssh-password",
        default=os.environ.get("DIFY_SSH_PASSWORD"),
        help="SSH password (or set DIFY_SSH_PASSWORD env var)",
    )
    p.add_argument(
        "--ssh-key",
        default=os.environ.get("DIFY_SSH_KEY"),
        help="Path to SSH private key (overrides --ssh-password)",
    )


def cmd_validate(args: argparse.Namespace) -> int:
    p = Path(args.yml)
    if not p.exists():
        print(f"yml not found: {p}", file=sys.stderr)
        return 2
    try:
        data = validate_yaml(p.read_text(encoding="utf-8"))
    except ValidationError as e:
        print(f"VALIDATION FAILED: {e}", file=sys.stderr)
        return 1
    graph = data["workflow"]["graph"]
    print(f"OK: {len(graph['nodes'])} nodes, {len(graph['edges'])} edges")
    return 0


def cmd_deploy(args: argparse.Namespace) -> int:
    p = Path(args.yml)
    if not p.exists():
        print(f"yml not found: {p}", file=sys.stderr)
        return 2
    must_have = args.must_have.split(",") if args.must_have else None

    with SSHClient(
        args.ssh_host,
        user=args.ssh_user,
        password=args.ssh_password,
        port=args.ssh_port,
        key_filename=args.ssh_key,
    ) as ssh:
        deployer = Deployer(ssh, api_container=args.api_container)
        result = deployer.deploy(
            p,
            args.app_id,
            restart=not args.no_restart,
            must_have_nodes=must_have,
        )
    print(result)
    return 0 if result.verified else 1


def cmd_verify(args: argparse.Namespace) -> int:
    p = Path(args.yml)
    if not p.exists():
        print(f"yml not found: {p}", file=sys.stderr)
        return 2
    cases: list[TestCase] = _load_test_cases(p, endpoint=args.endpoint)
    if not cases:
        print("no test cases defined (add a 'tests:' block to your yml)", file=sys.stderr)
        return 1
    with SSHClient(
        args.ssh_host,
        user=args.ssh_user,
        password=args.ssh_password,
        port=args.ssh_port,
        key_filename=args.ssh_key,
    ) as ssh:
        v = Verifier(ssh, default_endpoint=args.endpoint)
        report = v.run(cases)
    print(format_report(report))
    return 0 if report.failed == 0 else 1


def cmd_test_code(args: argparse.Namespace) -> int:
    p = Path(args.yml)
    if not p.exists():
        print(f"yml not found: {p}", file=sys.stderr)
        return 2
    data = yaml.safe_load(p.read_text(encoding="utf-8"))
    nodes = data["workflow"]["graph"]["nodes"]
    code_node = next(
        (n for n in nodes if n["id"] == args.code_node_id and n["data"]["type"] == "code"),
        None,
    )
    if not code_node:
        print(f"code node {args.code_node_id} not found", file=sys.stderr)
        return 1
    code = code_node["data"]["code"]

    from dify_workflow_toolkit.verifier import run_code_test
    inputs = {
        "text": args.text,
        "has_image": args.has_image,
        "answers": args.answers or "",
    }
    result = run_code_test(code, inputs=inputs, llm_text=args.llm_text)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


def _load_test_cases(yml_path: Path, *, endpoint: str | None) -> list[TestCase]:
    data = yaml.safe_load(yml_path.read_text(encoding="utf-8"))
    block = data.get("tests") or []
    out: list[TestCase] = []
    for c in block:
        out.append(
            TestCase(
                case_id=c["case_id"],
                text=c.get("text", ""),
                answers=c.get("answers", ""),
                has_image=c.get("has_image", False),
                expected=c.get("expected", {}),
                endpoint=c.get("endpoint") or endpoint,
                description=c.get("description", ""),
            )
        )
    return out


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="dify_workflow_toolkit")
    sub = p.add_subparsers(dest="cmd", required=True)

    p_v = sub.add_parser("validate", help="validate a workflow yml")
    p_v.add_argument("yml", help="path to the workflow yml")
    p_v.set_defaults(func=cmd_validate)

    p_d = sub.add_parser("deploy", help="deploy a workflow yml via SSH")
    p_d.add_argument("yml", help="path to the workflow yml")
    p_d.add_argument("--app-id", required=True)
    p_d.add_argument("--no-restart", action="store_true")
    p_d.add_argument(
        "--must-have",
        default="",
        help="comma-separated node ids that must exist in the deployed graph",
    )
    p_d.add_argument("--api-container", default=Deployer.DEFAULT_API_CONTAINER)
    _add_ssh_args(p_d)
    p_d.set_defaults(func=cmd_deploy)

    p_t = sub.add_parser("verify", help="run test cases against the live endpoint")
    p_t.add_argument("yml", help="yml with embedded 'tests:' block")
    p_t.add_argument(
        "--endpoint",
        default="http://127.0.0.1:8013/api/health-consult/chat",
    )
    _add_ssh_args(p_t)
    p_t.set_defaults(func=cmd_verify)

    p_c = sub.add_parser("test-code", help="run an inline code test (no LLM call)")
    p_c.add_argument("yml", help="yml with the code node")
    p_c.add_argument("--code-node-id", default="4002")
    p_c.add_argument("--text", default="")
    p_c.add_argument("--answers", default="")
    p_c.add_argument("--llm-text", default="")
    p_c.add_argument("--has-image", action="store_true")
    p_c.set_defaults(func=cmd_test_code)

    return p


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
