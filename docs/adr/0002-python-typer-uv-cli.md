# Python + Typer + uv for the CLI

The exhaust CLI is written in Python with [Typer](https://typer.tiangolo.com/), and the project is managed by [uv](https://docs.astral.sh/uv/).

Exhaust is a security tool, and the offensive-tooling ecosystem, the PoC scripts it scaffolds, and the disclosure-recon HTTP work are all Python-native. An agent working inside a Workspace therefore writes idiomatic Python by default. Typer gives a first-class CLI for little code, and uv provides reproducible environments and simple distribution, which complements the Nix-first Rig.

## Considered options

Node with [citty](https://github.com/unjs/citty) was the alternative. It was rejected because exhaust ships Claude agent skills (markdown, runtime-agnostic) and shell tools rather than TypeScript or MCP code, so Node's ecosystem advantage did not apply. Revisit only if shipping first-party MCP servers or TypeScript agent tooling becomes a core deliverable.
