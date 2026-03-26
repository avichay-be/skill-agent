# Repository Patterns

Load this file when using `$devops-init` in the `skill-agent` repository or another repo cloned from the same deployment pattern.

## Existing deploy assets in this repo

- `Dockerfile`
- `startup.sh`
- `.github/workflows/ci.yml`
- `.github/workflows/container-apps-deploy.yml`
- `.github/workflows/azure-deploy.yml`
- `infra/container-apps.bicep`
- `infra/main.bicep`
- `scripts/deploy-container-apps.sh`
- `scripts/setup-azure.sh`

## Current production direction

This repo is already oriented toward **Azure Container Apps**, not App Service.

The main deploy workflow is:
- `.github/workflows/container-apps-deploy.yml`

The important current conventions are:
- OIDC-based Azure login via `azure/login@v2`
- ACR login with `az acr login`
- deploy target is a Container App
- deployment verification allows health endpoint responses of `200` or `401`

That last detail matters because this repo has used protected ingress, so a `401` can still mean the app is alive.

## Current Azure naming in the repo

The checked-in workflow currently uses:

- resource group: `skill-agent-rg`
- container app: `skill-agent-app`
- image name: `skill-agent`
- ACR name variable: `skillagentprodacr`

Do not rename these unless the user explicitly asks for new naming.

## Current GitHub secret names in the repo

The deploy workflow expects Azure OIDC secrets:

- `SKILLAGENTAPP_AZURE_CLIENT_ID`
- `SKILLAGENTAPP_AZURE_TENANT_ID`
- `SKILLAGENTAPP_AZURE_SUBSCRIPTION_ID`

The deploy workflow may also use app/runtime secrets:

- `ANTHROPIC_API_KEY`
- `OPENAI_API_KEY`
- `GOOGLE_API_KEY`
- `GITHUB_REPO_URL`

If the user wants full bootstrap, verify whether these already exist before asking for new ones.

## Current runtime env shape

The deploy workflow currently sets:

- `ENVIRONMENT=production`
- `SKILLS_BASE_PATH=skills-library`
- `APP_NAME=Skill Agent`
- `LOG_LEVEL=INFO`

Preserve existing runtime env vars unless the code or deployment bug proves they are wrong.

## Important repo-specific cautions

1. The push trigger for production deploy is currently disabled in `.github/workflows/container-apps-deploy.yml`.
   Bootstrap work may need to decide whether to keep manual deploy or re-enable push-to-main deploy.

2. This repo has local, uncommitted changes frequently.
   Do not revert unrelated work while fixing CI/CD.

3. There is already historical Azure documentation under `.claude/04-DEPLOYMENT.md`, `.claude/05-QUICKSTART-AZURE.md`, and `.claude/06-CONTAINER-APPS-DEPLOYMENT.md`.
   Use those files as context, but prefer the checked-in workflow and infra files as the source of truth.

## Recommended inspection order in this repo

1. `Dockerfile`
2. `app/main.py` health endpoint
3. `.github/workflows/ci.yml`
4. `.github/workflows/container-apps-deploy.yml`
5. `infra/container-apps.bicep`
6. `scripts/deploy-container-apps.sh`
7. recent GitHub workflow runs
8. Azure Container Apps state via `az`

## Typical repair targets for this repo

- registry credentials drift between ACR and Container App
- disabled deploy trigger
- OIDC auth or RBAC mismatch
- health check expecting `200` when protected ingress returns `401`
- stale env var or secret sync during deploy
- app commit deployed successfully but runtime content still stale because schema/config load failed
