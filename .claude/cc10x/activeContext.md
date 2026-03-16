# Active Context
<!-- CONTRACT: This file tracks current session context. Update at workflow checkpoints. -->

## Current Focus
Completed Phase 4: Added file upload validation (size + type) to /execute/file endpoint.

## Recent Changes
- [2026-02-09] Phase 4: Added file upload validation to /execute/file endpoint
  - MAX_UPLOAD_SIZE_MB setting (default 10) in app/core/config.py
  - ALLOWED_FILE_EXTENSIONS setting (default .txt,.md,.json,.csv,.xml,.html,.pdf)
  - File type validation (415) checked BEFORE file content read
  - File size validation (413) checked after read but before decode
  - 15 new tests in tests/test_file_upload_validation.py
- [2026-02-06] Phase 2: Replaced datetime.utcnow() with datetime.now(timezone.utc) in 8 files (14 occurrences)
- [2026-02-06] Added 4 new tests in tests/test_datetime_timezone.py to verify timezone-aware datetimes
- [2026-02-06] Fixed proxy-aware rate limiting with custom get_client_ip() that checks X-Forwarded-For header
- [2026-02-06] Fixed exception message sanitization - hides internal details in production (debug=False)
- [2026-02-06] Added rate limit decorators to /resume and /legacy endpoints (10/min)
- [2026-02-06] Added 8 new tests for security fixes in tests/test_security.py (now 21 total)
- [2026-02-06] Added ALLOWED_ORIGINS setting to config.py with environment-based CORS origins
- [2026-02-06] Added slowapi rate limiting to execute endpoints (10/min, 5/min, 5/min)
- [2026-02-06] Added TimeoutMiddleware with configurable REQUEST_TIMEOUT_SECONDS (default 300s)
- [2026-02-06] Created app/core/rate_limiter.py to avoid circular imports

## Next Steps
- All 4 phases complete. Ready for code review and final verification.

## Decisions
- Use lambda for datetime.now(timezone.utc) in Pydantic Field default_factory (datetime.now requires callable)
- Used X-Forwarded-For header for proxy-aware rate limiting, taking first IP from comma-separated list
- Hide exception details in production using settings.debug flag, always log full details server-side
- Moved limiter to app/core/rate_limiter.py to avoid circular import between main.py and execute.py
- Used slowapi for rate limiting (standard FastAPI rate limiting library)
- Used custom TimeoutMiddleware based on BaseHTTPMiddleware (simpler than starlette-context)
- Used type: ignore[misc] comments for slowapi decorators (library lacks type stubs)

## Learnings
- Slowapi in-memory storage persists across tests; must reset limiter._storage.storage.clear() between tests
- FastAPI rejects empty filename multipart uploads with 422 before route handler executes
- HTTP_413_REQUEST_ENTITY_TOO_LARGE is deprecated in starlette; use HTTP_413_CONTENT_TOO_LARGE
- os.path.splitext("Makefile") returns ("Makefile", "") - no extension is empty string
- Routes are mounted at /api/v1 prefix; tests must use /api/v1/execute/file not /execute/file
- FastAPI TestClient requires raise_server_exceptions=False to test exception handlers
- Dual executor pattern (SkillExecutor vs GraphExecutor) with USE_LANGGRAPH feature flag
- LangGraph enables checkpointing (SQLite), streaming (SSE), and human-in-the-loop workflows
- Skill registry is singleton with thread-safe locking for concurrent requests
- Skills organized in schemas with parallel execution groups (group 1, 2, 3...)
- Fully async architecture with no blocking I/O
- Test coverage at 45% minimum, routes undertested (25-77%) vs services (59-98%)
- LLMClientFactory caches clients by vendor:model key but lacks eviction (potential memory leak)
- Retry logic uses exponential backoff with 1s * attempt delay
- Three merge strategies: FIRST_WINS, LAST_WINS, MERGE_DEEP for combining skill results
- Validation uses Pydantic model validation + custom rules (sum_check, required, range_check)

## References
- Plan: N/A
- Design: N/A
- Research: N/A

## Blockers
- None

## Last Updated
2026-02-09 (Phase 4 File Upload Validation Complete)
