from __future__ import annotations

import pytest

from agenthub import __version__
from agenthub.cli import main


def test_agenthub_exports_version():
    assert __version__ == "0.4.2"


def test_agenthub_cli_version_output(monkeypatch, capsys):
    monkeypatch.setattr("sys.argv", ["agenthub", "--version"])
    with pytest.raises(SystemExit) as exc_info:
        main()

    assert exc_info.value.code == 0
    output = capsys.readouterr().out.strip()
    assert output == f"agenthub {__version__}"
