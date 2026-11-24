import shutil
import sys

import pytest

import shfmt_dedent

pytestmark = pytest.mark.skipif(
    shutil.which("shfmt") is None, reason="shfmt binary not on PATH"
)


def _format(tmp_path, monkeypatch, text):
    target = tmp_path / "script.sh"
    target.write_text(text, encoding="utf-8")
    monkeypatch.setattr(sys, "argv", ["shfmt-dedent", str(target)])
    assert shfmt_dedent.main() == 0
    return target.read_text(encoding="utf-8")


def test_jq_pipeline_in_single_quotes_keeps_its_indentation(tmp_path, monkeypatch):
    text = (
        "#!/bin/bash\n"
        "jq '\n"
        "  def severity:\n"
        "    tonumber as $score\n"
        "    | first(.[] | select($score >= .min));\n"
        "  [\n"
        "    .results[]\n"
        "    | .package\n"
        "  ]\n"
        "  | sort' report.json\n"
    )

    assert _format(tmp_path, monkeypatch, text) == text


def test_heredoc_body_keeps_its_indentation(tmp_path, monkeypatch):
    text = (
        "#!/bin/bash\n"
        "cat << EOF\n"
        "    | Item | Value |\n"
        "    |------|-------|\n"
        "EOF\n"
    )

    assert _format(tmp_path, monkeypatch, text) == text


def test_heredoc_first_line_starting_with_an_expansion_keeps_its_indentation(
    tmp_path, monkeypatch
):
    text = (
        "#!/bin/bash\n"
        "true \\\n"
        "    && cat << EOF\n"
        "    $(date)\n"
        "    x\n"
        "EOF\n"
    )
    expected = (
        "#!/bin/bash\n"
        "true \\\n"
        "&& cat << EOF\n"
        "    $(date)\n"
        "    x\n"
        "EOF\n"
    )

    assert _format(tmp_path, monkeypatch, text) == expected


def test_non_newline_line_break_in_a_string_is_kept_and_does_not_shift_lines(
    tmp_path, monkeypatch
):
    text = (
        "#!/bin/bash\n"
        "x='a\x1cb'\n"
        "true \\\n"
        "    && echo '\n"
        "    | keep\n"
        "    '\n"
    )
    expected = (
        "#!/bin/bash\n"
        "x='a\x1cb'\n"
        "true \\\n"
        "&& echo '\n"
        "    | keep\n"
        "    '\n"
    )

    assert _format(tmp_path, monkeypatch, text) == expected


def test_pipeline_in_command_substitution_inside_a_string_is_dedented(
    tmp_path, monkeypatch
):
    text = (
        "#!/bin/bash\n"
        'echo "count: $(\n'
        "    ls |\n"
        "        wc -l\n"
        ')"\n'
    )
    expected = (
        "#!/bin/bash\n"
        'echo "count: $(\n'
        "    ls \\\n"
        "    | wc -l\n"
        ')"\n'
    )

    assert _format(tmp_path, monkeypatch, text) == expected
