# Patterns
<!-- CONTRACT: This file accumulates learned patterns across sessions. Append only. -->

## Architecture Patterns
- **Shared execution utils:** Extract duplicated logic into `app/services/execution_utils.py` (merge, validate, execute_single_skill)
- **Middleware placement:** Custom middleware classes belong in `app/core/middleware.py`, not in main.py
- **Request ID propagation:** Use `contextvars.ContextVar` for request ID, add via middleware, read in logging filter
- **Singleton consistency:** Use module-level global + getter for simple singletons; __new__ + _lock only when reset() needed (SkillRegistry)
- **Dead code detection:** CI/CD subagent (cicd.py, github_client.py) is unreachable - no routes, no production imports

## Code Conventions
- Use Python 3.11+ built-in generics: `dict[str, Any]` not `Dict[str, Any]`, `X | None` not `Optional[X]`
- Use `list[str]` not `List[str]`, `tuple[str, int]` not `Tuple[str, int]`
- Structured JSON logging in production, human-readable in development

## Common Gotchas
- **SECURITY [FIXED]**: CORS wildcard `allow_origins=["*"]` - now uses ALLOWED_ORIGINS env var
- **SECURITY [FIXED]**: No rate limiting - now uses slowapi with 10/min on all execute endpoints
- **SECURITY [FIXED]**: No request timeouts - now uses TimeoutMiddleware with REQUEST_TIMEOUT_SECONDS
- **SECURITY [FIXED]**: Rate limiting ignored X-Forwarded-For - now uses get_client_ip() function
- **SECURITY [FIXED]**: Exception handler leaked internal details - now sanitizes in production (debug=False)
- **IMPORT**: Avoid circular imports between main.py and route files - use separate module (rate_limiter.py)
- **SLOWAPI**: Requires parameter named `request` (not `http_request`) for rate limit decorator to work
- **TESTING**: FastAPI TestClient requires `raise_server_exceptions=False` to test exception handlers
- **DEPRECATION [FIXED]**: datetime.utcnow() deprecated in Python 3.12 - replaced with datetime.now(timezone.utc) in 8 files
- **DEPRECATION [FIXED]**: Pydantic v1 `class Config` deprecated - migrated to ConfigDict() in 5 files (10 classes)
- **PYDANTIC_V2**: `populate_by_name` does NOT inherit to child models - declare on each model with alias fields
- **PYDANTIC_V2**: Use `ConfigDict()` over dict literal `model_config = {...}` for IDE autocomplete and type safety
- **VALIDATION [FIXED]**: File uploads now validate size (MAX_UPLOAD_SIZE_MB) and type (ALLOWED_FILE_EXTENSIONS) before processing
- **SLOWAPI_TESTS**: Reset limiter._storage.storage.clear() between tests to avoid rate limit interference
- **STARLETTE**: HTTP_413_CONTENT_TOO_LARGE does NOT exist in installed starlette version — keep using HTTP_413_REQUEST_ENTITY_TOO_LARGE
- **MEMORY [FIXED]**: LLMClientFactory cache now uses OrderedDict LRU with max_cache_size=10
- **RELIABILITY [FIXED]**: SQLite checkpoint dir auto-created via Path.mkdir(parents=True, exist_ok=True)
- **SECRETS [FIXED]**: Git tokens sanitized via _safe_url property in GitLoader
- **FUTURE_ANNOTATIONS**: `from __future__ import annotations` is safe in non-Pydantic-model files. Do NOT use in files defining Pydantic BaseModel subclasses.
- **FORWARD_REFS**: `"ClassName" | None` fails at runtime without `from __future__ import annotations`. Either use the import or `Optional["ClassName"]`
- **REFACTORING**: When extracting code to new modules, verify previously-fixed issues are preserved in the new location
- **TESTING**: Route coverage low (25-77%) means production bugs more likely in upload/streaming/resume paths

## Last Updated
2026-03-19 (Refactoring Phases 5-7)
