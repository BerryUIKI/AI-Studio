# Changelog

All notable changes to Berry AI Studio are documented in this file.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.1.1] - 2026-11-01

First release candidate after the v0.1.0 baseline. Focused on review-driven
correctness fixes rather than new capability.

### Fixed

- Projects: keep work recoverable when a project action fails, and gate window
  close and shutdown on a successful save (`#230`).
- Engines: report observed service health separately from process ownership,
  retain the Starting state, and report failed stop attempts (`#231`).
- Engines: route native engine views by the selected connection, retain complete
  HTTP(S) endpoints, start the selected engine, and withhold lifecycle controls
  from external engines (`#232`).
- Cloud: supply the configured provider and model fallback when only the legacy
  OpenAI configuration is present (`#233`).
- Canvas: keep task, error and cancellation feedback visible inside the active
  Inpaint and Upscale dialogs, and allow those dialogs to scroll (`#234`).
- Canvas: make the model inventory shortcut reopen on the inventory tab, and
  honour externally selected connections (`#235`).
- Canvas: preserve an explicit zero seed and label random or empty input
  distinctly (`#236`).
- Runtime: exercise the real asynchronous download stream protocol in tests
  instead of leaving unresolved-mock warnings (`#238`).

### Changed

- Tests: declare the pytest async fixture event-loop scope explicitly, removing
  the last backend configuration warning (`#241`).

### Build

- Build: validate the Tauri v2 `frontendDist` path before packaging and reject a
  missing or reversed build order instead of warning (`#239`).
- Desktop: align both Tauri dialog plugins on 2.7.3 and add a Tauri CLI
  compatibility check to CI (`#240`).

### Known limitations

This release candidate has not completed live acceptance. Local ComfyUI and
WebUI inference, authorized cloud-provider journeys, GUI layout at supported
display scales, and clean Windows installation remain unverified; see
[docs/RELEASE_ACCEPTANCE_GATE.md](docs/RELEASE_ACCEPTANCE_GATE.md) and the
[2026-11-01 review follow-up](docs/reviews/2026-11-01-acceptance-follow-up.md).

[Unreleased]: https://github.com/BerryUIKI/AI-Studio/compare/v0.1.0...HEAD
[0.1.1]: https://github.com/BerryUIKI/AI-Studio/compare/v0.1.0...HEAD
