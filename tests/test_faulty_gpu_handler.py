"""Ensure the shfmt wrapper leaves already-formatted files untouched.

``faulty_gpu_handler-formatted.sh`` is checked in already formatted by this hook, so
running the formatter on it must be a no-op. The test copies the file to a
temp dir before formatting so the tracked file is never modified.
"""

import shutil
import sys
from pathlib import Path

import pytest

import shfmt_dedent

_FIXTURES = Path(__file__).resolve().parent / "fixtures"
_FORMATTED_FIXTURE = _FIXTURES / "faulty_gpu_handler-formatted.sh"
_UNFORMATTED_FIXTURE = _FIXTURES / "faulty_gpu_handler-unformatted.sh"


@pytest.mark.skipif(
    shutil.which("shfmt") is None, reason="shfmt binary not on PATH"
)
def test_formatter_makes_no_changes(tmp_path, monkeypatch):
    original = _FORMATTED_FIXTURE.read_text(encoding="utf-8")

    target = tmp_path / _FORMATTED_FIXTURE.name
    target.write_text(original, encoding="utf-8")

    monkeypatch.setattr(sys, "argv", ["shfmt-dedent", str(target)])
    assert shfmt_dedent.main() == 0

    assert target.read_text(encoding="utf-8") == original


@pytest.mark.skipif(
    shutil.which("shfmt") is None, reason="shfmt binary not on PATH"
)
def test_formatter_reformats_unformatted_file(tmp_path, monkeypatch):
    original = _UNFORMATTED_FIXTURE.read_text(encoding="utf-8")

    target = tmp_path / _UNFORMATTED_FIXTURE.name
    target.write_text(original, encoding="utf-8")

    monkeypatch.setattr(sys, "argv", ["shfmt-dedent", str(target)])
    assert shfmt_dedent.main() == 0

    assert target.read_text(encoding="utf-8") != original

    formatted = _FORMATTED_FIXTURE.read_text(encoding="utf-8")
    assert target.read_text(encoding="utf-8") == formatted


