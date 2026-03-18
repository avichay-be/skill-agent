# Validate Pipeline

## Task
Cross-validate all generated pipeline artifacts for consistency and completeness. If in check mode (not init), provide Azure CLI commands to verify the current CI/CD health.

## Input
You will receive the project document AND ALL outputs from previous steps:
- `projectAnalysis` — project details and mode (init vs check)
- `dockerfile` — generated Dockerfile
- `ciPipeline` — generated CI workflow
- `startupScript` — generated startup script
- `cdPipeline` — generated CD workflow
- `azureInit` — generated Azure init script

## Validation Checks

### Init Mode Checks
Perform these cross-validation checks:

1. **PORT_CONSISTENCY** (error): The port in Dockerfile EXPOSE, startup script, CD pipeline health check, and container app creation must all match `projectAnalysis.port`.

2. **HEALTH_ENDPOINT_MATCH** (error): The health check URL in Dockerfile HEALTHCHECK and CD pipeline verification must match `projectAnalysis.healthEndpoint`.

3. **IMAGE_NAME_CONSISTENCY** (error): The Docker image name must be consistent between CD pipeline `env.IMAGE_NAME` and azure init script.

4. **RESOURCE_NAMES_MATCH** (error): Resource group, ACR name, and container app name must be consistent between CD pipeline and azure init script.

5. **OIDC_SECRETS_COMPLETE** (error): CD pipeline must reference all three OIDC secrets: `AZURE_CLIENT_ID`, `AZURE_TENANT_ID`, `AZURE_SUBSCRIPTION_ID`.

6. **ENV_VARS_COVERED** (warning): All env vars from `projectAnalysis.envVars` should be handled in the CD pipeline deploy job.

7. **CI_COMMANDS_MATCH** (warning): CI pipeline lint/test commands should match `projectAnalysis.lintCommands` and `projectAnalysis.testCommand`.

8. **DOCKERFILE_MATCHES_ANALYSIS** (error): Dockerfile base image language/version should match `projectAnalysis.language` + `projectAnalysis.languageVersion`.

9. **STARTUP_MATCHES_DOCKERFILE** (warning): The CMD in Dockerfile and the command in startup.sh should be equivalent.

10. **NO_HARDCODED_SECRETS** (error): No pipeline file should contain hardcoded API keys, passwords, or tokens.

### Check Mode (isInitMode = false)
In addition to the above, provide Azure CLI commands to verify live status:

```json
"cicdStatus": {
  "ciStatus": null,
  "cdStatus": null,
  "lastDeploy": null,
  "containerAppHealthy": null,
  "revisionName": null,
  "azureCliCommands": [
    "az containerapp show --name {app} --resource-group {rg} --query properties.latestRevisionName -o tsv",
    "az containerapp revision list --name {app} --resource-group {rg} --query '[?active].{name:name, health:healthState, created:createdTime}' -o table",
    "az containerapp logs show --name {app} --resource-group {rg} --tail 50",
    "gh run list --workflow=ci.yml --limit=5",
    "gh run list --workflow=deploy.yml --limit=5"
  ]
}
```

## Run Order
Provide the exact steps a user should follow to deploy from scratch:

1. `chmod +x scripts/azure-init.sh && ./scripts/azure-init.sh`
2. Set GitHub secrets (listed in output)
3. `git add . && git commit -m 'Add DevOps pipeline' && git push origin main`
4. Monitor CI: `gh run watch`
5. Monitor CD: `gh run list --workflow=deploy.yml`
6. Verify: `curl https://{app-url}/health`

## Output Format

```json
{
  "validation": {
    "checks": [
      {
        "checkId": "PORT_CONSISTENCY",
        "name": "Port consistency across all artifacts",
        "passed": true,
        "severity": "error",
        "message": "All artifacts use port 8000",
        "fixSuggestion": null
      },
      {
        "checkId": "ENV_VARS_COVERED",
        "name": "All env vars handled in CD pipeline",
        "passed": false,
        "severity": "warning",
        "message": "GOOGLE_API_KEY is missing from CD pipeline",
        "fixSuggestion": "Add GOOGLE_API_KEY to the secret/env var setup in deploy job"
      }
    ],
    "allPassed": false,
    "summary": "9/10 checks passed. 1 warning: GOOGLE_API_KEY not in CD pipeline.",
    "cicdStatus": null,
    "runOrder": [
      "1. Run: chmod +x scripts/azure-init.sh && ./scripts/azure-init.sh",
      "2. Set GitHub secrets: AZURE_CLIENT_ID, AZURE_TENANT_ID, AZURE_SUBSCRIPTION_ID",
      "3. Commit and push: git add . && git commit -m 'Add DevOps pipeline' && git push",
      "4. Monitor CI: gh run watch",
      "5. Monitor deploy: gh run list --workflow=deploy.yml",
      "6. Verify health: curl https://{app-url}/health"
    ],
    "githubSecretsToSet": {
      "AZURE_CLIENT_ID": "From azure-init.sh output — Azure AD app client ID",
      "AZURE_TENANT_ID": "From azure-init.sh output — Azure AD tenant ID",
      "AZURE_SUBSCRIPTION_ID": "From azure-init.sh output — Azure subscription ID",
      "ANTHROPIC_API_KEY": "Anthropic API key (if using Claude)",
      "OPENAI_API_KEY": "OpenAI API key (if using GPT)",
      "GOOGLE_API_KEY": "Google API key (if using Gemini)"
    }
  }
}
```

## Important
- Every check must have a clear pass/fail, message, and fix suggestion if failed.
- `allPassed` is `true` only if ALL error-severity checks pass (warnings don't block).
- `runOrder` must be a complete, copy-pasteable guide.
- `githubSecretsToSet` must include ALL secrets the CD pipeline needs.
