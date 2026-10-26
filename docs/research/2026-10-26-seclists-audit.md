# Audit: danielmiessler/SecLists

Source: [github.com/danielmiessler/SecLists](https://github.com/danielmiessler/SecLists). Already in the user's own Nix lab module as the `seclists` package, so this isn't a new Rig component to adopt, it's a quick confirmation pass on a tool already pinned. A pure wordlist/payload data collection (usernames, passwords, fuzzing strings, discovery wordlists, pattern-matching rules, web shells), not a harness or methodology, so no multi-agent audit was warranted; checked directly via a shallow tree listing rather than a full clone, given the repo's size.

## What's there, by category

`Passwords/`, `Usernames/`, `Discovery/` (DNS, file-system, infrastructure, SNMP, and `Web-Content/` with subdirectories per CMS, programming language, and web server), `Fuzzing/` (categorized by injection class: LFI, XSS, databases, amounts, dates, user-agents, 403-bypass), `Pattern-Matching/` (grep rules for auditing PHP source, dangerous Angular functions, PHP magic-hash collisions), `Payloads/`, `Web-Shells/`, and `Ai/`.

## One concrete, usable find: a real prompt-injection dataset

`Ai/LLM_Testing/` carries attributed jailbreak-prompt datasets sourced from a CCS 2024 academic paper (Shen et al., "Do Anything Now"), plus smaller sets for bias testing, data-leakage probing, and divergence attacks. This is a ready, sourced dataset for the prompt-injection gap the PayloadsAllTheThings audit already flagged as having no home in the current spine. Whether that becomes a vertical is a spine-locking decision, not this note's; the point here is that if it does, the data to drive it already exists and is already in the Rig.

## What this confirms, nothing new to decide

`Discovery/Web-Content/CMS` and the language/web-server-specific wordlist directories line up cleanly with the stack-gating idea already settled in ADR 0011: a recon pass identifies the stack, and the right wordlist gets selected for it, rather than every Workspace carrying every wordlist. No ADR needed; this is confirmation that the data this pattern needs already exists and is already pinned in the Rig.
