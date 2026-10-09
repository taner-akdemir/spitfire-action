#!/usr/bin/env python3
"""Runs the action's steps (action.yml) against a live Spitfire, as GitHub
would: inputs and their defaults in the step env, GITHUB_OUTPUT,
GITHUB_STEP_SUMMARY, GITHUB_PATH, RUNNER_TEMP. Needs SPITFIRE_URL and
SPITFIRE_ADMIN_EMAIL / SPITFIRE_ADMIN_PASSWORD (a Spitfire docs-shots stack:
STACK_RUN='python3 …/test/local.py' bash scripts/docs-shots/run.sh in the
Spitfire repo) and SPITFIRE_CLI, a CLI built for this machine: the download
step is checked for a Linux runner (the file and its checksum), the run step
runs the local CLI."""
import json, os, re, subprocess, sys, tempfile, urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
import yaml  # noqa: E402

action = yaml.safe_load(open(os.path.join(HERE, "..", "action.yml")))
URL = os.environ["SPITFIRE_URL"].rstrip("/")
API = URL + "/api/v1"
fails = 0


def call(method, path, body=None, token=None):
    req = urllib.request.Request(API + path, method=method, data=None if body is None else json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json", **({"Authorization": "Bearer " + token} if token else {})})
    with urllib.request.urlopen(req) as r:
        raw = r.read()
        return json.loads(raw) if raw else None


def check(name, ok, detail=""):
    global fails
    print(("ok    " if ok else "FAIL  ") + name + ("" if ok else f"  {detail}"))
    fails += 0 if ok else 1


tok = call("POST", "/auth/login", {"email": os.environ["SPITFIRE_ADMIN_EMAIL"], "password": os.environ["SPITFIRE_ADMIN_PASSWORD"]})["data"]["accessToken"]
pat = call("POST", "/me/api-tokens", {"name": "action test", "expiresInDays": 1}, tok)["data"]["token"]


def run_action(inputs, step_ids=None, extra_env=None, path_first=None):
    """Runs the steps; returns (exit code, outputs, step summary, GITHUB_PATH lines)."""
    tmp = tempfile.mkdtemp(prefix="sf-action-")
    files = {k: os.path.join(tmp, k) for k in ("output", "summary", "path")}
    for f in files.values():
        open(f, "w").close()
    vals = {k: str(v.get("default", "")) for k, v in action["inputs"].items()}
    vals["github-token"] = "ghs_test"
    vals.update(inputs)
    code = 0
    for i, st in enumerate(action["runs"]["steps"]):
        if step_ids is not None and i not in step_ids:
            continue
        env = dict(os.environ, RUNNER_TEMP=tmp, RUNNER_OS="Linux", RUNNER_ARCH="X64", GITHUB_OUTPUT=files["output"],
                   GITHUB_STEP_SUMMARY=files["summary"], GITHUB_PATH=files["path"], **(extra_env or {}))
        if path_first:
            env["PATH"] = path_first + os.pathsep + env["PATH"]
        for k, v in (st.get("env") or {}).items():
            env[k] = re.sub(r"\$\{\{\s*inputs\.([\w-]+)\s*\}\}", lambda m: vals[m.group(1)], str(v)).replace("${{ github.event_name }}", env.get("EVENT_NAME", "push"))
        r = subprocess.run(["bash", "-c", st["run"]], env=env, cwd=tmp, capture_output=True, text=True)
        sys.stdout.write("".join("        " + l + "\n" for l in (r.stdout + r.stderr).strip().splitlines()[-6:]))
        code = r.returncode
        if code != 0:
            break
    out = dict(l.split("=", 1) for l in open(files["output"]).read().splitlines() if "=" in l)
    return code, out, open(files["summary"]).read(), open(files["path"]).read().split(), tmp


# 1. the download step: the Linux CLI from the controller, checked against its header
code, _, _, paths, tmp = run_action({"url": URL, "token": pat, "test": "x"}, step_ids={0})
check("download: the Linux CLI with a matching checksum", code == 0 and paths and os.path.exists(os.path.join(paths[0], "spitfire")), code)

# a CLI for this machine stands in for it in the run step
bindir = tempfile.mkdtemp(prefix="sf-cli-")
os.symlink(os.environ["SPITFIRE_CLI"], os.path.join(bindir, "spitfire"))

# 2. a passing test
spec = lambda name, expr: {"name": name, "variables": {"base": os.environ["DOCS_TARGET_URL"]}, "options": {"gracefulStop": "2s"},
                           "scenarios": [{"name": "s", "executor": {"type": "constant-vus", "vus": 2, "duration": "4s"},
                                          "steps": [{"id": "items", "name": "Items", "request": {"url": "{{base}}/items"}}]}],
                           "thresholds": [{"metric": "req_duration", "expr": expr}]}
call("POST", "/tests", {"spec": spec("action pass", "p(95)<5000"), "description": ""}, tok)
call("POST", "/tests", {"spec": spec("action fail", "p(95)<0.001"), "description": ""}, tok)
code, out, summ, _, tmp = run_action({"url": URL, "token": pat, "test": "action pass"}, step_ids={1}, path_first=bindir)
check("passing test: exit 0, result passed", code == 0 and out.get("exit-code") == "0" and out.get("result") == "passed", (code, out))
check("passing test: summary JSON written", os.path.exists(os.path.join(tmp, "spitfire-summary.json")), out)
check("passing test: the job summary has the Markdown", "action pass" in summ or "|" in summ, summ[:200])

# 3. a failing threshold fails the step, and fail: false keeps it green
code, out, _, _, _ = run_action({"url": URL, "token": pat, "test": "action fail"}, step_ids={1}, path_first=bindir)
check("failing threshold: step fails with 99, result failed", code == 99 and out.get("result") == "failed", (code, out))
code, out, _, _, _ = run_action({"url": URL, "token": pat, "test": "action fail", "fail": "false"}, step_ids={1}, path_first=bindir)
check("fail: false: step passes, exit-code 99 recorded", code == 0 and out.get("exit-code") == "99", (code, out))

# 4. inputs reach the CLI: vars, runners, scale (an unknown test is an error, exit 1)
code, out, _, _, _ = run_action({"url": URL, "token": pat, "test": "no such test", "vars": "a=1\n b = 2 \n", "scale": "0.5"}, step_ids={1}, path_first=bindir)
check("unknown test: exit 1, result error", code == 1 and out.get("result") == "error", (code, out))

sys.exit(1 if fails else 0)
