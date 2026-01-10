"""
Test script to compare LangGraph executor vs Legacy executor.

This script tests both executors with sample data and compares:
- Execution time
- Token usage
- Results consistency
- Error handling
"""

import asyncio
import sys
import time
import json
from typing import Dict, Any

# Add project to path
sys.path.insert(0, '.')

from app.models.execution import ExecutionRequest
from app.services.executor import SkillExecutor
from app.services.graph_executor import GraphExecutor
from app.services.skill_registry import get_registry
from app.core.config import get_settings


# Sample test document
SAMPLE_DOCUMENT = """
John Smith, CEO of TechCorp Inc., announced today that the company will be opening a new office in San Francisco, California.
The expansion, scheduled for March 15, 2024, will create 200 new jobs in the Bay Area.

The announcement was made at the annual shareholders meeting in New York on January 10, 2024.
Sarah Johnson, CFO, stated that the company expects revenue to grow by 25% this year.

TechCorp Inc., founded in 2010 by John Smith and Mike Davis in Seattle, Washington,
has become a leader in artificial intelligence solutions.
"""


async def test_executor(executor, executor_name: str, request: ExecutionRequest) -> Dict[str, Any]:
    """Test a single executor and return metrics."""
    print(f"\n{'='*60}")
    print(f"Testing: {executor_name}")
    print(f"{'='*60}")

    start_time = time.time()

    try:
        response = await executor.execute(request)

        elapsed_time = time.time() - start_time

        print(f"✓ Status: {response.status.value}")
        print(f"✓ Execution time: {elapsed_time:.2f}s")
        print(f"✓ Processing time (internal): {response.metadata.processing_time_ms}ms")
        print(f"✓ Token usage: {response.metadata.token_usage.total_tokens} tokens")
        print(f"✓ Skills executed: {len(response.skill_results)}")

        # Show extracted data
        if response.data:
            print(f"\n📊 Extracted data:")
            print(json.dumps(response.data, indent=2)[:500] + "...")

        # Show validation results
        if response.validation:
            print(f"\n✅ Validation: {response.validation.status} (score: {response.validation.quality_score})")
            if response.validation.errors:
                print(f"   Errors: {response.validation.errors}")
            if response.validation.warnings:
                print(f"   Warnings: {response.validation.warnings}")

        return {
            "executor": executor_name,
            "success": True,
            "status": response.status.value,
            "elapsed_time": elapsed_time,
            "processing_time_ms": response.metadata.processing_time_ms,
            "token_usage": response.metadata.token_usage.total_tokens,
            "skills_executed": len(response.skill_results),
            "data": response.data,
            "error": None
        }

    except Exception as e:
        elapsed_time = time.time() - start_time
        print(f"✗ Error: {str(e)}")
        import traceback
        traceback.print_exc()

        return {
            "executor": executor_name,
            "success": False,
            "elapsed_time": elapsed_time,
            "error": str(e)
        }


async def main():
    """Run comparison tests."""
    print("\n" + "="*60)
    print("LangGraph vs Legacy Executor Comparison Test")
    print("="*60)

    # Initialize
    settings = get_settings()
    registry = get_registry()
    registry.initialize()  # Initialize is synchronous

    # Check available skills
    print(f"\n📋 Available skills:")
    schema_configs = registry.list_schemas()  # Returns list of SchemaConfig
    print(f"  Found {len(schema_configs)} schemas")

    if not schema_configs:
        print("\n⚠️  No skills found! Please ensure skills are loaded.")
        return

    schemas = []
    for config in schema_configs:
        try:
            schema = registry.get_schema(config.schema_id)
            if schema:
                schemas.append(schema)
                print(f"  - {config.schema_id}: {config.name}")
        except Exception as e:
            print(f"  ⚠️  Failed to load {config.schema_id}: {e}")

    if not schemas:
        print("\n⚠️  No skills found! Please ensure skills are loaded.")
        return

    # Use first available skill for testing
    test_skill = schemas[0].config.schema_id
    print(f"\n🎯 Testing with skill: {test_skill}")

    # Create test request
    request = ExecutionRequest(
        document=SAMPLE_DOCUMENT,
        skill_name=test_skill,
        vendor=None,  # Use default
        model=None    # Use default
    )

    # Initialize executors
    legacy_executor = SkillExecutor()
    graph_executor = GraphExecutor()

    # Test both executors
    results = []

    # Test 1: Legacy Executor
    result_legacy = await test_executor(legacy_executor, "Legacy Executor", request)
    results.append(result_legacy)

    # Small delay between tests
    await asyncio.sleep(1)

    # Test 2: LangGraph Executor
    result_graph = await test_executor(graph_executor, "LangGraph Executor", request)
    results.append(result_graph)

    # Comparison
    print(f"\n{'='*60}")
    print("COMPARISON SUMMARY")
    print(f"{'='*60}")

    if result_legacy["success"] and result_graph["success"]:
        print(f"\n⏱️  Performance:")
        print(f"  Legacy:    {result_legacy['elapsed_time']:.2f}s")
        print(f"  LangGraph: {result_graph['elapsed_time']:.2f}s")

        time_diff = result_graph['elapsed_time'] - result_legacy['elapsed_time']
        time_pct = (time_diff / result_legacy['elapsed_time']) * 100

        if time_diff > 0:
            print(f"  → LangGraph is {abs(time_pct):.1f}% slower (+{time_diff:.2f}s)")
        else:
            print(f"  → LangGraph is {abs(time_pct):.1f}% faster ({time_diff:.2f}s)")

        print(f"\n🪙 Token Usage:")
        print(f"  Legacy:    {result_legacy['token_usage']} tokens")
        print(f"  LangGraph: {result_graph['token_usage']} tokens")

        token_diff = result_graph['token_usage'] - result_legacy['token_usage']
        if token_diff == 0:
            print(f"  → Same token usage ✓")
        else:
            print(f"  → Difference: {token_diff:+d} tokens")

        print(f"\n📊 Results:")
        print(f"  Legacy status:    {result_legacy['status']}")
        print(f"  LangGraph status: {result_graph['status']}")

        # Check data consistency
        if result_legacy.get('data') == result_graph.get('data'):
            print(f"  → Results are IDENTICAL ✓")
        else:
            print(f"  → Results differ (check detailed output above)")

        print(f"\n✅ Both executors completed successfully!")

    else:
        print(f"\n⚠️  One or both executors failed:")
        if not result_legacy["success"]:
            print(f"  Legacy: {result_legacy['error']}")
        if not result_graph["success"]:
            print(f"  LangGraph: {result_graph['error']}")

    print(f"\n{'='*60}")
    print("Test completed!")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    asyncio.run(main())
