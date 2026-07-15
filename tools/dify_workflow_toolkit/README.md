# dify-workflow-toolkit

A self-contained Python toolkit to **build, validate, deploy, and verify**
Dify workflow DSL files end-to-end over SSH.

Designed to be copy-pasted into another project / Claude session and
work out of the box. The companion `examples/health_consult_v2.py` is
a fully-working demo of the **LLM + code 6-layer safety-net** scene
classifier that was deployed in production and validated against 10/10
test cases.

## Why this exists

The Dify web UI does not expose a stable API for publishing a new
workflow version programmatically. If you have many workflows to manage
(or want to deploy from a script), the only reliable path is:

1. Construct the yml in code
2. SSH into the Dify host
3. Update the `workflows` table's `graph` column directly
4. Restart the api + worker containers so the new graph is picked up

This toolkit does steps 2-4 automatically, with a clean Python API
that hides Dify's verbose JSON shape.

## Install

```bash
cd tools/dify_workflow_toolkit
pip install -e .
```

Or just drop the `dify_workflow_toolkit/` directory into your project
and `import dify_workflow_toolkit` — the only runtime deps are
`PyYAML` and `paramiko` (plus `psycopg2-binary` inside the Dify api
container for the deploy step).

## Quickstart

### 1. Build a workflow in code

```python
from dify_workflow_toolkit import (
    Workflow, StartNode, LLMNode, CodeNode, EndNode, Variable,
)

wf = Workflow(
    name="my_classifier",
    description="classify user input into A/B/C",
)

wf.add(StartNode(
    id="4001", title="开始",
    variables=[Variable("text", "Text", type="paragraph")],
))

wf.add(LLMNode(
    id="4080", title="classify",
    system_prompt='Return JSON: {"label": "A|B|C"}',
    user_prompt="{{#4001.text#}}",
    json_mode=True,
))

wf.add(CodeNode(
    id="4002", title="parse",
    code=(
        "def main(llm_text: str = '', text: str = '') -> dict:\n"
        "    import json, re\n"
        "    m = re.search(r'\\{.*\\}', llm_text or '', re.DOTALL)\n"
        "    if m:\n"
        "        try:\n"
        "            return json.loads(m.group(0))\n"
        "        except Exception:\n"
        "            pass\n"
        "    return {'label': 'A', '_fallback': True}\n"
    ),
    variables=[{"variable": "llm_text", "value_selector": ["4080", "text"]}],
))

wf.add(EndNode(outputs=[{"variable": "output", "value_selector": ["4002", "label"]}]))

wf.connect("4001", "4080")
wf.connect("4080", "4002")
wf.connect("4002", "4099")

yml_text = wf.to_yaml()
```

### 2. Validate before deploying

```python
from dify_workflow_toolkit import validate_yaml
validate_yaml(yml_text)  # raises ValidationError on bad structure
```

### 3. Deploy to Dify over SSH

```python
import os
from dify_workflow_toolkit import SSHClient, Deployer

with SSHClient(
    "124.243.178.156",
    user="root",
    password=os.environ["DIFY_SSH_PASSWORD"],
) as ssh:
    deployer = Deployer(ssh)
    result = deployer.deploy(
        yml_text,
        app_id="d2623d9a-ac8e-40b6-9ba8-ded2f99f874a",
        restart=True,
        must_have_nodes=["4080", "4002", "4099"],
    )
print(result)
# DeploymentResult(app_id=..., rows_updated=1, restarted=True, verified=True, nodes=4)
```

The deployer will:
- install `psycopg2-binary` inside `docker-api-1` if missing
- push a deploy + verify script via SFTP + `docker cp` to `/tmp/`
- run an `UPDATE workflows SET graph = ...` against the published row
- restart `docker-api-1`, `docker-worker-1`, `docker-worker-beat-1`
- verify the deployed graph contains the required node ids

### 4. Run end-to-end test cases

```python
from dify_workflow_toolkit import SSHClient, Verifier, TestCase

cases = [
    TestCase(case_id="leg_pain", text="我腿疼",
             expected={"scene": "symptom", "scene_confidence": ">=0.7"}),
    TestCase(case_id="bone_density", text="T值-2.1",
             expected={"scene": "report", "scene_confidence": ">=0.7"}),
]

with SSHClient("124.243.178.156", user="root", password="...") as ssh:
    v = Verifier(ssh, default_endpoint="http://127.0.0.1:8013/api/health-consult/chat")
    report = v.run(cases)
print(report)
# VerificationReport 10/10 passed (100%)
```

