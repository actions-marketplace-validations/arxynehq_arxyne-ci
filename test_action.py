#!/usr/bin/env python3
"""Run this action's own steps locally, against a real CLI and the test twins.

GitHub is where the workflow runs, not where it is written. This executable takes the
three scripts out of `action.yml` and the cases out of `.github/workflows/selftest.yml`,
so neither is copied by hand: a change to the action or to the case table is tested the
next time this runs, and the two cannot drift into disagreeing.

What it asserts is the MAPPING - exit code to job status, row counts to annotations - not
the CLI, which has its own suite upstream.

    python3 test_action.py            # with `arxyne` on PATH
    CLI=/path/to/arxyne python3 test_action.py
"""

from __future__ import annotations

import os
import pathlib
import re
import shutil
import subprocess
import sys
import tempfile

import yaml

HERE = pathlib.Path(__file__).resolve().parent
CLI = os.environ.get("CLI", "arxyne")


def steps_of_action() -> dict[str, dict]:
    doc = yaml.safe_load((HERE / "action.yml").read_text(encoding="utf-8"))
    return {step["id"]: step for step in doc["runs"]["steps"] if step.get("id")}


def cases() -> list[dict]:
    doc = yaml.safe_load((HERE / ".github/workflows/selftest.yml").read_text(encoding="utf-8"))
    job = doc["jobs"]["gate-case"]
    return job["strategy"]["matrix"]["include"]


def substitute(script: str, values: dict[str, str]) -> str:
    """Replace `${{ inputs.x }}` exactly as the runner does before the step runs."""
    for name, value in values.items():
        script = script.replace("${{ inputs." + name + " }}", value)
    left = re.search(r"\$\{\{ inputs\.(\w+) \}\}", script)
    if left:
        raise SystemExit(f"unsubstituted input: {left.group(1)}")
    return script


def run(script: str, env: dict[str, str]) -> subprocess.CompletedProcess:
    return subprocess.run(["bash", "-c", script], env=env, capture_output=True, text=True)


