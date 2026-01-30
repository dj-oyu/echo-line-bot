---
description: Language Server Protocol integration guidelines
globs: ["**/*.py", "**/*.ts", "**/*.tsx"]
alwaysApply: false
---

# LSP Integration Rules

## Core Philosophy

When LSP MCP is available:

1. **Static Analysis First**: Check LSP diagnostics before making changes
2. **Language-Agnostic**: Apply consistent patterns across Python and TypeScript
3. **Real-Time Feedback**: Use LSP for immediate error detection

## Before Code Changes

1. Run LSP diagnostics on target files
2. Understand existing errors/warnings
3. Plan changes to avoid introducing new issues

## During Development

### Use These Features

**Code Intelligence:**
- Hover for type signatures and documentation
- Go to Definition for navigation
- Find References for impact analysis
- Document Symbols for structure overview

**Code Quality:**
- Diagnostics for error/warning detection
- Code Actions for quick fixes
- Signature Help for function parameters
- Completion for accurate code

**Refactoring:**
- Rename Symbol for safe refactoring
- Format Document for consistency

## Before Committing

1. Check all LSP diagnostics
2. Resolve errors (required)
3. Address warnings (recommended)
4. Format documents

## Language-Specific Notes

### Python (lambda/)
- Use type hints for better LSP support
- Ensure imports are resolvable
- Check for undefined variables

### TypeScript (cdk/)
- Leverage strict mode diagnostics
- Use explicit return types
- Check for unused variables/imports
