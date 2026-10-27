# exhaust

> **⚠️ Work in progress — design phase, no code yet.** This repository currently holds only the glossary, architecture decisions, and background research produced while designing exhaust. There is no CLI, no Harness, no skills, and nothing runnable. Expect everything here, including terminology, to still change.

Exhaust is an agent-first toolkit for security research. From it you scaffold a self-contained **Workspace** per **Target**, and it provides what an agent needs to probe that Target autonomously and exhaustively: the **Rig** it works from, a library of skills, a methodology checklist, and the **Harness** that drives the agent through it.

To exhaust a Target is to work through every known angle of attack until the options are spent, not to stop at the first finding.

## Where things stand

The project is past the idea-sharpening stage and into recording real architecture decisions, but nothing has been built yet. What exists today:

- **[GLOSSARY.md](GLOSSARY.md)** — the project's vocabulary: Target, Workspace, Sandbox, Rig, Scope Contract, Brief, Finding, Verdict, Oracle, Harness, Disclosure. Read this first; the rest of the docs assume it.
- **[docs/adr/](docs/adr/)** — 22 architecture decision records, covering the Harness's design, how findings are stored and verified, how the Playbook is shaped, and the safety boundaries around testing a real Target.
- **[docs/research/](docs/research/)** — audits of a dozen comparable tools (security-research harnesses, pentest platforms, skill libraries, and one general-purpose agent platform), each distilling what to adopt, what to reject, and why. These are what most of the ADRs are built on.

Not yet decided: the exact Playbook (the full list of verticals an agent works through per Target) and the skills themselves. That's the next piece of design work.

## Core ideas so far

- **A Scope Contract gates any real-Target testing.** With no Scope Contract in a Workspace, the agent is confined to the Sandbox. Reaching a real, remote Target requires one, and its authority can never be satisfied by anything that arrives inside the agent's own context — not a Target's response, not the agent's own text.
- **Findings are append-only claims, not deletable records.** A Finding keeps its original record forever; a later Verdict (confirmed, false-positive, duplicate, fixed, accepted-risk) is recorded on it, never erasing it.
- **A `confirmed` Verdict requires a host-run Oracle**, not just the agent's self-report. This is the one gap found, in some form, in essentially every comparable tool audited so far.
- **The Harness's "done" is an explicit per-vertical ledger**, not a heuristic or the agent's own say-so.

See the ADRs for the full reasoning behind each of these, and the research audits for the evidence they're built on.

## Research

Fourteen repositories have been audited for architecture ideas so far: [deepsec](docs/research/2026-10-26-deepsec-audit.md), [Shannon](docs/research/2026-10-26-shannon-audit.md), [Anthropic's reference harness](docs/research/2026-10-26-defending-code-reference-harness-audit.md), [OWASP ASRH](docs/research/2026-10-26-owasp-asrh-audit.md), [Cloudflare's security-audit-skill](docs/research/2026-10-26-cloudflare-security-audit-skill-audit.md), [cyber-harness](docs/research/2026-10-26-cyber-harness-audit.md), [T3MP3ST](docs/research/2026-10-26-t3mp3st-audit.md), [ScopeSentry](docs/research/2026-10-26-scopesentry-audit.md), [osmedeus](docs/research/2026-10-26-osmedeus-audit.md), [Lynis](docs/research/2026-10-26-lynis-audit.md), [Anthropic-Cybersecurity-Skills](docs/research/2026-10-26-anthropic-cybersecurity-skills-audit.md), and [Cloudflare OS](docs/research/2026-10-26-cloudflare-os-audit.md). Each audit file states plainly what was adopted, what was rejected, and why.

## Responsible use

Exhaust is built around a responsible-disclosure discipline from the ground up — see the Scope Contract and Disclosure concepts in [GLOSSARY.md](GLOSSARY.md). It is meant for testing systems you own or are explicitly authorized to test.
