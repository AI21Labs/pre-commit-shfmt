"""Wrapper for the ``shfmt`` pre-commit hook.

With ``-bn``, shfmt puts each ``&&`` / ``||`` / ``|`` on its own line and
indents the whole operand -- the operator line, its body, and any closing brace
-- one level deeper than the list's first command, which reads as excessive
nesting. There is no shfmt flag to disable it, so this pass pulls each operand
back to align its operator with the first command's column.

The dedent keeps a stack of open operand regions so nested operators are handled
in one pass. A line that *starts* with ``&&``, ``||``, or ``|`` opens a region whose
base column is one level (4 spaces) shallower than the operator; every line loses
4 spaces per enclosing region (including its own), so a pipe nested inside a
``||`` operand is pulled back two levels. A region closes when indentation returns
to its base column; a sibling operator at the same column reopens at the same
depth (it continues the same list, it does not nest). Mid-line operators (e.g.
inside ``[[ a || b ]]``) and single-line lists never match, so they are left
untouched. So are lines that start inside a quoted string or a heredoc body: their
indentation and any leading ``|`` are string content, such as a jq program.
"""

import json
import os
import re
import subprocess
import sys

# Hard-coded shfmt formatting flags (matching the original `shfmt -i 4 -ci -sr
# -bn "$f"`). Fixing them here keeps formatting consistent regardless of any
# `args` the hook config passes. `-w` is intentionally omitted: we feed each
# file to shfmt on stdin and capture stdout, so shfmt must not write in place.
_SHFMT_ARGS = ["-i", "4", "-ci", "-sr", "-bn"]

# Only leading spaces count as indentation, matching the awk `/^ */` measure.
_LEADING_SPACES = re.compile(r"^ *")
# A line is blank if it is empty or whitespace-only ([[:space:]] in awk).
_BLANK = re.compile(r"^[ \t\r\f\v]*$")
# A line opens an operand region when it starts with `&&`, `||`, or `|`
# followed by whitespace or end of line (mirrors the awk operator match).
_OPERATOR = re.compile(r"^[ \t\r\f\v]*(\|\|?|&&)([ \t\r\f\v]|$)")


def _string_lines(text: str) -> frozenset[int]:
    result = subprocess.run(
        ["shfmt", "--to-json"],
        input=text,
        capture_output=True,
        text=True,
        check=True,
    )
    lines: set[int] = set()
    nodes = [json.loads(result.stdout)]
    while nodes:
        node = nodes.pop()
        if isinstance(node, list):
            nodes.extend(node)
        elif isinstance(node, dict):
            nodes.extend(node.values())
            # A heredoc body starts at column 1, so its first line is content even
            # when no multi-line literal spans it, e.g. when it starts with $(...).
            if "Hdoc" in node:
                lines.add(node["Hdoc"]["Pos"]["Line"])
            # Code in a $(...) inside a string is its own node, so its lines stay code.
            if node.get("Type") not in ("Lit", "SglQuoted"):
                continue
            start, end = node["Pos"], node["End"]
            if start["Line"] == end["Line"]:
                continue
            first = start["Line"] + 1
            # End is exclusive: ending at column 1 leaves that line outside the node.
            last = end["Line"] if end["Col"] > 1 else end["Line"] - 1
            lines.update(range(first, last + 1))
    return frozenset(lines)


def _dedent(text: str, string_lines: frozenset[int]) -> str:
    """Dedent the operands of multi-line ``&&`` / ``||`` / ``|`` compounds.

    Processes the text one line at a time, keeping a stack of open operand
    regions so nested operators are handled in a single pass.
    """
    base: list[int] = []  # base column of each open operand region
    out: list[str] = []
    # Split on "\n" only: shfmt numbers lines that way, and splitlines() would
    # also break on characters such as \x1c or   inside strings.
    for number, line in enumerate(text.split("\n"), start=1):
        if number in string_lines or _BLANK.match(line):
            out.append(line)
            continue

        ind = _LEADING_SPACES.match(line).end()
        if _OPERATOR.match(line):
            nb = ind - 4  # column to align the operator to
            while base and base[-1] >= nb:  # drop siblings/shallower regions
                base.pop()
            dedent = 4 * (len(base) + 1)  # enclosing regions + this one
            base.append(nb)
        else:
            while base and ind <= base[-1]:  # close regions we have exited
                base.pop()
            dedent = 4 * len(base)

        if dedent > ind:  # never strip past the text
            dedent = ind
        out.append(line[dedent:])

    return "\n".join(out)


def _format_file(path: str) -> None:
    with open(path, encoding="utf-8") as f:
        original = f.read()
    result = subprocess.run(
        ["shfmt", *_SHFMT_ARGS],
        input=original,
        capture_output=True,
        text=True,
        check=True,
    )
    transformed = _dedent(result.stdout, _string_lines(result.stdout))
    if transformed != original:
        with open(path, "w", encoding="utf-8") as f:
            f.write(transformed)


def main() -> int:
    # pre-commit passes filenames as argv; the shfmt flags are hard-coded above.
    files = [arg for arg in sys.argv[1:] if os.path.isfile(arg)]
    for f in files:
        _format_file(f)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
