---
description: Use when generating code, modifying existing code, reviewing pull requests, suggesting dependencies, or answering technical implementation questions. Enforce latest stable dependencies, modern APIs, and up-to-date implementation patterns.
---

Provide project context and coding guidelines that AI should follow when generating code, answering questions, or reviewing changes.

## Core Rules

- Always prefer the latest stable dependencies, frameworks, and tooling available at the time of work.
- Do not pin to old, arbitrary, or deprecated versions unless the user explicitly requests a version.
- When a version must be mentioned, prefer the newest stable release and avoid hardcoding outdated versions.
- Use the most up-to-date language features, framework patterns, and APIs available.
- Avoid deprecated functions, legacy syntax, and obsolete implementation patterns unless required for compatibility.

## Freshness and Research Requirements

- At the start of every project or coding task, use the current date as the working reference date.
- Unless the user explicitly asks for older behavior or legacy compatibility, generate code that is current as of today.
- Before initially developing code, perform a web search across:
  - official documentation
  - public Git repositories
  - current community examples when needed
- Use the latest authoritative sources to confirm APIs, package usage, configuration, and best practices.
- Prefer official documentation over third-party tutorials when sources conflict.

## Code Quality Expectations

- Favor modern, maintainable, production-ready code.
- Keep dependencies minimal and current.
- Refactor outdated code to modern equivalents when safe and appropriate.
- If a requested approach depends on deprecated APIs, propose the modern replacement first.
- If compatibility constraints are unknown, assume the latest supported stack unless the user says otherwise.

## Review Behavior

- When reviewing changes, check for outdated dependency usage, deprecated APIs, and version drift.
- Flag places where newer stable APIs or patterns should replace older ones.
- Ensure all generated code aligns with current best practices and the latest documented behavior.