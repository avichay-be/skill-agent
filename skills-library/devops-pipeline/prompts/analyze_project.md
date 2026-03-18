# Analyze Project for DevOps Pipeline

## Task
Analyze the provided project description/codebase information and determine all technical details needed to create a complete DevOps pipeline. This is the first step — all downstream skills depend on your analysis.

## Input
You will receive a document describing a software project. This may include:
- File listings (directory structure)
- Package manifests (pyproject.toml, package.json, go.mod, pom.xml, etc.)
- Existing Dockerfiles or CI/CD configs
- README or documentation fragments
- Free-text project description

## Analysis Rules

1. **Language Detection**: Identify the primary language and version from:
   - `pyproject.toml` / `setup.py` → Python
   - `package.json` → Node.js
   - `go.mod` → Go
   - `pom.xml` / `build.gradle` → Java
   - `Cargo.toml` → Rust

2. **Framework Detection**: Identify from imports/dependencies:
   - `fastapi`, `flask`, `django` → Python web
   - `express`, `nestjs`, `next` → Node web
   - `gin`, `echo`, `fiber` → Go web
   - `spring-boot` → Java web

3. **Entry Point**: Find the main application file:
   - Python: look for `app/main.py`, `main.py`, `manage.py`, or uvicorn/gunicorn target
   - Node: look at `"main"` or `"scripts.start"` in package.json
   - Go: look for `cmd/main.go` or `main.go`

4. **Test & Lint Commands**: Identify from project config:
   - Python: `pytest`, `ruff check .`, `ruff format --check .`, `mypy`
   - Node: `npm test`, `eslint .`, `tsc --noEmit`
   - Go: `go test ./...`, `golangci-lint run`

5. **Init vs Check Mode**: Determine based on:
   - `isInitMode: true` — No existing Docker/CI/CD files found, or user explicitly says "create from scratch"
   - `isInitMode: false` — Existing pipeline files found, user wants to check/update

6. **Environment Variables**: List required env vars from:
   - `.env` or `.env.example` files
   - Config/settings files referencing `os.environ` or `process.env`
   - Known API keys for detected services (anthropic, openai, google, etc.)

7. **System Dependencies**: Identify extra system packages:
   - `git` — if project uses GitPython or git operations
   - `gcc` / build-essential — if native extensions needed
   - `libpq-dev` — if PostgreSQL client needed

## Output Format

Return a JSON object with this exact structure:
```json
{
  "projectAnalysis": {
    "language": "python",
    "languageVersion": "3.11",
    "framework": "fastapi",
    "packageManager": "pip",
    "entryPoint": "app/main.py",
    "startCommand": "python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --log-level info",
    "testCommand": "pytest --cov=app --cov-fail-under=45",
    "lintCommands": ["ruff check .", "ruff format --check ."],
    "typeCheckCommand": "mypy app",
    "dependenciesFile": "requirements.txt",
    "hasDocker": false,
    "hasCi": false,
    "hasCd": false,
    "port": 8000,
    "healthEndpoint": "/health",
    "extraBuildDeps": ["gcc", "git"],
    "extraRuntimeDeps": ["git"],
    "envVars": ["ANTHROPIC_API_KEY", "OPENAI_API_KEY", "GOOGLE_API_KEY"],
    "isInitMode": true
  }
}
```

## Important
- Be precise about versions — use exact version from project config, not assumptions.
- If no health endpoint is found, default to `/health`.
- If no port is specified, use 8000 for Python/Go, 3000 for Node.
- List ALL env vars found, including optional ones.
- `startCommand` must be production-ready (not dev mode with `--reload`).
