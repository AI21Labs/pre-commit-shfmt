#!/usr/bin/env python3

import sys


hooks_template = """
- id: shfmt
  name: shfmt
  description: Shell source code formatter (prebuilt upstream executable)
  language: python
  # Wrapper console script: runs shfmt, then dedents multi-line && / || / | operands.
  entry: shfmt-dedent
  types: [shell]
  exclude_types: [csh, tcsh]
  stages: [pre-commit, pre-merge-commit, pre-push, manual]
  minimum_pre_commit_version: 3.2.0 # for "stages" names
"""


def main() -> None:
    sys.stdout.write(hooks_template.lstrip())


if __name__ == "__main__":
    main()
