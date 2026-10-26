# Audit: projectdiscovery/nuclei-templates

Source: [github.com/projectdiscovery/nuclei-templates](https://github.com/projectdiscovery/nuclei-templates). The industry-standard community-curated template catalog (13,200-plus stars, actively maintained, pushed the day of this audit) for the `nuclei` scanning engine: a flat corpus of 14,500-plus YAML checks, mostly data rather than code, so this audit reads as a taxonomy and verification-mechanism survey rather than a code-architecture one. Read directly via a shallow, blobless clone and a sample of real templates and workflows, not via subagent fan-out, since the repository is overwhelmingly declarative data.

## Adopted: a production-grade, real-world instance of our own OOB Oracle mechanism

A sampled CVE template ([CVE-2019-0192](http://github.com/projectdiscovery/nuclei-templates/blob/main/http/cves/2019/CVE-2019-0192.yaml), an Apache Solr deserialization RCE) does not take the scanner's own request as proof of anything. It points a vulnerable config parameter at `{{interactsh-url}}`, an out-of-band callback placeholder, and its matcher requires `contains(interactsh_protocol, "dns")` alongside independent response-shape checks, combined with `and`. This is the exact out-of-band-callback Oracle mechanism named in the verification-gap meta-analysis and already in [ADR 0008](../adr/0008-confirmed-requires-a-host-run-oracle.md), found here not as a design proposal but as a mechanism running in production, today, across one of the most widely deployed scanning engines in the industry. Nothing new to decide; the strongest real-world confirmation yet that this mechanism is both correct and operationally practical at scale, worth recording because every other audited source only argued for it or sketched it, never shipped it this directly.

## New decision

**[ADR 0022](../adr/0022-community-skill-content-is-signed-and-verified-before-use.md): community-contributed skill or template content is signed, and the signature is checked before use.** Every official template in this catalog ends with a cryptographic digest line, generated at publish time and verified by the scanning engine before the template's logic ever runs; a community-submitted template lacking a valid signature is flagged rather than treated as equivalent to a vetted one. Exhaust's skills and templates are executable instruction content, the same supply-chain risk a tampered or malicious template poses to this catalog's users. Not covered by [ADR 0012](../adr/0012-rig-wraps-a-pinned-tool-catalog.md) (pinned tool binaries) or [ADR 0016](../adr/0016-no-hand-maintained-vertical-catalog.md) (no hand-maintained coverage claims); this is the separate, narrower question of integrity for pluggable, potentially community-sourced content.

## Reinforced, not new

**Gate on a confirmed signal, not a keyword guess, now confirmed at industry scale.** This catalog's workflow files (for example `workflows/zimbra-workflow.yaml`) chain a cheap, narrow fingerprinting template first, and only fan out to that product's full template set once the fingerprint actually matches, never on a static keyword or dependency-name assumption. Folded into [ADR 0011](../adr/0011-spine-is-core-plus-gated-modules.md) as independent confirmation, from a tool run against millions of real targets, that our own recon-gated module design is the right shape, not merely the cautious one.

## Noted, not adopted

**A mature, directly reusable taxonomy for the spine's eventual vertical catalog**, still not locked per the user's standing instruction. The top-level `http/` categories (`cves`, `exposed-panels`, `exposures`, `default-logins`, `misconfiguration`, `technologies`, `takeovers`, `token-spray`, `osint`, `iot`, `honeypot`, `fuzzing`, `credential-stuffing`, `cnvd`) and each template's structured `classification` block (CVSS vector and score, CWE ID, EPSS score and percentile, CPE) is a second, independently converged, real-world taxonomy to set alongside the material already gathered from Strix, PayloadsAllTheThings, and Cloudflare's security-audit-skill. No decision yet, by design; added to the pool for when the spine lock happens.

## What this settled for exhaust

- [ADR 0022](../adr/0022-community-skill-content-is-signed-and-verified-before-use.md): new decision, community skill/template content must be signed and verified before use.
- [ADR 0011](../adr/0011-spine-is-core-plus-gated-modules.md) reinforced: gating domain modules on a confirmed recon signal, not a keyword guess, is now confirmed by a scanner run at industry scale, not just by one audited skill library.
- [ADR 0008](../adr/0008-confirmed-requires-a-host-run-oracle.md) unchanged but strongly reinforced: the out-of-band-callback Oracle mechanism is found running in production in the industry's own standard scanner templates, not just argued for.
- Methodology-spine taxonomy material for the eventual (still deliberately unlocked) vertical catalog, independently converging with prior sources.
