# Generate CI Pipeline (GitHub Actions)

## Task
Generate a GitHub Actions CI workflow that runs on every push to `main` and on pull requests. This workflow should lint, type-check, and test the project.

## Input
You will receive the project document AND the `projectAnalysis` output from step 1.

## Requirements

### Triggers
```yaml
on:
  push:
    branches: [main]
  pull_request:
    branches: [main]
  workflow_dispatch:
```

### Job: build-and-test
1. **Checkout** code (`actions/checkout@v4`)
2. **Set up language** runtime (e.g., `actions/setup-python@v5` with version and pip cache)
3. **Install dependencies** from the detected package manager
4. **Lint** — run all lint commands from `lintCommands`
5. **Type check** — run `typeCheckCommand` if present
6. **Test with coverage** — run `testCommand` with coverage reporting
7. **Upload coverage** to Codecov (`codecov/codecov-action@v4`)

### Language-Specific Patterns

**Python:**
```yaml
- name: Set up Python 3.11
  uses: actions/setup-python@v5
  with:
    python-version: "3.11"
    cache: 'pip'

- name: Install dependencies
  run: |
    python -m pip install --upgrade pip
    pip install -e ".[dev]"
```

**Node.js:**
```yaml
- name: Set up Node.js 20
  uses: actions/setup-node@v4
  with:
    node-version: "20"
    cache: 'npm'

- name: Install dependencies
  run: npm ci
```

### Rules
- Use the exact commands from the project analysis — do NOT guess or modify.
- Each lint/check should be a separate step (so failures are visible per-step).
- Keep the workflow name simple: `CI` or `CI - Build and Test`.
- Do NOT include any deployment steps — that's the CD pipeline's job.
- Do NOT include Azure login or service principal references.

## Output Format

```json
{
  "ciPipeline": {
    "content": "name: CI\n\non:\n  push:\n    branches: [main]\n...",
    "filePath": ".github/workflows/ci.yml",
    "triggers": ["push:main", "pull_request:main", "workflow_dispatch"],
    "jobs": ["build-and-test"],
    "hasCoverage": true,
    "notes": [
      "Runs lint, type check, and tests on every PR",
      "Uploads coverage to Codecov"
    ]
  }
}
```

## Important
- The `content` field must be valid, complete YAML.
- Use `env:` block at top level for shared variables like `PYTHON_VERSION`.
- The workflow must pass without any secrets or external dependencies.
