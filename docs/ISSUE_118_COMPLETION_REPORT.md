# Windows package runtime evidence (#118)

Status: implementation and host checks; clean Windows acceptance remains open.

The runtime shipped by PR #169 used the CPython embeddable distribution. Backend
imports alone did not establish support for `venv` and `ensurepip`, which optional
engine installation requires. A copied developer virtual environment is also
insufficient: its base interpreter can remain outside the package.

## Current contract

- `prepare-standalone-python.ps1` downloads the full x64 Windows MSVC CPython
  3.12.14 distribution from the pinned python-build-standalone release 20260901.
  SHA-256 is verified before extraction. Source, version and digest are saved in
  `berry-runtime.json`; upstream licenses remain in the distribution.
- Dependencies are installed with the bundled interpreter. Preparation and probe
  temporary files stay under the repository. No global Python environment is used.
- The existing runtime is preserved until the candidate passes checks. Promotion
  to a different path must pass again; failed promotion restores the previous one.
- Runtime verification checks exact prefixes, executable and module containment,
  backend `app.main` imports, isolated engine `venv` creation and its own pip.
  It uses system-only PATH with Python environment variables cleared.
- Packaging creates `runtime/python` before copying. Bundled Git 2.56.0.2 is
  checksum verified before extraction and is mandatory. Download, extraction,
  version and runtime verification errors stop packaging.
- Smoke tests extract the delivered ZIP to another directory, then check bundled
  launcher/Git execution, backend imports and engine environment creation there.
  They do not silently substitute system tools or remove invalid `pyvenv.cfg`.
- Windows backend CI exercises standalone preparation and relocation, in addition
  to its normal tests. Full native package and clean VM journeys remain separate.

## Host evidence (2026-10-09)

CPython 3.12.14 preparation passed isolated imports, exact prefix checks and engine
environment creation at both the staging and promoted paths. An intentionally
invalid archive was rejected without changing the existing runtime executable.

The full package build and delivered ZIP smoke results must be recorded against
the final PR head. These host checks cannot establish clean VM acceptance.

## Required remaining acceptance evidence

Follow [CLEAN_MACHINE_TESTING.md](CLEAN_MACHINE_TESTING.md) on Windows without
Python, Git or Node installed. Record the exact commit, ZIP SHA-256, OS version
and results for native startup, cloud onboarding, scoped optional engine
installation and safe exit. Real cloud inference and NVIDIA inference require
their own provider/hardware evidence. Keep #118 open until these gates pass.

## Upstream sources

- [Pinned CPython assets](https://github.com/astral-sh/python-build-standalone/releases/tag/20260901)
- [Distribution behavior](https://github.com/astral-sh/python-build-standalone/blob/main/docs/distributions.rst)
- [Pinned Git for Windows release](https://github.com/git-for-windows/git/releases/tag/v2.56.0.windows.2)
