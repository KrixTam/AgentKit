from __future__ import annotations

import os
import sys
import tempfile

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from agenthub.models import AgentManifest
from agenthub.manifest import load_manifest


def test_manifest_validation_error_contains_field():
    bad_yaml = """
name: demo
version: "1.0.0"
entry: "invalid_entry_without_colon"
"""
    with tempfile.NamedTemporaryFile("w+", suffix=".yaml", delete=True) as f:
        f.write(bad_yaml)
        f.flush()
        try:
            load_manifest(f.name)
            assert False, "expected validation error"
        except ValueError as e:
            assert "entry" in str(e)


def test_manifest_semver_validation():
    with pytest.raises(Exception):
        AgentManifest(
            name="demo",
            version="1.0",  # invalid semver
            entry="pkg.module:create_agent",
        )


def test_manifest_new_fields_and_schema_backward_compat():
    m = AgentManifest(
        name="demo",
        version="1.0.0",
        description="demo desc",
        entry="pkg.module:create_agent",
        skills=["s1", "s2"],
        schema={"type": "object", "properties": {"input": {"type": "string"}}},
        output_schema={"type": "object", "properties": {"final_output": {"type": "string"}}},
        requires_human_input=True,
        runner_config={"max_turns": 8},
        tags=["demo"],
    )
    # backward compatibility: schema -> input_schema
    assert m.input_schema.get("type") == "object"
    assert m.manifest_schema.get("type") == "object"
    assert m.requires_human_input is True
    assert m.skills == ["s1", "s2"]
