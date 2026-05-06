---
description: Git workflow and commit guidelines
globs: ["**/*"]
alwaysApply: true
---

# Git Workflow Rules

## Branch Strategy

- **main**: Production code deployed to AWS
- **feature branches**: New features (e.g., `feature/add-rich-message-support`)
- **hotfix branches**: Urgent fixes (e.g., `hotfix/webhook-timeout`)

Create pull requests even for solo development to maintain code history.

## Commit Rules

### CRITICAL: Commit Timing

**YOU MUST COMMIT AFTER EVERY SIGNIFICANT CHANGE.**

Commit immediately after:
1. Implementing a complete feature
2. Fixing a bug
3. Refactoring code
4. Adding/updating documentation
5. Infrastructure changes (CDK)
6. Configuration updates

**NEVER leave uncommitted changes between work sessions.**

### Commit Message Format

```
type(scope): description
```

- **type**: feat, fix, refactor, docs, test, chore
- **scope** (optional): lambda, cdk, docs
- **description**: imperative mood, lowercase, no period

### Good Examples
- `fix: handle empty webhook body gracefully`
- `feat(lambda): add support for image message handling`
- `refactor(cdk): extract secret references to separate method`
- `docs: update architecture diagram`

### Bad Examples
- `fix stuff` (too vague)
- `add feature and fix bugs` (multiple changes)
- `work in progress` (incomplete work)
- `Fixed the bug.` (wrong case, period)

## Pre-commit Checks

Before committing:
1. Run `pnpm test` in cdk/ directory
2. Check for LSP errors/warnings
3. Verify no secrets in staged files
