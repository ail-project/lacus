## Unreleased

### Feat

**code-formatting-best-practices**:
- pre-commit new features:
  - python-check-mock-methods
  - python-use-type-annotations
  - rst-backticks
  - rst-directive-colons
  - rst-inline-touching-normal
  - text-unicode-replacement-char
  - check-added-large-files
  - check-ast
  - check-builtin-literals
  - check-case-conflict
  - check-docstring-first
  - check-json
  - check-merge-conflict
  - check-shebang-scripts-are-executable
  - check-symlinks
  - check-toml
  - check-vcs-permalinks
  - check-xml
  - check-yaml
  - debug-statements
  - destroyed-symlinks
  - detect-private-key
  - end-of-file-fixer
  - fix-byte-order-marker
  - mixed-line-ending
  - name-tests-test
  - trailing-whitespace
  - commitizen
  - ruff
  - black
  - poetry-check
  - poetry-lock-check
  - mypy
- add support to documentation
- add support to test
- add support to poethepoet
- add force format commit message(documentation)
- add support to pre-commit
- add support to black
- add support to coverage
- add support to pytest
- add support to ruff 
- add support to ChangeLog
- add support to bump(release): v$current_version → v$new_version




## v1.6.0 (2023-06-30)

### Fix

- add call to install system deps
- encoding issue, for good.
- encoding issue

## v1.5.0 (2023-05-31)

### Fix

- Pass max capture time to LacusCore.

## v1.4.1 (2023-04-09)

### Fix

- Avoid stoping the DB before everything is really done.
- Make sure we do not stop lacus while a capture is going

## v1.3.0 (2023-03-01)

## v1.2.0 (2022-12-29)

### Fix

- Edge case on some urls
- Install dev for mypy checks
- Missing import

## v1.1.0 (2022-10-28)

### Fix

- Properly handle canceled tasks.

## v1.0.0 (2022-10-19)

### Fix

- Typo in lacuscore
- Issues with cookies, bump deps
- another typo.
- Typo in workflow
- missing config, CI