def one_case(case: dict, action: dict[str, dict], work: pathlib.Path, index: int) -> list[str]:
    """Execute the three steps for one case. Returns the failure messages, if any."""
    problems: list[str] = []
    result_file = work / "results.json"
    junit_file = work / "gate.xml"
    outputs = work / "outputs"
    summary = work / "summary.md"
    outputs.write_text("", encoding="utf-8")
    summary.write_text("", encoding="utf-8")

    twin = HERE / "test-twin" / case["twin"]
    # A distinct port per case: the MCP server is its own process, so two cases on one
    # port mean case 2 reads case 1's twin.
    env = dict(
        os.environ,
        PATH=str(pathlib.Path(shutil.which(CLI)).parent) + os.pathsep + os.environ["PATH"],
        ARXYNE_TRACE_MCP="off",
        ARXYNE_HOME=str(twin),
        NO_PROXY="127.0.0.1,localhost",
        ARXYNE_MCP_PORT=str(8600 + index),
        GITHUB_OUTPUT=str(outputs),
        GITHUB_STEP_SUMMARY=str(summary),
        RESULT_FILE=str(result_file),
        PRODUCT=case["product"],
        # The gate step reads its inputs from the environment, not by substitution.
        ARXYNE_GATE_PRODUCT=case["product"],
        ARXYNE_RESULTS_JSON=str(result_file),
        ARXYNE_JUNIT=str(junit_file),
        ARXYNE_FAIL_ON_GATE=case["fail_on_gate"],
    )

    gate = substitute(action["gate"]["run"], {})
    gate_proc = run(gate, env)
    gate_outputs = dict(
        line.split("=", 1) for line in outputs.read_text(encoding="utf-8").splitlines() if "=" in line
    )
    exit_code = gate_outputs.get("exit_code", "")

    # The annotate step always runs, even after a refused gate, and it is what writes the
    # annotations and the summary a reader sees.
    outputs.write_text("", encoding="utf-8")
    annotate_proc = run(action["annotate"]["run"], env)
    if annotate_proc.returncode != 0:
        problems.append(f"annotate step crashed: {annotate_proc.stderr.strip()[:400]}")
    annotate_outputs = dict(
        line.split("=", 1) for line in outputs.read_text(encoding="utf-8").splitlines() if "=" in line
    )

    concl_env = dict(
        env,
        EXIT_CODE=exit_code,
        FAILED_ROWS=annotate_outputs.get("failed_rows", "0"),
        FAIL_ON_GATE=case["fail_on_gate"],
        ALLOW_NO_TARGETS=case["allow_no_targets"],
    )
    concl = run(action["conclusion"]["run"], concl_env)
    conclusion_outputs = dict(
        line.split("=", 1) for line in outputs.read_text(encoding="utf-8").splitlines() if "=" in line
    )

    # The job's status is decided by the conclusion step alone; the gate step runs under
    # continue-on-error so its failure can be reported rather than only suffered.
    outcome = "failure" if concl.returncode != 0 else "success"

    want_outcome = case["outcome"]
    if outcome != want_outcome:
        problems.append(f"outcome: want {want_outcome}, got {outcome}")
    if exit_code != case["exit_code"]:
        problems.append(f"exit_code: want {case['exit_code']}, got {exit_code}")
    verdict = conclusion_outputs.get("verdict", "")
    if verdict != case["verdict"]:
        problems.append(f"verdict: want {case['verdict']!r}, got {verdict!r}")
    for key in ("failed_rows", "declared_rows"):
        if annotate_outputs.get(key, "") != case[key]:
            problems.append(f"{key}: want {case[key]!r}, got {annotate_outputs.get(key, '')!r}")

    # A case that reached a verdict leaves a parseable document and report, and the two
    # must AGREE: the JUnit report is a second rendering of the same verdict, and two
    # renderings that disagree is worse than either alone.
    if case["exit_code"] != "2":
        for path, label in ((result_file, "results.json"), (junit_file, "gate.xml")):
            if not path.exists() or path.stat().st_size == 0:
                problems.append(f"{label} missing")
        try:
            import json
            import xml.etree.ElementTree as ET

            view = json.loads(result_file.read_text(encoding="utf-8"))
            suite = ET.parse(junit_file).getroot()
            declared = str(view["gates"]["attestation"]["declared"])
            if suite.get("failures", "0") != case["failed_rows"]:
                problems.append(
                    f"gate.xml failures={suite.get('failures')}, rows say {case['failed_rows']}"
                )
            if suite.get("tests", "0") != declared:
                problems.append(f"gate.xml tests={suite.get('tests')}, declared={declared}")
        except Exception as exc:  # noqa: BLE001 - any parse problem is a failure here
            problems.append(f"document check crashed: {exc}")

    # Every missed target produces one ::error annotation, whatever the job's own
    # status is - a report-only job still names the KPI, which is the point of it.
    errors = gate_proc.stdout.count("::error") + annotate_proc.stdout.count("::error")
    want_errors = int(case["failed_rows"])
    if errors < want_errors:
        problems.append(f"annotations: want at least {want_errors} ::error, got {errors}")

    body = summary.read_text(encoding="utf-8")
    if f"## Arxyne KPI gate: {case['product']}" not in body:
        problems.append("summary: no heading written")
    if str(case["declared_rows"]) not in body and case["declared_rows"] != "0":
        problems.append("summary: declared count missing")
    return problems


def main() -> int:
    if not shutil.which(CLI):
        print(f"CLI not found: {CLI}", file=sys.stderr)
        return 2
    version = subprocess.run([CLI, "--version"], capture_output=True, text=True).stdout.strip()
    print(f"Action under test: {HERE / 'action.yml'}")
    print(f"CLI: {version}")

    action = steps_of_action()
    work_root = pathlib.Path(tempfile.mkdtemp())
    passed = failed_cases = 0
    try:
        for index, case in enumerate(cases(), start=1):
            work = work_root / f"case{index}"
            work.mkdir()
            problems = one_case(case, action, work, index)
            label = case["label"]
            if problems:
                failed_cases += 1
                print(f"  FAIL {label}")
                for problem in problems:
                    print(f"       {problem}")
            else:
                passed += 1
                print(f"  PASS {label} (exit {case['exit_code']}, {case['outcome']})")
    finally:
        shutil.rmtree(work_root, ignore_errors=True)

    print(f"\n{passed} passed, {failed_cases} failed")
    return 0 if failed_cases == 0 else 1

if __name__ == "__main__":
    raise SystemExit(main())
