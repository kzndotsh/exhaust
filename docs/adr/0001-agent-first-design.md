# Agent-first design

Exhaust's primary user is an AI agent, not a human operator. It scaffolds a self-contained Workspace loaded with tooling, skills, and a Playbook so an agent can autonomously and exhaustively research one Target, looping until the angles are spent.

We chose this over a human-first CLI because the whole point is to send an agent off to exhaust every angle with minimal steering. A human can still drive exhaust directly, but when a design choice trades human ergonomics against agent ergonomics, the agent wins.