## CLI

After `pip install -e .`:

```bash
# Validate
dify-workflow-toolkit validate my_classifier.yml

# Deploy
dify-workflow-toolkit deploy my_classifier.yml \
    --ssh-host 124.243.178.156 --ssh-user root \
    --ssh-password "$DIFY_SSH_PASSWORD" \
    --app-id d2623d9a-ac8e-40b6-9ba8-ded2f99f874a \
    --must-have 4080,4002,4099

# Verify (yml must have a 'tests:' block)
dify-workflow-toolkit verify my_classifier.yml \
    --ssh-host 124.243.178.156 --ssh-password "$DIFY_SSH_PASSWORD" \
    --endpoint http://127.0.0.1:8013/api/health-consult/chat

# Run inline code test (no LLM call)
dify-workflow-toolkit test-code my_classifier.yml \
    --text "我腿疼" --llm-text '{"scene":"symptom","confidence":0.9}'
```

## Working example: `examples/health_consult_v2.py`

This is the production-deployed scene classifier (LLM + code 6-layer
safety net) — re-implemented in 200 lines of clean Python instead of
1,200 lines of hand-rolled yml.

Run it directly:

```bash
cd tools/dify_workflow_toolkit
python examples/health_consult_v2.py build       # writes yml
python examples/health_consult_v2.py test-code   # 10/10 offline
python examples/health_consult_v2.py deploy \
    --ssh-host 124.243.178.156 --ssh-password "$DIFY_SSH_PASSWORD" \
    --app-id d2623d9a-ac8e-40b6-9ba8-ded2f99f874a
python examples/health_consult_v2.py verify \
    --ssh-host 124.243.178.156 --ssh-password "$DIFY_SSH_PASSWORD" \
    --endpoint http://127.0.0.1:8013/api/health-consult/chat
```

The 6-layer fallback logic in `CODE_SAFETY_NET`:

1. **Answers priority** — if a questionnaire answer has a known tag, use its scene
2. **LLM high-confidence** — if LLM gave a clear answer (conf ≥ 0.5), trust it
3. **Image-only** — `text="" + has_image=true` → report
4. **Empty** — `text="" + no image` → symptom (default)
5. **LLM + keyword confirm** — if LLM hint matches a keyword, use it
6. **Pure keyword scoring** — score each scene's keywords, pick the best
7. **Danger signal override** — match emergency keywords → urgent
8. **Final fallback** — respect LLM hint with low conf, else default to symptom

## Tests

```bash
cd tools/dify_workflow_toolkit
pip install -e ".[dev]"
pytest
```

10 tests covering the builder API + 1 smoke-test running the example's
10 production test cases offline.

## Architecture

```
┌──────────────────────────────────────────────────────────────────┐
│  Caller script / CLI                                             │
│      │                                                            │
│      ├── builder.Workflow  →  to_yaml()                          │
│      ├── yml_validator.validate_yaml()                            │
│      ├── deployer.Deployer  →  ssh + DB update + restart          │
│      │      └── ssh_client.SSHClient (paramiko)                   │
│      │           └── docker exec docker-api-1 ...                 │
│      │                └── psycopg2 → UPDATE workflows SET graph  │
│      └── verifier.Verifier  →  curl → POST /api/.../chat          │
└──────────────────────────────────────────────────────────────────┘
```

## Why not just edit the yml by hand?

Because the yml is 1,200+ lines with deeply nested metadata, and a
single typo (e.g. wrong `provider` field name) silently breaks the
workflow in Dify. The builder catches these errors at construction
time, and the validator catches them at deploy time.

## Why not use the Dify web UI's "Import DSL" feature?

It does work, but:
- Doesn't update the *published* version (worker reads published, not draft)
- Requires you to manually click "Publish" after each import
- Doesn't restart worker, so changes don't take effect for in-flight runs
- Doesn't fit into CI/CD

This toolkit does all four, scripted.

## License

MIT.
