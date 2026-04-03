# Release Playbook

This playbook documents the release process for this project.

> **Template repo note:** Release workflows are disabled by default. See the TODO comments in each workflow file to enable them when using this template in a real project.

---

## Minor / Major Release

A minor release (e.g., 0.1.0 → 0.2.0) ships new features and represents a new supported version.

### Prerequisites

- On the `main` branch, up to date with remote
- `task check` passes (lint, typecheck, test, security)
- DHI registry credentials configured (`DOCKERHUB_USERNAME` / `DOCKERHUB_TOKEN` secrets)
- GitHub App secrets configured (`MCP_RELEASE_WORKFLOW_APP_ID` / `MCP_RELEASE_WORKFLOW_APP_KEY`) — a GitHub App installed on this repo with **Contents: Read & Write** permission. Required to generate an ephemeral token that will work for triggering downstream workflows (GitHub Actions security restriction). See [Setup: GitHub App for releases](#setup-github-app-for-releases) below.

### Steps

**1. Cut the release:**

Trigger the `Create Release` workflow via GitHub UI or CLI:

```bash
gh workflow run create-release.yml -f version=0.2.0
```

This workflow (`create-release.yml`):
- Validates the version is strict semver (`X.Y.Z`)
- Verifies neither the `release/X.Y` branch nor the `vX.Y.Z` tag already exist
- Creates `release/0.2` branch from `main` (or a specified base ref)
- Bumps both `VERSION` and `pyproject.toml` to `0.2.0`
- Commits as `"Release v0.2.0"` and pushes
- Tags `v0.2.0` and pushes — which triggers the release pipeline

**2. The tag push triggers the release pipeline (`release.yml`):**

The pipeline runs three jobs in sequence:

| Job | Steps |
|-----|-------|
| **Code checks** (`code-checks.yml`) | Code quality (ruff lint, ty typecheck, pytest, bandit + pip-audit) → Docker image build → Grype vulnerability scan (filesystem + image) |
| **Release container** | Validates `VERSION` ↔ `pyproject.toml` ↔ git tag consistency → Builds multi-arch container (linux/amd64, linux/arm64) via Docker Buildx with DHI base image → Pushes to `ghcr.io/<owner>/<repo>` with semver tags → Generates SBOM → Attests SLSA build provenance → Signs image digest with Cosign (keyless via GitHub OIDC) → Verifies signature and provenance attestation |
| **GitHub Release** | Creates a GitHub Release for the tag with auto-generated notes categorized by PR labels (via `.github/release.yml` config) |

**3. Verify the release:**

```bash
# Check the GitHub Release was created
gh release view v0.2.0

# Verify the container signature (replace <owner>/<repo> with actual values)
cosign verify \
  --certificate-identity-regexp="https://github.com/<owner>/<repo>/.github/workflows/release.yml@.*" \
  --certificate-oidc-issuer="https://token.actions.githubusercontent.com" \
  ghcr.io/<owner>/<repo>:0.2.0
```

---

## Patch Release

A patch release (e.g., 0.2.0 → 0.2.1) addresses bugs or security fixes on the latest supported version. Patch releases are **automated**: merging a PR to a `release/*` branch triggers `patch-release.yml`, which bumps VERSION, commits, tags, and pushes — firing the same release pipeline as a minor release.

### Steps

**1. Develop the fix on a branch off the release branch:**

```bash
# For a new fix
git checkout -b fix/handle-token-expiry origin/release/0.2

# Or cherry-pick a fix that already exists on main
git checkout -b fix/cherry-pick-token-expiry origin/release/0.2
git cherry-pick <commit-sha>
```

**2. Open a PR against the release branch:**

```bash
git push -u origin fix/handle-token-expiry
gh pr create \
  --base release/0.2 \
  --head fix/handle-token-expiry \
  --title "fix(auth): handle expired OAuth tokens"
```

CI runs on PRs targeting `release/**` branches, so the build is validated before merge.

**3. Merge the PR.**

Once merged, `patch-release.yml` automatically:
- Determines the next patch version from existing tags (e.g., `v0.2.0` → `v0.2.1`)
- Bumps `VERSION` and `pyproject.toml`, commits as `"Release v0.2.1"`
- Tags and pushes, which triggers the full release pipeline

> **Note:** The initial `vX.Y.0` release must be created via `create-release.yml`. The patch-release workflow requires at least one existing tag for the minor version.

### Support Policy

Only the **latest** release branch receives patches. Older release branches are not backported to. Users should always upgrade to the latest version.

---

## Manual Release (without automation)

If the workflows are unavailable, you can perform a release manually:

```bash
# 1. Ensure you're on main and up to date
git checkout main && git pull

# 2. Create the release branch
VERSION="0.2.0"
MINOR="${VERSION%.*}"
git checkout -b "release/${MINOR}"

# 3. Bump versions
echo "$VERSION" > VERSION
# macOS:
sed -i '' "s/^version = \".*\"/version = \"${VERSION}\"/" pyproject.toml
# Linux:
# sed -i "s/^version = \".*\"/version = \"${VERSION}\"/" pyproject.toml

# 4. Commit and tag
git add VERSION pyproject.toml
git commit -m "Release v${VERSION}"
git tag "v${VERSION}"

# 5. Push (triggers release pipeline)
git push origin "release/${MINOR}"
git push origin "v${VERSION}"
```

---

## PR Conventions

Release notes are auto-generated from PR titles, so consistent formatting matters.

### Title format (enforced by CI)

PR titles must follow [Conventional Commits](https://www.conventionalcommits.org/):

```
<type>(<optional scope>): <description>
```

| Type | When to use |
|------|-------------|
| `feat` | New feature or capability |
| `fix` | Bug fix |
| `docs` | Documentation only |
| `style` | Code style changes (formatting, whitespace) |
| `refactor` | Code change that neither fixes a bug nor adds a feature |
| `perf` | Performance improvement |
| `test` | Adding or updating tests |
| `ci` | CI/CD changes |
| `build` | Build system or dependency changes |
| `chore` | Maintenance tasks |
| `revert` | Reverting a previous commit |

Append `!` after the type for breaking changes: `feat!: remove legacy auth flow`

### Size labels

PRs are automatically labeled by size:

| Label | Lines changed |
|-------|---------------|
| `size/XS` | < 100 |
| `size/S` | 100–299 |
| `size/M` | 300–599 |
| `size/L` | 600–999 |
| `size/XL` | 1000+ |

---

## Setup: GitHub App for Releases

The release workflows (`create-release.yml`, `patch-release.yml`) use a GitHub App token to push tags. This is necessary because tags pushed with the built-in `GITHUB_TOKEN` do not trigger downstream workflows (a GitHub Actions security restriction).

### One-time setup

1. **Create a GitHub App** (org admin):
   - Go to **GitHub → Org Settings → Developer settings → GitHub Apps → New GitHub App**
   - **Name:** e.g. `stackloklabs-release-bot`
   - **Permissions → Repository → Contents:** Read & Write
   - No webhook URL required — uncheck "Active" under Webhooks
   - Click **Create GitHub App**

2. **Generate a private key:**
   - On the app's settings page, scroll to **Private keys → Generate a private key**
   - Save the downloaded `.pem` file securely

3. **Install the app** on this repository (or all repos in the org):
   - On the app's settings page → **Install App** → select the org → choose repositories

4. **Add repository secrets:**
   - `MCP_RELEASE_WORKFLOW_APP_ID` — the numeric App ID (shown on the app's General page)
   - `MCP_RELEASE_WORKFLOW_APP_KEY` — the full contents of the `.pem` file

   Add these at **Repo → Settings → Secrets and variables → Actions → New repository secret**.

### How it works

Each workflow run calls `actions/create-github-app-token` to mint a short-lived token (expires in ~1 hour). This token is used for `git push` so that the resulting tag push event triggers `release.yml`. No long-lived PATs are needed.

---

## Workflow Reference

| Workflow | Trigger | Purpose |
|----------|---------|---------|
| `create-release.yml` | Manual (`workflow_dispatch`) | Cut a new minor/major release |
| `patch-release.yml` | PR merged to `release/**` | Auto-create patch releases |
| `release.yml` | Tag push (`v*`) | Build, sign, push container; create GitHub Release |
| `code-checks.yml` | PR, push to `main`, or called by `release.yml` | Orchestrate code quality → image build → Grype security |
| `code-quality.yml` | Called by `code-checks.yml` | Ruff lint, ty typecheck, pytest, bandit, pip-audit |
| `image-build.yml` | Called by `code-checks.yml` | Docker build verification (multi-arch, no push) |
| `security.yml` | Called by `code-checks.yml`, or daily at 2 AM UTC | Grype vulnerability scan (filesystem + image) |
| `lint-pr-title.yml` | PR opened/edited | Enforce Conventional Commits on PR titles |
| `pr-size-labeler.yml` | PR opened/synced | Auto-label PRs by size |
