"""Pydantic output models for DevOps Pipeline Generator skill."""

from typing import Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field

# ─── Step 1: analyze_project output ──────────────────────────────


class Dependency(BaseModel):
    """A project dependency."""

    model_config = ConfigDict(populate_by_name=True)

    name: str = Field(..., description="Package name")
    version: Optional[str] = Field(None, description="Version constraint")
    dev_only: bool = Field(False, alias="devOnly", description="Dev dependency only")


class ProjectAnalysis(BaseModel):
    """Output of project analysis step."""

    model_config = ConfigDict(populate_by_name=True)

    language: str = Field(..., description="Primary language: python, node, go, java, etc.")
    language_version: str = Field(..., alias="languageVersion", description="e.g. '3.11', '20'")
    framework: str = Field(..., description="Web framework: fastapi, express, gin, spring, etc.")
    package_manager: str = Field(
        ..., alias="packageManager", description="pip, npm, yarn, go mod, maven, etc."
    )
    entry_point: str = Field(
        ..., alias="entryPoint", description="Main entry file: app/main.py, src/index.ts, etc."
    )
    start_command: str = Field(
        ...,
        alias="startCommand",
        description="Command to start the app: python -m uvicorn app.main:app",
    )
    test_command: str = Field(
        ..., alias="testCommand", description="Command to run tests: pytest, npm test, etc."
    )
    lint_commands: List[str] = Field(
        default_factory=list,
        alias="lintCommands",
        description="Lint/format commands: ruff check ., eslint ., etc.",
    )
    type_check_command: Optional[str] = Field(
        None, alias="typeCheckCommand", description="Type check command: mypy app, tsc --noEmit"
    )
    dependencies_file: str = Field(
        ...,
        alias="dependenciesFile",
        description="Dependencies file: requirements.txt, package.json, go.mod",
    )
    has_docker: bool = Field(False, alias="hasDocker", description="Dockerfile already exists")
    has_ci: bool = Field(False, alias="hasCi", description="CI workflow already exists")
    has_cd: bool = Field(False, alias="hasCd", description="CD workflow already exists")
    port: int = Field(8000, description="Application port")
    health_endpoint: str = Field("/health", alias="healthEndpoint", description="Health check path")
    extra_build_deps: List[str] = Field(
        default_factory=list,
        alias="extraBuildDeps",
        description="Extra system packages needed: git, gcc, etc.",
    )
    extra_runtime_deps: List[str] = Field(
        default_factory=list,
        alias="extraRuntimeDeps",
        description="Extra runtime system packages",
    )
    env_vars: List[str] = Field(
        default_factory=list,
        alias="envVars",
        description="Required env vars: API keys, DB URLs, etc.",
    )
    is_init_mode: bool = Field(
        True,
        alias="isInitMode",
        description="True if pipeline should be created from scratch, false if checking existing",
    )


# ─── Step 2a: generate_dockerfile output ─────────────────────────


class DockerfileOutput(BaseModel):
    """Generated Dockerfile."""

    model_config = ConfigDict(populate_by_name=True)

    content: str = Field(..., description="Full Dockerfile content")
    is_multi_stage: bool = Field(True, alias="isMultiStage")
    base_image: str = Field(..., alias="baseImage", description="e.g. python:3.11-slim")
    exposed_port: int = Field(..., alias="exposedPort")
    has_health_check: bool = Field(True, alias="hasHealthCheck")
    notes: List[str] = Field(default_factory=list, description="Explanatory notes")


# ─── Step 2b: generate_ci_pipeline output ────────────────────────


class CiPipelineOutput(BaseModel):
    """Generated CI pipeline (GitHub Actions)."""

    model_config = ConfigDict(populate_by_name=True)

    content: str = Field(..., description="Full GitHub Actions CI workflow YAML")
    file_path: str = Field(
        ".github/workflows/ci.yml",
        alias="filePath",
        description="Target file path in repo",
    )
    triggers: List[str] = Field(
        default_factory=list, description="Trigger events: push, pull_request"
    )
    jobs: List[str] = Field(
        default_factory=list, description="Job names: build-and-test, lint, etc."
    )
    has_coverage: bool = Field(True, alias="hasCoverage")
    notes: List[str] = Field(default_factory=list)


# ─── Step 2c: generate_startup_script output ─────────────────────


class StartupScriptOutput(BaseModel):
    """Generated startup script."""

    model_config = ConfigDict(populate_by_name=True)

    content: str = Field(..., description="Full startup.sh script content")
    file_path: str = Field("startup.sh", alias="filePath")
    uses_gunicorn: bool = Field(False, alias="usesGunicorn")
    worker_count: int = Field(1, alias="workerCount")
    notes: List[str] = Field(default_factory=list)


# ─── Step 3a: generate_cd_pipeline output ────────────────────────


class SecretDefinition(BaseModel):
    """A GitHub Actions secret needed for deployment."""

    model_config = ConfigDict(populate_by_name=True)

    name: str = Field(..., description="Secret name: AZURE_CLIENT_ID, etc.")
    description: str = Field(..., description="What this secret is for")
    required: bool = Field(True)


