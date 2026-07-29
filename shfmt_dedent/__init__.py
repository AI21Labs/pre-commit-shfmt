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
untouched.
"""

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


def _dedent(text: str) -> str:
    """Dedent the operands of multi-line ``&&`` / ``||`` / ``|`` compounds.

    Processes the text one line at a time, keeping a stack of open operand
    regions so nested operators are handled in a single pass. Returns the transformed text with every line
    terminated by ``\\n``.
    """
    base: list[int] = []  # base column of each open operand region
    out: list[str] = []
    for line in text.splitlines():
        if _BLANK.match(line):
            out.append(line)
            continue

        ind = _LEADING_SPACES.match(line).end()
        # shfmt -bn always indents an operand at least one level, so a real
        # operator line is never at column 0. Requiring `ind >= 4` keeps
        # line-initial `|` inside a string literal (e.g. a markdown table row in
        # a multi-line assignment) from opening a region that swallows the rest
        # of the file.
        if ind >= 4 and _OPERATOR.match(line):
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

    # awk terminates every record with ORS (\n), so each line gets one.
    return "".join(line + "\n" for line in out)


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
    transformed = _dedent(result.stdout)
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
