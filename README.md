# Spitfire load test — GitHub Action

Run a load test saved on your self-hosted [Spitfire](https://usespitfire.com) as a performance gate: the step
fails when a threshold fails, the pull request gets a summary comment (updated on later pushes), and the job
summary shows the per-step results.

```yaml
name: Load test
on: [pull_request]
permissions:
  contents: read
  pull-requests: write   # the summary comment
jobs:
  load-test:
    runs-on: ubuntu-latest
    steps:
      - uses: usespitfire/spitfire-action@v1
        with:
          url: https://spitfire.example.com
          token: ${{ secrets.SPITFIRE_TOKEN }}
          test: "Shop: log in, browse, add to cart, check out"
          environment: staging
```

The test runs on your Spitfire runners, not on the GitHub runner: the action starts it, waits for the
result and reports it. The GitHub runner only needs to reach the controller's URL (a self-hosted GitHub
runner inside your network works when the controller is not public).

## Setup

1. In Spitfire: user menu (top right) → **API tokens** → **Create token**.
2. In GitHub: **Settings → Secrets and variables → Actions** → `SPITFIRE_TOKEN`.
3. Add the workflow above. For the pull request comment the job needs `pull-requests: write`; the comment
   needs a Spitfire plan that includes it (otherwise the run still gates, without the comment).

The action downloads the CLI from your controller (so it always matches its version) and checks it against
the SHA-256 the controller sends.

## Inputs

| Input | Default | |
|---|---|---|
| `url` | required | The controller's URL |
| `token` | required | A personal API token (from a secret) |
| `test` | required | The saved test's name or id |
| `environment` | | One of the test's environments, e.g. `staging` |
| `compare` | | Compare two environments at the same time: `A=prod,B=staging` (A the reference, B the candidate) |
| `runners` | `1` | Idle runners to use (ignored with `locations`) |
| `locations` | | One per line: `name=percent[:runners]`, e.g. `istanbul=60:2` |
| `scale` | | Multiply the load: `0.5`, `2` |
| `vars` | | Test variables, one per line: `name=value` |
| `confirm-writes` | `false` | Allow a test whose steps modify data |
| `pr-comment` | `auto` | `true`, `false`, or `auto` (on pull request events) |
| `github-token` | `github.token` | Token for the comment |
| `report` | | Write the run report: `report.pdf` or `report.html` |
| `report-lang` | `en` | `en` or `tr` |
| `summary` | `spitfire-summary.json` | The run summary JSON |
| `timeout` | | e.g. `45m` (default: the planned duration + 15m) |
| `fail-on-inconclusive` | `false` | With `compare`: fail on an inconclusive verdict |
| `fail` | `true` | `false` records the result without failing the step |
| `workspace` | | Workspace name or id |
| `insecure` | `false` | Skip TLS verification (a test controller only) |

## Outputs

| Output | |
|---|---|
| `exit-code` | `0` passed, `99` thresholds failed, `97` aborted by a threshold, `98` the candidate is worse, `1` error, `2` writes not confirmed |
| `result` | `passed`, `failed`, `aborted`, `worse` or `error` |
| `summary` | Path of the summary JSON |

More examples: [`examples/`](examples) (a pull request gate with the report as an artifact, a release
comparison across two locations). Documentation: [CI/CD with Spitfire](https://usespitfire.com/docs/ci-cd).

Runners: Linux (x64, arm64) and Windows (x64).

## Testing the action

`test/local.py` runs the action's steps against a live Spitfire as GitHub would (inputs and defaults,
`GITHUB_OUTPUT`, `GITHUB_STEP_SUMMARY`, `GITHUB_PATH`): the CLI download and its checksum, a passing test,
a failing threshold with `fail` true and false, an unknown test.

## License

MIT. Spitfire itself is commercial software with a free edition: [spitfire.tr/en](https://usespitfire.com).
