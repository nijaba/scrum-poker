#!/usr/bin/env bash
# Tags and publishes a release (design.md, "Versions and releases").
#
#   scripts/release.sh 1.2.0
#
# Run it on main, up to date with origin and with nothing uncommitted, once a pull request has
# set `version` in pyproject.toml to that number and been merged. It tags vX.Y.Z, pushes the
# tag, and creates the GitHub Release with notes generated from the merged pull requests.
# Then deploy that tag (README, "Upgrading").
#
# RELEASE_DRY_RUN=1 stops after the checks; tests/test_release.py uses it.
set -euo pipefail

fail() {
  echo "release: $*" >&2
  exit 1
}

version=${1:-}
[[ $version =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]] || fail "give the version as X.Y.Z, such as 1.2.0"
tag="v$version"
cd "${RELEASE_ROOT:-$(dirname "$0")/..}"

[ "$(git branch --show-current)" = main ] || fail "switch to main first"
[ -z "$(git status --porcelain --untracked-files=no)" ] || fail "commit or stash your changes first"
git fetch -q origin main
[ "$(git rev-parse HEAD)" = "$(git rev-parse origin/main)" ] || fail "main differs from origin/main: pull or push first"

declared=$(sed -n 's/^version *= *"\([^"]*\)".*/\1/p' pyproject.toml | head -1)
[ "$declared" = "$version" ] || fail "pyproject.toml says $declared; merge a pull request setting $version first"
if git rev-parse -q --verify "refs/tags/$tag" >/dev/null || git ls-remote --exit-code --tags origin "$tag" >/dev/null; then
  fail "$tag already exists"
fi

echo "Ready to release $tag from $(git rev-parse --short HEAD)."
[ -z "${RELEASE_DRY_RUN:-}" ] || exit 0

git tag -a "$tag" -m "Scrum poker $version"
git push origin "$tag"
gh release create "$tag" --verify-tag --generate-notes --title "Scrum poker $version"
echo "Released $tag. Deploy it with: git fetch --tags && git checkout $tag"
