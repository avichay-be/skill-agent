# Generate Dockerfile

## Task
Generate a production-ready, multi-stage Dockerfile based on the project analysis from the previous step.

## Input
You will receive the project document AND the `projectAnalysis` output from step 1, including language, framework, dependencies, port, and system dependencies.

## Requirements

### Multi-stage Build
1. **Builder stage**: Install build dependencies and compile/install packages
2. **Runtime stage**: Copy only what's needed for runtime — minimal image size

### Security Best Practices
- Use `-slim` base images (e.g., `python:3.11-slim`, `node:20-slim`)
- Create and run as non-root user (`appuser`, uid 1000)
- `chown` application files to the non-root user
- No secrets in the Dockerfile — use env vars at runtime

### Health Check
- Add `HEALTHCHECK` instruction using the detected health endpoint
- Interval: 30s, Timeout: 10s, Start period: 40s, Retries: 3

### Language-Specific Patterns

**Python:**
```dockerfile
FROM python:${version}-slim as builder
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends ${extraBuildDeps} && rm -rf /var/lib/apt/lists/*
COPY requirements.txt ./
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"
RUN pip install --no-cache-dir --upgrade pip && pip install --no-cache-dir -r requirements.txt

FROM python:${version}-slim
WORKDIR /app
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"
COPY app ./app
# ... non-root user, EXPOSE, HEALTHCHECK, CMD
```

**Node.js:**
```dockerfile
FROM node:${version}-slim as builder
WORKDIR /app
COPY package*.json ./
RUN npm ci --only=production

FROM node:${version}-slim
WORKDIR /app
COPY --from=builder /app/node_modules ./node_modules
COPY . .
# ... non-root user, EXPOSE, HEALTHCHECK, CMD
```

### Additional Rules
- Copy dependency files BEFORE application code (Docker layer caching)
- Use `--no-cache-dir` for pip, `npm ci` instead of `npm install`
- Set `PYTHONUNBUFFERED=1` for Python
- Set `NODE_ENV=production` for Node.js
- Include any extra runtime dependencies (e.g., `git` if needed)
- If the project has a `skills-library/` or similar data directory, COPY it

## Output Format

```json
{
  "dockerfile": {
    "content": "# Full Dockerfile content here\nFROM python:3.11-slim as builder\n...",
    "isMultiStage": true,
    "baseImage": "python:3.11-slim",
    "exposedPort": 8000,
    "hasHealthCheck": true,
    "notes": [
      "Uses multi-stage build to reduce image size",
      "Runs as non-root user for security"
    ]
  }
}
```

## Important
- The `content` field must contain the COMPLETE, ready-to-use Dockerfile.
- No placeholder values — use actual values from the project analysis.
- The Dockerfile must work as-is when saved to the project root.
