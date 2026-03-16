# Patterns
<!-- CONTRACT: This file accumulates learned patterns across sessions. Append only. -->

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
- **STARLETTE**: HTTP_413_REQUEST_ENTITY_TOO_LARGE is deprecated; use HTTP_413_CONTENT_TOO_LARGE
- **MEMORY**: LLMClientFactory cache grows unbounded - no eviction policy
- **RELIABILITY**: SQLite checkpoint directory (./data/) must pre-exist or initialization fails
- **SECRETS**: Git tokens embedded in URLs can leak in GitPython logs
- **TESTING**: Route coverage low (25-77%) means production bugs more likely in upload/streaming/resume paths

## Last Updated
2026-02-09
