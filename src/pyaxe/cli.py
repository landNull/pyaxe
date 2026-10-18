#!/usr/bin/env python3
"""pyaxe: Python Swiss army knife.

Syntax, pattern, style, dependency, and safety checks with safe local healing.
Auto-scans the tree. Emits JSON for LLMs and a one-line spoken summary.
"""

import argparse
import ast
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


def find_python_files(root: Path = Path(".")) -> List[Path]:
    """Auto-discover .py files, skip common junk dirs."""
    files: List[Path] = []
    skip_dirs = {".git", "__pycache__", ".venv", "venv", "env", ".tox", "node_modules", "build", "dist"}
    for dirpath, dirnames, filenames in os.walk(root):
        # prune
        dirnames[:] = [d for d in dirnames if d not in skip_dirs and not d.startswith(".")]
        for fname in filenames:
            if fname.endswith(".py"):
                files.append(Path(dirpath) / fname)
    return sorted(files)


def tool_available(name: str) -> bool:
    return shutil.which(name) is not None


def run_ruff(files: List[Path], fix: bool = False) -> List[Dict[str, Any]]:
    """Run ruff check, optionally with --fix. Return findings."""
    if not tool_available("ruff"):
        return []
    cmd = ["ruff", "check", "--output-format", "json"]
    if fix:
        cmd.append("--fix")
    cmd.extend(str(f) for f in files)
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        if result.returncode not in (0, 1):  # 1 means findings
            return []
        if not result.stdout.strip():
            return []
        data = json.loads(result.stdout)
        findings = []
        for item in data:
            findings.append({
                "kind": "error" if item.get("code", "").startswith(("E", "F")) else "warning",
                "file": item.get("filename", ""),
                "what": f"{item.get('code', '')}: {item.get('message', '')}",
                "why": item.get("message", ""),
                "fix": item.get("fix", {}).get("message") or "Run ruff check --fix",
                "layer": "lint",
            })
        return findings
    except (subprocess.TimeoutExpired, json.JSONDecodeError, Exception):
        return []


def check_syntax(files: List[Path]) -> List[Dict[str, Any]]:
    """Parse with AST for syntax errors."""
    findings = []
    for f in files:
        try:
            source = f.read_text(encoding="utf-8", errors="replace")
            ast.parse(source, filename=str(f))
        except SyntaxError as e:
            findings.append({
                "kind": "error",
                "file": str(f),
                "what": f"SyntaxError: {e.msg}",
                "why": f"Invalid Python at line {e.lineno}",
                "fix": "Correct the syntax error",
                "layer": "syntax",
            })
        except Exception as e:
            findings.append({
                "kind": "error",
                "file": str(f),
                "what": f"Parse error: {e}",
                "why": "Could not parse file",
                "fix": "Inspect the file",
                "layer": "syntax",
            })
    return findings


def basic_safety_checks(files: List[Path]) -> List[Dict[str, Any]]:
    """Simple safety / best-practice scans via AST or text."""
    findings = []
    for f in files:
        try:
            source = f.read_text(encoding="utf-8", errors="replace")
            tree = ast.parse(source, filename=str(f))
            # Look for exec/eval
            for node in ast.walk(tree):
                if isinstance(node, ast.Call):
                    func = node.func
                    name = None
                    if isinstance(func, ast.Name):
                        name = func.id
                    elif isinstance(func, ast.Attribute):
                        name = func.attr
                    if name in ("exec", "eval"):
                        findings.append({
                            "kind": "warning",
                            "file": str(f),
                            "what": f"Use of {name}()",
                            "why": "Dynamic execution can be a security risk",
                            "fix": "Avoid exec/eval or carefully validate inputs",
                            "layer": "safety",
                        })
            # Bare except
            for node in ast.walk(tree):
                if isinstance(node, ast.ExceptHandler) and node.type is None:
                    findings.append({
                        "kind": "warning",
                        "file": str(f),
                        "what": "Bare except:",
                        "why": "Catches all exceptions including KeyboardInterrupt",
                        "fix": "Catch specific exceptions",
                        "layer": "safety",
                    })
        except Exception:
            pass  # already caught in syntax
    return findings


def format_human(finding: Dict[str, Any]) -> str:
    kind = finding.get("kind", "error").upper()
    layer = finding.get("layer", "unknown")
    return (
        f"{kind}\n"
        f"LAYER: {layer}\n"
        f"FILE: {finding.get('file', '')}\n"
        f"WHAT: {finding.get('what', '')}\n"
        f"WHY: {finding.get('why', '')}\n"
        f"FIX: {finding.get('fix', '')}\n"
    )


