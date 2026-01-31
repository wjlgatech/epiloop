#!/usr/bin/env bash
#
# sync-upstream.sh - Smart upstream sync for epiloop fork
#
# This script syncs with openclaw/openclaw while preserving epiloop branding

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

# Color output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

log_info() { echo -e "${BLUE}ℹ${NC} $*"; }
log_success() { echo -e "${GREEN}✓${NC} $*"; }
log_warning() { echo -e "${YELLOW}⚠${NC} $*"; }
log_error() { echo -e "${RED}✗${NC} $*"; }

# Check if upstream remote exists
if ! git remote get-url upstream &>/dev/null; then
    log_error "Upstream remote not configured. Run:"
    echo "  git remote add upstream https://github.com/openclaw/openclaw.git"
    exit 1
fi

# Check working directory is clean
if [[ -n "$(git status --porcelain | grep -v '^??')" ]]; then
    log_error "Working directory has uncommitted changes. Commit or stash them first."
    git status --short
    exit 1
fi

log_info "Fetching upstream changes..."
git fetch upstream

# Show what's new
NEW_COMMITS=$(git log --oneline upstream/main ^main | wc -l | tr -d ' ')
if [[ "$NEW_COMMITS" -eq 0 ]]; then
    log_success "Already up to date with upstream!"
    exit 0
fi

log_info "Found ${NEW_COMMITS} new commits in upstream"
echo
git log --oneline --graph upstream/main ^main | head -20
echo

# Interactive confirmation
if [[ "${EPILOOP_AUTO_SYNC:-}" != "1" ]]; then
    read -p "Merge these changes? (y/N) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        log_warning "Sync cancelled"
        exit 0
    fi
fi

# Create backup branch
BACKUP_BRANCH="backup-pre-sync-$(date +%Y%m%d-%H%M%S)"
git branch "$BACKUP_BRANCH"
log_info "Created backup branch: $BACKUP_BRANCH"

# Create merge branch
MERGE_BRANCH="sync-upstream-$(date +%Y%m%d)"
git checkout -b "$MERGE_BRANCH" 2>/dev/null || git checkout "$MERGE_BRANCH"

log_info "Merging upstream/main..."
log_warning "This may take a while and will have conflicts..."

# Attempt merge with custom strategy
if git merge upstream/main --no-edit --strategy-option=patience; then
    log_success "Clean merge!"
else
    log_warning "Merge conflicts detected. Applying epiloop branding..."

    # Auto-resolve branding conflicts
    log_info "Auto-resolving branding conflicts..."

    # Get list of conflicted files
    CONFLICTED_FILES=$(git diff --name-only --diff-filter=U)

    if [[ -z "$CONFLICTED_FILES" ]]; then
        log_success "No conflicts remain!"
    else
        log_info "Resolving conflicts in $(echo "$CONFLICTED_FILES" | wc -l) files..."

        # Strategy: For each conflicted file, check if it's a branding conflict
        # If so, prefer epiloop branding
        while IFS= read -r file; do
            if [[ -f "$file" ]]; then
                log_info "  Processing: $file"

                # Use sed to resolve conflicts favoring epiloop branding in specific patterns
                # This is a simplified heuristic - manual review still recommended
                if grep -q "<<<<<<< HEAD" "$file"; then
                    # Check if conflict is about branding (openclaw vs epiloop)
                    if grep -A 5 "<<<<<<< HEAD" "$file" | grep -qi "epiloop"; then
                        log_info "    → Branding conflict detected, favoring epiloop"
                        # This is complex - marking for manual resolution
                    fi
                fi
            fi
        done <<< "$CONFLICTED_FILES"

        log_warning "Conflicts require manual resolution!"
        log_info "Conflicted files:"
        echo "$CONFLICTED_FILES"
        echo
        log_info "Resolution guidelines:"
        echo "  1. Keep 'epiloop' branding in ALL user-facing files"
        echo "  2. Keep github.com/wjlgatech/epiloop URLs"
        echo "  3. Keep ~/.epiloop config paths"
        echo "  4. Merge upstream logic improvements"
        echo "  5. Keep extensions/claude-loop/* (autonomous coding)"
        echo
        log_info "After resolving conflicts:"
        echo "  git add <resolved-files>"
        echo "  git commit"
        echo "  git checkout main && git merge $MERGE_BRANCH"
        exit 1
    fi
fi

# If we get here, merge was clean or conflicts resolved
log_success "Merge complete!"

# Test the build
log_info "Testing build..."
if pnpm install && pnpm build; then
    log_success "Build successful!"
else
    log_error "Build failed! Review changes before merging to main."
    exit 1
fi

# Optionally run tests
if [[ "${EPILOOP_SYNC_TEST:-}" == "1" ]]; then
    log_info "Running tests..."
    if pnpm test; then
        log_success "Tests passed!"
    else
        log_error "Tests failed! Review changes."
        exit 1
    fi
fi

# Merge to main
log_info "Merging to main..."
git checkout main
git merge "$MERGE_BRANCH" --no-edit

log_success "✨ Sync complete!"
log_info "Backup branch: $BACKUP_BRANCH"
log_info "Merge branch: $MERGE_BRANCH (you can delete it)"
log_info ""
log_info "Next steps:"
echo "  1. Review changes: git log --oneline -10"
echo "  2. Test locally: pnpm epiloop --version"
echo "  3. Push to origin: git push origin main"
echo "  4. Delete merge branch: git branch -d $MERGE_BRANCH"
