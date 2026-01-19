"""Tests for Pydantic models."""


from app.models.events import EventType, GitWebhookPayload, SkillEvent
from app.models.execution import ExecutionRequest, ExecutionResponse, ExecutionStatus
from app.models.schema import LoadedSchema, MergeStrategy, SchemaConfig, ValidationRule
from app.models.skill import Skill, SkillConfig, SkillExecutionResult, SkillStatus


class TestSkillModels:
    """Tests for skill-related models."""

    def test_skill_config_defaults(self):
        """Test SkillConfig with minimal required fields."""
        config = SkillConfig(
            id="test",
            name="Test Skill",
            prompt_file="prompts/test.md",
        )

        assert config.id == "test"
        assert config.parallel_group == 1
        assert config.timeout_seconds == 45
        assert config.retry_count == 2
        assert config.temperature == 0.0
        assert config.status == SkillStatus.ACTIVE

    def test_skill_config_custom_values(self):
        """Test SkillConfig with custom values."""
        config = SkillConfig(
            id="custom",
            name="Custom Skill",
            prompt_file="prompts/custom.md",
            parallel_group=3,
            timeout_seconds=120,
            retry_count=5,
            vendor="openai",
            model="gpt-4o",
            temperature=0.7,
            status=SkillStatus.DISABLED,
        )

        assert config.parallel_group == 3
        assert config.timeout_seconds == 120
        assert config.vendor == "openai"
        assert config.temperature == 0.7
        assert config.status == SkillStatus.DISABLED

    def test_skill_effective_vendor(self):
        """Test Skill.get_effective_vendor method."""
        config = SkillConfig(
            id="test", name="Test", prompt_file="test.md", vendor="anthropic"
        )
        skill = Skill(
            id="test",
            name="Test",
            prompt="Test prompt",
            config=config,
            schema_id="schema",
            version="abc123",
            file_path="/path/test.md",
        )

        assert skill.get_effective_vendor("gemini") == "anthropic"

        # Test fallback when vendor not set
        config.vendor = None
        assert skill.get_effective_vendor("gemini") == "gemini"

    def test_skill_execution_result(self):
        """Test SkillExecutionResult model."""
        result = SkillExecutionResult(
            skill_id="test",
            success=True,
            data={"key": "value"},
            execution_time_ms=500,
            model_used="claude-sonnet-4-20250514",
            vendor_used="anthropic",
        )

        assert result.success is True
        assert result.data == {"key": "value"}
        assert result.retries == 0


class TestSchemaModels:
    """Tests for schema-related models."""

    def test_schema_config_minimal(self):
        """Test SchemaConfig with minimal fields."""
        config = SchemaConfig(
            schema_id="test",
            version="1.0",
            name="Test Schema",
        )

        assert config.schema_id == "test"
        assert config.skills == []
        assert config.post_processing.merge_strategy == MergeStrategy.MERGE_DEEP

    def test_validation_rule(self):
        """Test ValidationRule model."""
        rule = ValidationRule(
            id="sum_check",
            name="Check Sum",
            type="sum_check",
            params={"expected": "total", "operands": ["a", "b"]},
            severity="error",
        )

        assert rule.type == "sum_check"
        assert rule.severity == "error"

    def test_loaded_schema_get_skills_by_group(self):
        """Test LoadedSchema.get_skills_by_group method."""
        config = SchemaConfig(
            schema_id="test", version="1.0", name="Test"
        )

        skill1_config = SkillConfig(
            id="s1", name="S1", prompt_file="s1.md", parallel_group=2
        )
        skill2_config = SkillConfig(
            id="s2", name="S2", prompt_file="s2.md", parallel_group=1
        )
        skill3_config = SkillConfig(
            id="s3", name="S3", prompt_file="s3.md", parallel_group=2
        )

        skills = {
            "s1": Skill(
                id="s1", name="S1", prompt="p1", config=skill1_config,
                schema_id="test", version="v1", file_path="s1.md"
            ),
            "s2": Skill(
                id="s2", name="S2", prompt="p2", config=skill2_config,
                schema_id="test", version="v1", file_path="s2.md"
            ),
            "s3": Skill(
                id="s3", name="S3", prompt="p3", config=skill3_config,
                schema_id="test", version="v1", file_path="s3.md"
            ),
        }

        loaded = LoadedSchema(
            config=config,
            skills=skills,
            git_commit="abc123",
            source_path="/test",
        )

        groups = loaded.get_skills_by_group()

        assert list(groups.keys()) == [1, 2]
        assert len(groups[1]) == 1
        assert len(groups[2]) == 2


class TestEventModels:
    """Tests for event-related models."""

    def test_skill_event_creation(self):
        """Test SkillEvent model."""
        event = SkillEvent(
            type=EventType.SKILL_UPDATED,
            schema_id="test_schema",
            skill_id="test_skill",
            git_commit="abc123",
        )

        assert event.type == EventType.SKILL_UPDATED
        assert event.id is not None
        assert event.timestamp is not None

    def test_git_webhook_payload_get_branch(self):
        """Test GitWebhookPayload.get_branch method."""
        payload = GitWebhookPayload(
            ref="refs/heads/main",
            after="abc123",
        )

        assert payload.get_branch() == "main"

        payload.ref = "refs/heads/feature/new-skill"
        assert payload.get_branch() == "feature/new-skill"

        payload.ref = None
        assert payload.get_branch() is None

    def test_git_webhook_payload_get_changed_files(self):
        """Test GitWebhookPayload.get_changed_files method."""
        payload = GitWebhookPayload(
            commits=[
                {"added": ["file1.py"], "modified": ["file2.py"], "removed": []},
                {"added": [], "modified": ["file3.py"], "removed": ["file4.py"]},
            ]
        )

        files = payload.get_changed_files()
        assert set(files) == {"file1.py", "file2.py", "file3.py", "file4.py"}


class TestExecutionModels:
    """Tests for execution-related models."""

    def test_execution_request(self):
        """Test ExecutionRequest model."""
        request = ExecutionRequest(
            document="Test document content",
            schema_id="test_schema",
        )

        assert request.document == "Test document content"
        assert request.vendor is None
        assert request.skill_ids is None

    def test_execution_response(self):
        """Test ExecutionResponse model."""
        response = ExecutionResponse(
            status=ExecutionStatus.COMPLETED,
            schema_id="test",
            data={"field": "value"},
        )

        assert response.status == ExecutionStatus.COMPLETED
        assert response.metadata is not None
        assert response.metadata.execution_id is not None
