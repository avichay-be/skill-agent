# Generate Startup Script

## Task
Generate a `startup.sh` script for the application. This is used by Azure App Service and as an alternative entrypoint for containers.

## Input
You will receive the project document AND the `projectAnalysis` output from step 1.

## Requirements

### Script Structure
```bash
#!/bin/bash
# Startup script for {framework} application
{start_command}
```

### Language-Specific Patterns

**Python (FastAPI/Flask):**
```bash
#!/bin/bash
# Option 1: uvicorn (simple, good for moderate traffic)
python -m uvicorn app.main:app \
    --host 0.0.0.0 \
    --port 8000 \
    --log-level info

# Option 2: gunicorn with uvicorn workers (production, high traffic)
# python -m gunicorn app.main:app \
#     --workers 4 \
#     --worker-class uvicorn.workers.UvicornWorker \
#     --bind 0.0.0.0:8000 \
#     --timeout 120 \
#     --access-logfile - \
#     --error-logfile -
```

**Node.js:**
```bash
#!/bin/bash
node dist/index.js
# or: npm start
```

### Rules
- Always include both simple and production options for Python (gunicorn commented out).
- Use `--host 0.0.0.0` to bind to all interfaces.
- Use the port from project analysis.
- Log level should be `info` for production.
- No `--reload` flag (that's for dev only).

## Output Format

```json
{
  "startupScript": {
    "content": "#!/bin/bash\n# Startup script...\npython -m uvicorn ...",
    "filePath": "startup.sh",
    "usesGunicorn": false,
    "workerCount": 1,
    "notes": ["Includes commented gunicorn option for high-traffic deployments"]
  }
}
```
