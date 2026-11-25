"""Ensure the hook preserves a script holding a markdown table in a string.

``github_release.sh`` builds a PR comment body from a multi-line assignment whose
lines start with ``|``. Those are string content, not pipe operators, so the
dedent pass must leave them -- and every line after them -- alone. The fixture is
checked in already formatted by this hook, so running the formatter on it must be
a no-op. The test copies the file to a temp dir before formatting so the tracked
file is never modified.
"""

import shutil
import sys
from pathlib import Path

import pytest

import shfmt_dedent

_FIXTURE = Path(__file__).resolve().parent / "fixtures" / "github_release.sh"


@pytest.mark.skipif(
    shutil.which("shfmt") is None, reason="shfmt binary not on PATH"
)
def test_formatter_preserves_markdown_table_in_string(tmp_path, monkeypatch):
    original = _FIXTURE.read_text(encoding="utf-8")

    target = tmp_path / _FIXTURE.name
    target.write_text(original, encoding="utf-8")

    monkeypatch.setattr(sys, "argv", ["shfmt-dedent", str(target)])
    assert shfmt_dedent.main() == 0

    assert target.read_text(encoding="utf-8") == original


@pytest.mark.skipif(
    shutil.which("shfmt") is None, reason="shfmt binary not on PATH"
)
def test_dedent_ignores_line_initial_pipe_in_string():
    """A ``|`` inside a string must not dedent the code that follows it."""
    text = (
        "f() {\n"
        '    body="## Title\n'
        "\n"
        "| Item | Value |\n"
        "|------|-------|\n"
        '| **Version** | \\`1.0\\`"\n'
        "\n"
        '    gh pr comment --body "$body"\n'
        "}\n"
    )

    assert shfmt_dedent._dedent(text, shfmt_dedent._string_lines(text)) == text
