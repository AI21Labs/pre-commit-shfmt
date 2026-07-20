# pre-commit-shfmt

[![Main push and PR checks](https://github.com/scop/pre-commit-shfmt/actions/workflows/check.yml/badge.svg)](https://github.com/scop/pre-commit-shfmt/actions/workflows/check.yml)
[![Tag checks](https://github.com/scop/pre-commit-shfmt/actions/workflows/check-tag.yml/badge.svg)](https://github.com/scop/pre-commit-shfmt/actions/workflows/check-tag.yml)
[![CodeQL](https://github.com/scop/pre-commit-shfmt/actions/workflows/github-code-scanning/codeql/badge.svg)](https://github.com/scop/pre-commit-shfmt/actions/workflows/github-code-scanning/codeql)
[![OpenSSF Scorecard](https://api.scorecard.dev/projects/github.com/scop/pre-commit-shfmt/badge)](https://scorecard.dev/viewer/?uri=github.com%2Fscop%2Fpre-commit-shfmt)

[shfmt](https://github.com/mvdan/sh#shfmt) hook for
[prek](https://prek.j178.dev) and
[pre-commit](https://pre-commit.com), with auto install.

Usage in `.pre-commit-config.yaml`:

```yaml
- repo: https://github.com/scop/pre-commit-shfmt
  rev: v3.13.1-1
  hooks:
    - id: shfmt  # prebuilt upstream executable
```

> #### Notes
>
> From v3.12.0-2 on, the default args passed to `shfmt`
> [no longer contain `-s`](https://github.com/mvdan/sh/issues/1173).
>
> From v3.7.0-2 on, the `shfmt` id points to the variant that uses a prebuilt
> upstream executable.

## Development

Use `run.sh` to run tests or `tox` inside a local virtualenv. On first run it
creates `.venv` and installs the package with its `test` and `dev` extras,
reusing the environment on subsequent runs.

```sh
./run.sh pytest          # run the test suite
./run.sh pytest -k gpu   # extra args are forwarded to pytest
./run.sh tox             # run tox across the configured interpreters
```

Set `PYTHON` to control the interpreter used to bootstrap the virtualenv, e.g.
`PYTHON=python3.13 ./run.sh pytest`.
