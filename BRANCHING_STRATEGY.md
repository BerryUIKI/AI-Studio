# Git Branching Strategy & Release Specification

This document establishes the official Git branching model, branch governance, commit standards, and release workflows for the **Berry AI Studio** repository.

---

## 1. Branch Architecture Overview

The repository follows a modified Git Flow model optimized for modern CI/CD, continuous development, and strict release stability.

```
(main)    v0.1.0 -------------------------------------> v0.2.0 (Release Tags)
             ^                                             ^
             |                                             |
(release)    |                                      [release/v0.2.0]
             |                                             ^
(dev)        +--- [PR Merge] <--- [PR Merge] <--- [PR Merge] (Integration)
                    ^                   ^
                    |                   |
(feature)      [feature/canvas]    [feature/api-runner]
```

### The Primary Branches

| Branch | Lifecycle | Protection Level | Purpose |
| :--- | :--- | :--- | :--- |
| **`main`** | Permanent | **Strictly Protected** | **Production / Official Releases**. Every commit on `main` represents a stable, release-ready artifact tagged with a Semantic Version (`vX.Y.Z`). Direct pushes are prohibited. |
| **`dev`** | Permanent | **Protected (Default Branch)** | **Active Integration**. All new features, performance improvements, and non-critical bug fixes converge here. Continuous Integration (CI) test suites run on every commit. |

---

## 2. Supporting Branch Conventions

All temporary branches must branch off the appropriate source and follow the standardized naming convention:

```
<prefix>/<issue-id-or-descriptor>
```

| Type | Source Branch | Target Branch | Description & Example |
| :--- | :--- | :--- | :--- |
| **`feature/*`** | `dev` | `dev` | New features, nodes, UI modules.<br>`feature/reactflow-canvas`<br>`feature/isolated-comfy-installer` |
| **`bugfix/*`** | `dev` | `dev` | Non-critical bug fixes during normal development.<br>`bugfix/dag-cycle-detection`<br>`bugfix/node-cache-hash` |
| **`release/*`** | `dev` | `main` & `dev` | Preparing a new production release (version bumping, changelog update, final freeze testing).<br>`release/v0.2.0` |
| **`hotfix/*`** | `main` | `main` & `dev` | Critical production security or runtime bug fixes requiring immediate deployment.<br>`hotfix/v0.1.1` |

---

## 3. Commit Message Standards (Conventional Commits)

Write all commit messages and pull request titles and descriptions in English.

All commits across all branches must follow the [Conventional Commits v1.0.0](https://www.conventionalcommits.org/) specification:

```
<type>(<optional scope>): <description>

[optional body]

[optional footer(s)]
```

### Allowed Types

- **`feat`**: Introduces a new feature or user-facing capability.
- **`fix`**: Fixes a bug.
- **`docs`**: Documentation changes only.
- **`style`**: Formatting, missing semi-colons, whitespace (no code change).
- **`refactor`**: Code restructuring that neither fixes a bug nor adds a feature.
- **`perf`**: Performance improvement.
- **`test`**: Adding missing tests or correcting existing tests.
- **`build`**: Changes that affect the build system or external dependencies (npm, uv, pyproject, vite).
- **`ci`**: Changes to CI/CD configuration files and scripts (GitHub Actions).
- **`chore`**: Maintenance tasks, housekeeping, tooling updates.

### Examples

- `feat(canvas): add single-node run button and isolated execution trigger`
- `fix(engine): resolve race condition in dag topological sort when nodes fail`
- `docs(readme): add quickstart guide for isolated comfyui runtime`
- `refactor(runners): unify openai-compatible request payload adapter`

---

## 4. Pull Request (PR) Lifecycle & Merge Rules

### Branch Protection Rules
1. **No direct pushes** to `main` or `dev`.
2. **Review Requirements**: At least 1 code review approval required before merge.
3. **CI Status Checks**: All automated tests, type checks (`tsc`, `pyright`/`mypy`), and linter runs (`eslint`, `ruff`) must pass.
4. **Up-to-Date**: Branches must be rebased or updated with target before merging.

### Merge Strategies
- **Merging into `dev`**: **Squash and Merge** or **Rebase and Merge** (keeps the integration history linear and readable).
- **Merging into `main`**: **Merge Commit** (preserves the release branch history and tag pointers) or **Squash and Merge** for hotfixes.

---

## 5. Release Workflow & Semantic Versioning

This project adheres to **Semantic Versioning (SemVer 2.0.0)**:
`MAJOR.MINOR.PATCH`

- **MAJOR**: Incompatible API or workflow graph schema breaking changes.
- **MINOR**: Backward-compatible new functionality (e.g., new node types, runner drivers).
- **PATCH**: Backward-compatible bug fixes and security patches.

### Step-by-Step Release Procedure

1. **Cut Release Branch**:
   ```bash
   git checkout dev
   git pull origin dev
   git checkout -b release/v0.2.0
   ```
2. **Stabilization & Bumping**:
   - Bump version numbers in `package.json`, `pyproject.toml`, etc.
   - Update `CHANGELOG.md` with notes from the milestone.
   - Run full regression tests and verification suites.
3. **Merge Release into `main`**:
   - Create PR from `release/v0.2.0` into `main`.
   - Once approved and merged, tag the release:
     ```bash
     git checkout main
     git pull origin main
     git tag -a v0.2.0 -m "Release v0.2.0: Isolated ComfyUI engine integration"
     git push origin v0.2.0
     ```
4. **Back-merge into `dev`**:
   - Merge `release/v0.2.0` back into `dev` to ensure version bumps and changelog persist.
   - Delete `release/v0.2.0`.
