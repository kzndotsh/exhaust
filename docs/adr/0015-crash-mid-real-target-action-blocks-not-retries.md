# A crash mid-real-Target action blocks for review, it does not silently retry

If the Harness crashes or loses state while an action against a real (non-Sandbox) Target was in flight and its outcome is ambiguous, that action's status becomes blocked, requiring a human to look at it before anything resumes. It is never silently retried.

Exhaust's general resumability principle is to converge cleanly on restart (per the idempotent-operations principle). That's the right default for Sandbox work, where re-running a check has no real-world cost. It's the wrong default for an action against a real, authorized Target: blindly re-firing an attack whose prior outcome is unknown could repeat a destructive action, trip a rate limit or alerting threshold a second time, or otherwise cause more harm than simply stopping would. The one place a real Target is touched at all is exactly the one place a crash should make the Harness more cautious, not less.
