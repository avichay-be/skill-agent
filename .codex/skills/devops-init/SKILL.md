---
name: devops-init
description: Bootstrap or repair end-to-end DevOps for a repository that should build with Docker, run CI in GitHub Actions, deploy to Azure Container Apps, and stay verifiable through Azure CLI. Use when the user wants CI/CD created from scratch, production deployment fixed, Container Apps resources created if missing, or ongoing audit of GitHub Actions and Azure deployment health.
---

# Devops Init

## Overview

Use this skill when the user wants a repository taken from "no deployment story" to "running in production" on Azure Container Apps, or when an existing pipeline needs to be audited and repaired.

This skill has two modes:

- **Bootstrap mode**: create the Docker/runtime contract, CI workflow, CD workflow, Azure resources, and deployment wiring from scratch.
- **Audit mode**: inspect the existing GitHub Actions and Azure resources, find the failing link, and repair the minimum necessary surface.

If the repo already contains Azure Container Apps assets, preserve and extend them instead of replacing them with a different deployment model.

## Trigger Examples

- "Create full DevOps for this repo and deploy it to Azure Container Apps."
- "Set up Docker, GitHub Actions, PR flow, merge to main, and production deploy."
- "If the container app does not exist, create everything from scratch."
- "Check CI and CD using Azure CLI and fix whatever is broken."
- "Make this the init skill for first deploy, then use it for CI/CD health checks."

## Workflow

### 1. Choose mode

Use **bootstrap mode** if any of these are missing or clearly unusable:

- Container runtime contract: `Dockerfile`, startup command, health endpoint
- CI workflow: build/test workflow in `.github/workflows/`
- CD workflow: deploy workflow for Azure Container Apps
- Azure resource definition or CLI creation path
- Running production target

Use **audit mode** if the stack already exists and the user wants verification, troubleshooting, or repair.

### 2. Build context first

Before editing anything:

- Inspect the repository for runtime and deploy assets.
- Identify the actual application start command and health endpoint.
- Identify the real test command instead of inventing one.
- Check whether the repo already uses Bicep, shell scripts, or existing GitHub workflows.
- If working in this repository, read [repo-patterns.md](./references/repo-patterns.md) before changing deploy assets.

Prefer current repo conventions over generic templates.

### 3. Bootstrap mode

When bootstrapping, work in this order:

1. **Runtime contract**
Ensure the app has:
- a working `Dockerfile`
- a stable container entrypoint
- a health endpoint used by orchestration
- explicit runtime environment variables where needed

2. **CI**
Create or repair GitHub Actions so pull requests and main-branch changes run:
- dependency install
- lint/format checks if the repo already uses them
- unit/integration tests that are safe in CI
- optional Docker build smoke test when container deployment is the production path

3. **CD**
Create or repair deployment automation so it:
- authenticates to Azure with OIDC where possible
- builds and pushes the container image to ACR
- creates missing Azure Container Apps dependencies if the user asked for full bootstrap
- updates the Container App image, secrets, and env vars
- verifies deployment health after rollout

4. **Azure resource creation**
If Azure resources are missing and the user wants full setup, create or update:
- resource group
- Azure Container Registry
- Container Apps environment
- Container App
- required role assignments and registry access
- any secret wiring required for runtime

Prefer infrastructure already present in the repo, especially Bicep, over inventing one-off imperative scripts. Use imperative `az` creation only when the repo has no infrastructure definition or the user explicitly wants CLI-first setup.

5. **GitHub repo wiring**
If you have access, use `gh` and GitHub Actions to wire or verify:
- workflows
- environments
- required secrets and variables
- PR checks
- deploy trigger strategy

If you cannot set a secret automatically, stop with the exact secret names and values the user must provide.

6. **Delivery**
Finish by:
- running the local test/build checks you changed
- validating workflow syntax as far as practical
- confirming Azure deploy health with CLI checks
- creating a PR and merging to `main` only if the user asked for that step

### 4. Audit mode

When the pipeline already exists, do not rebuild it blindly. Inspect first:

1. **GitHub side**
- workflow files in `.github/workflows/`
- latest workflow runs
- branch protection / required checks if relevant
- whether deploy triggers are disabled, manual-only, or failing

2. **Azure side**
- `az account show`
- `az group show`
- `az acr show`
- `az containerapp show`
- `az containerapp revision list`
- `az containerapp logs show`
- `az containerapp secret list` or the equivalent non-destructive inspection path

3. **Failure classification**
Classify the problem before editing:
- build failure
- test failure
- image push / registry auth failure
- OIDC / RBAC failure
- bad runtime env var or secret
- health check mismatch
- ingress / auth mismatch
- stale image / revision rollout issue

Then repair the narrowest failing surface and re-verify end to end.

## Azure CLI-first Checks

Use Azure CLI as the source of truth for deployment health. Favor commands like:

```bash
az account show
az group show --name <resource-group>
az acr show --name <acr-name> --resource-group <resource-group>
az containerapp show --name <app-name> --resource-group <resource-group>
az containerapp revision list --name <app-name> --resource-group <resource-group>
az containerapp logs show --name <app-name> --resource-group <resource-group> --follow
```

If the user wants "check CI/CD", inspect both:
- GitHub workflow state and recent runs
- Azure runtime state and current active revision

Do not declare success from workflow completion alone.

## Guardrails

- Prefer OIDC over long-lived Azure service principal secrets.
- Reuse existing naming, resource groups, and workflow conventions when present.
- Do not replace a working Bicep-based setup with ad hoc shell scripts.
- Do not merge to `main` without the user's intent.
- If a missing credential or Azure permission blocks progress, surface the exact missing item and continue with everything else that is still actionable.

## Output Expectations

A successful run of this skill should leave the repo in one of these states:

- **Bootstrap complete**: repo has Docker + CI + CD + Azure target wired, and production is reachable or ready for the last missing secret/approval.
- **Audit complete**: the broken part is identified, patched, and re-verified with GitHub/Azure evidence.

When you finish, summarize:
- what was created or repaired
- what was verified locally
- what was verified in GitHub Actions
- what was verified in Azure
- any remaining manual secret, approval, or RBAC step
