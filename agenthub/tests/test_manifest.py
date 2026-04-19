from __future__ import annotations

import os
import sys
import tempfile

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

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
