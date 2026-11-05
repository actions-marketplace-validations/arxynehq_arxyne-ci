# Arxyne KPI gate

A GitHub Action that judges a saved Arxyne result against the product's own KPI targets, and
fails the job when a declared target is missed.

## Use it

```yaml
- uses: arxynehq/arxyne-ci@v1.0.4
  with:
    product: ahmed
```

It installs the `arxyne` CLI, reads the product's saved results, writes a summary table and
annotations, publishes the documents, and fails the job on a missed target.

The gate reads **saved results**. It does not run a simulation, so it needs no GPU, no Docker
and no minutes.

## Block a merge

Require the check in branch protection. The failing KPI is named in an annotation on the check
run and in the job summary, so a reviewer sees which requirement failed without opening a log.

The JSON document and the JUnit report are published as an artefact named
`arxyne-gate-<job>-<product>`, kept for a week, whatever the verdict.

## Inputs

| Input | Default | What it does |
|---|---|---|
| `product` | *(required)* | The product to judge, as `arxyne` names it. |
| `fail_on_gate` | `true` | `false` makes it a report-only job that blocks nothing. |
| `allow_no_targets` | `false` | Pass when the product declares no targets at all. |
| `arxyne_home` | *(empty)* | Where the products live. Empty means the default (`~/.arxyne`). |
| `arxyne_version` | `arxyne` | What to install from PyPI. Pin a version for a reproducible pipeline. |
| `python_version` | `3.12` | Python the CLI is installed into. |
| `result_file` | `arxyne-results.json` | Where the results document is written. |
| `junit_file` | `arxyne-gate-junit.xml` | Where the JUnit report is written. |
| `artifact_name` | *(empty)* | Artefact name. Empty means `arxyne-gate-<job>-<product>`; a matrix job should set it. |

## Outputs

| Output | What it is |
|---|---|
| `exit_code` | The CLI's own exit status. |
| `verdict` | What the job decided: `pass`, `missed_target`, `no_targets`, `report_only` or `config_error`. |
| `declared_rows` | How many KPI targets the product declared. |
| `failed_rows` | How many gated KPIs failed. |
| `not_judged_rows` | How many were not judged (NOT RUN, SKIPPED, INCONCLUSIVE). |

## Exit codes

| Code | Meaning |
|---|---|
| `0` | Every declared target passed |
| `3` | A declared target failed |
| `4` | Nothing declared to gate against |
| `2` | Usage or configuration error |

`4` fails by default: a gate with nothing to check has not proved anything. Set
`allow_no_targets: true` only for a project that must merge before targets exist.

A report-only job (`fail_on_gate: false`) publishes the report and blocks nothing, whatever the
verdict. Exit `2` is the one status it does not swallow.

## The same gate without the Action

The action wraps two CLI flags, and both work anywhere:

```bash
arxyne results --product ahmed --json             # the results as one JSON document
arxyne results --product ahmed --fail-on-gate     # non-zero exit on a missed target
arxyne results --product ahmed --junit gate.xml   # a JUnit report for any CI
```

The same gate is a GitLab CI component:
[gitlab.com/arxynehq/arxyne-ci](https://gitlab.com/arxynehq/arxyne-ci).

A working demonstration - a green branch, a red branch, a report-only job - is at
[arxynehq/arxyne-gate-demo](https://github.com/arxynehq/arxyne-gate-demo).

## Testing

`.github/workflows/selftest.yml` runs the action through the real `uses:` path against a real
CLI, one case per branch of the exit-code mapping, and asserts the outputs, the documents and
the artefact. `test_action.py` runs the same cases locally:

```bash
CLI=/path/to/arxyne python3 test_action.py
```

## Licence

MIT. See [LICENSE.md](LICENSE.md).
