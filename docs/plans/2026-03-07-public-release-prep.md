# Public Release Prep Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Prepare the repository for public use by adding baseline public-facing documentation and removing the personal email address from git history.

**Architecture:** Keep the source tree unchanged except for `README.md` and `LICENSE`, then perform a non-interactive history rewrite that swaps the Gmail author/committer email for the existing GitHub noreply address. Verify locally first, then force-push the rewritten `main` branch.

**Tech Stack:** Git, GitHub CLI, Markdown, pytest

---

### Task 1: Add public-facing repository files

**Files:**
- Create: `README.md`
- Create: `LICENSE`

**Step 1: Write the README**

Describe the repository purpose, layout, and basic verification commands.

**Step 2: Add the MIT license**

Use the standard MIT license text with the current copyright holder and year.

**Step 3: Review the files**

Run: `sed -n '1,220p' README.md LICENSE`
Expected: content is present and readable

### Task 2: Rewrite commit email metadata

**Files:**
- Modify: git history metadata only

**Step 1: Rewrite author and committer email**

Run a non-interactive history rewrite that changes `jakub.czakaj@gmail.com` to `22999250+jc1122@users.noreply.github.com` across all refs.

**Step 2: Set local git config for future commits**

Run:

```bash
git config user.email 22999250+jc1122@users.noreply.github.com
git config user.name jc1122
```

Expected: future local commits use the noreply address.

**Step 3: Verify rewritten history locally**

Run: `git log --format='%h %an <%ae>' --all`
Expected: no commits show `jakub.czakaj@gmail.com`

### Task 3: Verify and publish rewritten history

**Files:**
- Test: `tests/test_check_skill_requirements.py`

**Step 1: Run the test suite**

Run: `pytest -q`
Expected: all tests pass

**Step 2: Confirm remote repository state**

Run GitHub API checks for repo visibility and current commit author metadata.

**Step 3: Force-push the rewritten branch**

Run: `git push --force-with-lease origin main`
Expected: remote branch updates cleanly

**Step 4: Re-verify**

Run remote checks again.
Expected: repo remains public and new history no longer exposes the Gmail address
