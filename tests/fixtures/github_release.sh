#!/usr/bin/env bash

set -eu

source ./prologue.vars
source /scripts/common.sh

# gh and git-cliff here use GITHUB_TOKEN, exported by the release step's connect_github.
repo="AI21Labs/$GIT_REPO"

create_github_release() {
    local notes
    notes=$(run_git_cliff --latest --strip all)

    gh release create "$NEXT_APP_VERSION" \
        --title "Release $NEXT_APP_VERSION" \
        --notes "$notes" \
        --repo "$repo"
}

post_release_comment_on_pr() {
    local sha pr_number release_url comment_body

    sha=$(git rev-parse HEAD)

    # The PR this commit was merged from (empty for direct pushes to master).
    pr_number=$(gh api "repos/$repo/commits/$sha/pulls" -q '.[0].number // empty')
    [ -z "$pr_number" ] && return 0

    release_url=$(gh release view "$NEXT_APP_VERSION" --repo "$repo" --json url -q .url)
    comment_body="## Release (merge to master)

| Item | Value |
|------|--------|
| **Version** | \`${NEXT_APP_VERSION}\` |
| **Helm** | \`${NEXT_HELM_VERSION}\` |
| **Docker** | \`${AR_DOCKER_REPO}/${GIT_REPO}:${NEXT_APP_VERSION}\` |
| **Release** | [GitHub Release](${release_url}) |"

    gh pr comment "$pr_number" --repo "$repo" --body "$comment_body"
}

create_github_release
post_release_comment_on_pr