def emit(findings: List[Dict[str, Any]], summary: Dict[str, Any], json_mode: bool, speak_mode: bool) -> None:
    if json_mode:
        for f in findings:
            out = {k: v for k, v in f.items() if k in ("kind", "file", "what", "why", "fix")}
            print(json.dumps(out))
        print(json.dumps(summary))
    elif speak_mode:
        failed = summary.get("failed", 0)
        if failed == 0:
            print("SPEAK: All checks passed.")
        else:
            print(f"SPEAK: Found {failed} issue{'s' if failed != 1 else ''}.")
    else:
        for f in findings:
            print(format_human(f))
        failed = summary.get("failed", 0)
        if failed == 0:
            print("OK")
        else:
            print(f"{failed} issue(s) found.")


def do_scan(args: argparse.Namespace) -> int:
    files = find_python_files(Path(args.path or "."))
    if args.json:
        for f in files:
            print(json.dumps({"kind": "file", "file": str(f)}))
        print(json.dumps({"kind": "summary", "count": len(files)}))
    elif args.speak:
        print(f"SPEAK: Found {len(files)} Python file{'s' if len(files) != 1 else ''}.")
    else:
        for f in files:
            print(f)
        print(f"{len(files)} file(s)")
    return 0


def do_check(args: argparse.Namespace, files: Optional[List[Path]] = None) -> Tuple[int, List[Dict[str, Any]]]:
    if files is None:
        if args.files:
            files = [Path(f) for f in args.files]
        else:
            files = find_python_files(Path("."))
    if not files:
        if not args.json and not args.speak:
            print("No Python files found.")
        return 0, []

    findings: List[Dict[str, Any]] = []
    findings.extend(check_syntax(files))
    findings.extend(basic_safety_checks(files))
    findings.extend(run_ruff(files, fix=False))

    failed = sum(1 for f in findings if f.get("kind") == "error")
    summary = {"kind": "summary", "failed": failed, "passed_hint": "ok" if failed == 0 else "issues"}
    emit(findings, summary, args.json, args.speak)
    return 1 if failed else 0, findings


def do_heal(args: argparse.Namespace) -> int:
    if args.files:
        files = [Path(f) for f in args.files]
    else:
        files = find_python_files(Path("."))
    if not files:
        print("No Python files found.")
        return 0

    # Safe heal: ruff --fix if available
    if tool_available("ruff"):
        if not args.json and not args.speak:
            print("Running ruff check --fix ...")
        run_ruff(files, fix=True)
    else:
        if not args.json and not args.speak:
            print("ruff not found; no automatic fixes applied.")

    # Then re-check
    code, _ = do_check(args, files)
    return code


def do_intent(phrase: str, args: argparse.Namespace) -> int:
    phrase = phrase.lower().strip()
    if any(w in phrase for w in ("scan", "list", "find files", "what files")):
        return do_scan(args)
    if any(w in phrase for w in ("heal", "fix", "repair", "auto fix")):
        return do_heal(args)
    if any(w in phrase for w in ("check", "lint", "validate", "test syntax")):
        return do_check(args)[0]
    # default
    if args.speak:
        print("SPEAK: Unknown intent. Try check, heal, or scan.")
    else:
        print("Unknown intent. Supported: check, heal, scan.")
    return 1


def main() -> int:
    parser = argparse.ArgumentParser(prog="pyaxe", description="Python Swiss army knife")
    parser.add_argument("--json", action="store_true", help="JSON output")
    parser.add_argument("--speak", action="store_true", help="Spoken summary line")
    sub = parser.add_subparsers(dest="mode")

    # default is check
    scan_p = sub.add_parser("scan", help="List Python files")
    scan_p.add_argument("path", nargs="?", default=".")

    check_p = sub.add_parser("check", help="Check files or auto-scan")
    check_p.add_argument("files", nargs="*")

    heal_p = sub.add_parser("heal", help="Safe fixes then check")
    heal_p.add_argument("files", nargs="*")

    intent_p = sub.add_parser("intent", help="Map speech to a mode")
    intent_p.add_argument("phrase", nargs="+")

    args = parser.parse_args()

    if args.mode == "scan":
        return do_scan(args)
    if args.mode == "check":
        return do_check(args)[0]
    if args.mode == "heal":
        return do_heal(args)
    if args.mode == "intent":
        phrase = " ".join(args.phrase)
        return do_intent(phrase, args)

    # no mode: default check
    return do_check(args)[0]


if __name__ == "__main__":
    sys.exit(main())
