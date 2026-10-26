# Audit: dair-ai/Prompt-Engineering-Guide

Source: [github.com/dair-ai/Prompt-Engineering-Guide](https://github.com/dair-ai/Prompt-Engineering-Guide), the Next.js/Nextra site behind promptingguide.ai and the repo backing this session's own `prompt-engineering` skill (79,500-plus stars, actively maintained, MIT). A curriculum and reference site, not a tool, so this audit reads it for citable primary-source backing on exhaust's existing injection-defense and agent-design decisions rather than for new architecture. Read directly via a shallow, blobless clone and a sample of its `risks/adversarial` and `agents/context-engineering` pages, not via subagent fan-out, given the content is prose rather than code.

## Adopted: the field's own admission that instruction-level injection defense has no reliable technique

Folded into [ADR 0009](../adr/0009-untrusted-target-output-is-delimited.md). The guide's own adversarial-prompting page states plainly that telling a model to ignore injected content "is not a complete solution or offers any guarantees," and that no widely accepted technique reliably defeats a text-based prompt injection through instruction alone. It draws the right analogy unprompted: prompt injection resembles SQL injection, and the fix that works there is parameterization, genuinely separate channels for instructions and untrusted input, not relying on a model (or a database driver) to tell them apart inside one blended string. This is a citable, widely-read primary source for exactly the premise already underlying exhaust's design: a delimiter marks the boundary between agent instructions and Target output, but the thing that actually has to hold is the agent's own hardcoded rule to never execute an instruction that arrives inside Target output, not the delimiter or any prompt-level warning on its own.

## Reinforced, not new

**Silent task-skipping without justification is a known, named agent failure mode, independently described outside this project's own audits.** The guide's context-engineering case study on building a research agent names, as its first debugged issue, an orchestrator that silently skips a planned subtask without explicit reasoning, and proposes fixing it by requiring the agent to either execute every planned step or explicitly justify skipping it. This is the same shape as the "errored is not exhausted" distinction already in [ADR 0005](../adr/0005-harness-done-is-a-per-vertical-ledger.md), arrived at independently by a different project working a different problem (research report generation, not a pentest ledger). Also a reminder of that ADR's own lesson about enforcement: the guide's own fix is a system-prompt instruction, not a structural check, which is a textbook instance of the instruction-vs-enforcement gap exhaust's ledger is specifically designed not to repeat.

## Noted, not adopted

**Context-engineering vocabulary (system prompts, task constraints, tool descriptions, memory management, error handling) is a clean checklist for Harness design**, but names nothing exhaust hasn't already settled or isn't already tracking as open (BRIEF.md, ADR 0006; typed Verdicts, ADR 0007; the open Harness-driving-mechanism question from the osmedeus and oss-crs audits). No decision to record; useful vocabulary cross-check only.

## What this settled for exhaust

- [ADR 0009](../adr/0009-untrusted-target-output-is-delimited.md) sharpened with a citable primary source: instruction-level injection defense is field-acknowledged as unreliable, which is why the delimiter must be paired with a hardcoded instruction-source rule, not treated as a defense on its own.
- [ADR 0005](../adr/0005-harness-done-is-a-per-vertical-ledger.md) reinforced by an independent, non-security example of the same silent-skip failure mode and the same instruction-only, unenforced fix that doesn't actually close it.
