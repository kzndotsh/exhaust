# New dependency versions wait out a cooldown window before adoption

Exhaust's own dependency resolution does not pick up a package version the moment it's published; it waits a short window (on the order of a few days) before treating a new release as eligible, the same way a lockfile pin would, but applied as a rolling policy rather than a one-time pin.

A competing tool in this space adopted exactly this (a five-day `uv` cooldown) after a real incident: a popular LLM-provider library published a poisoned release, and the cooldown window meant their build never picked it up. A newly published package version is the least-scrutinized version that will ever exist; most supply-chain compromises are caught and pulled within days, and a short wait costs nothing but a few days of latency on routine updates while meaningfully reducing the chance of installing a release that hasn't survived first contact with the wider ecosystem yet.
