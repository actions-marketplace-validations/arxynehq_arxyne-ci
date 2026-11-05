# Arxyne KPI gate

A GitHub Action that judges saved Arxyne results against a product's own KPI targets and fails
the job when a declared target is missed.

## Use it

```yaml
- uses: arxynehq/arxyne-ci@v1.0.4
  with:
    product: ahmed
```

It installs the `arxyne` CLI, reads the saved results, writes a summary table and annotations,
publishes the documents, and fails the job on a missed target. It reads saved results only, so it
needs no GPU and no Docker.

## Block a merge

Require the check in branch protection. The failing KPI is named in the annotation and the job
summary. The JSON document and JUnit report are kept as `arxyne-gate-<job>-<product>` for a week,
whatever the verdict.

## Inputs

| Input | Default | What it does |
|---|---|---|
| `product` | *(required)* | The product to judge, as `arxyne` names it. |
| `fail_on_gate` | `true` | `false` makes it report-only. |
| `allow_no_targets` | `false` | Pass when the product declares no targets. |
| `arxyne_home` | *(empty)* | Where the products live; empty means `~/.arxyne`. |
| `arxyne_version` | `arxyne` | What to install from PyPI; pin it for reproducibility. |
| `python_version` | `3.12` | Python the CLI installs into. |
| `result_file` | `arxyne-results.json` | Where the results document is written. |
| `junit_file` | `arxyne-gate-junit.xml` | Where the JUnit report is written. |
| `artifact_name` | *(empty)* | Override the artefact name; set it in a matrix job. |

## Outputs

`exit_code`, `verdict` (`pass`, `missed_target`, `no_targets`, `report_only`, `config_error`),
`declared_rows`, `failed_rows`, `not_judged_rows`.

## Exit codes

| Code | Meaning |
|---|---|
| `0` | Every declared target passed |
| `3` | A declared target failed |
| `4` | Nothing declared to gate against |
| `2` | Usage or configuration error |

`4` fails by default: a gate with nothing to check has proved nothing. Set
`allow_no_targets: true` only for a project that must merge before targets exist. Report-only
swallows everything except exit `2`.

## Also available as

- A GitLab CI component: [gitlab.com/arxynehq/arxyne-ci](https://gitlab.com/arxynehq/arxyne-ci)
- A working demo with a green, red and report-only branch:
  [arxynehq/arxyne-gate-demo](https://github.com/arxynehq/arxyne-gate-demo)

The same gate without the Action:

```bash
arxyne results --product ahmed --json             # results as one JSON document
arxyne results --product ahmed --fail-on-gate     # non-zero exit on a missed target
arxyne results --product ahmed --junit gate.xml   # JUnit report for any CI
```

## Licence

MIT. See [LICENSE.md](LICENSE.md).