class CdPipelineOutput(BaseModel):
    """Generated CD pipeline (GitHub Actions → Azure Container Apps)."""

    model_config = ConfigDict(populate_by_name=True)

    content: str = Field(..., description="Full GitHub Actions CD workflow YAML")
    file_path: str = Field(
        ".github/workflows/deploy.yml",
        alias="filePath",
        description="Target file path in repo",
    )
    deploy_target: str = Field(
        "azure-container-apps",
        alias="deployTarget",
        description="Deployment target platform",
    )
    uses_oidc: bool = Field(True, alias="usesOidc", description="Uses OIDC federated identity")
    required_secrets: List[SecretDefinition] = Field(default_factory=list, alias="requiredSecrets")
    has_health_check: bool = Field(True, alias="hasHealthCheck")
    has_rollback: bool = Field(False, alias="hasRollback")
    notes: List[str] = Field(default_factory=list)


# ─── Step 3b: generate_azure_init output ─────────────────────────


class AzureResource(BaseModel):
    """An Azure resource to create."""

    model_config = ConfigDict(populate_by_name=True)

    resource_type: str = Field(
        ..., alias="resourceType", description="resource-group, acr, container-app, etc."
    )
    name: str = Field(..., description="Resource name")
    cli_command: str = Field(..., alias="cliCommand", description="az CLI command to create it")


class AzureInitOutput(BaseModel):
    """Generated Azure init script."""

    model_config = ConfigDict(populate_by_name=True)

    content: str = Field(
        ..., description="Full bash script: creates resource group, ACR, container app"
    )
    file_path: str = Field("scripts/azure-init.sh", alias="filePath")
    resources: List[AzureResource] = Field(
        default_factory=list, description="Azure resources that will be created"
    )
    resource_group: str = Field(..., alias="resourceGroup")
    acr_name: str = Field(..., alias="acrName", description="Azure Container Registry name")
    container_app_name: str = Field(..., alias="containerAppName")
    location: str = Field("westeurope", description="Azure region")
    oidc_setup_commands: List[str] = Field(
        default_factory=list,
        alias="oidcSetupCommands",
        description="Commands to set up OIDC/federated identity for GitHub Actions",
    )
    notes: List[str] = Field(default_factory=list)


# ─── Step 4: validate_pipeline output ────────────────────────────


class CheckResult(BaseModel):
    """A single validation check result."""

    model_config = ConfigDict(populate_by_name=True)

    check_id: str = Field(..., alias="checkId")
    name: str
    passed: bool
    severity: str = Field("error", description="error, warning, info")
    message: Optional[str] = None
    fix_suggestion: Optional[str] = Field(None, alias="fixSuggestion")


class CiCdStatus(BaseModel):
    """Current CI/CD health status (for check mode)."""

    model_config = ConfigDict(populate_by_name=True)

    ci_status: Optional[str] = Field(
        None, alias="ciStatus", description="passing, failing, not_found"
    )
    cd_status: Optional[str] = Field(None, alias="cdStatus")
    last_deploy: Optional[str] = Field(
        None, alias="lastDeploy", description="ISO timestamp of last deploy"
    )
    container_app_healthy: Optional[bool] = Field(None, alias="containerAppHealthy")
    revision_name: Optional[str] = Field(None, alias="revisionName")
    azure_cli_commands: List[str] = Field(
        default_factory=list,
        alias="azureCliCommands",
        description="Azure CLI commands to check status",
    )


class ValidationOutput(BaseModel):
    """Output of the validation step."""

    model_config = ConfigDict(populate_by_name=True)

    checks: List[CheckResult] = Field(default_factory=list)
    all_passed: bool = Field(False, alias="allPassed")
    summary: str = Field(..., description="Human-readable summary of validation results")
    cicd_status: Optional[CiCdStatus] = Field(
        None, alias="cicdStatus", description="Populated in check mode (not init)"
    )
    run_order: List[str] = Field(
        default_factory=list,
        alias="runOrder",
        description="Ordered list of steps to execute the pipeline",
    )
    github_secrets_to_set: Dict[str, str] = Field(
        default_factory=dict,
        alias="githubSecretsToSet",
        description="Map of secret name → description for GitHub repo setup",
    )


# ─── Top-level result ────────────────────────────────────────────


class DevopsPipelineResult(BaseModel):
    """Top-level output model aggregating all sub-skill results."""

    model_config = ConfigDict(populate_by_name=True)

    project_analysis: ProjectAnalysis = Field(..., alias="projectAnalysis")
    dockerfile: DockerfileOutput = Field(...)
    ci_pipeline: CiPipelineOutput = Field(..., alias="ciPipeline")
    startup_script: StartupScriptOutput = Field(..., alias="startupScript")
    cd_pipeline: CdPipelineOutput = Field(..., alias="cdPipeline")
    azure_init: AzureInitOutput = Field(..., alias="azureInit")
    validation: ValidationOutput = Field(...)
