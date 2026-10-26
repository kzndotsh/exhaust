# Verdicts are recorded through typed tools, never free prose

When an agent reaches a verdict on a Finding, it records it by calling a structured tool the Harness validates against a schema, not by writing it in a prose response the Harness then has to parse back out. An invalid call is rejected and the agent must retry it.

Both audited tools do this already, and for the same reason. Shannon's prompts state the rule directly: "record the verdict via tool, do not narrate." Deepsec validates every finding with a schema on write and runs a same-session, tool-free repair loop on anything that fails, rather than trusting the model's prose. An autonomous agent's narration is not a reliable place to keep a fact the rest of the system depends on: it can be hedged, contradicted later in the same turn, or simply missed by whatever is meant to read it back out. A typed call is the one representation that is checkable the moment it is made.
