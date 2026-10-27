# Skills use progressive disclosure, not one monolithic file

Each vertical or tool gets a short top-level entry (what it is, when to use it, a pointer to more) and a separate, more detailed doc that only gets loaded into an agent's context when that vertical or tool is actually invoked. No skill tries to carry its entire reference material inline at all times.

cyber-harness's scanner extension does this concretely: a short top-level skill lists what's available, and each tool's full playbook lives in its own doc, loaded through a virtual path only on first invocation of that tool. The alternative, one large skill file covering every vertical and every tool up front, spends context budget on verticals and tools a given Workspace may never touch. With an 11-item (or larger) Playbook, each with its own detailed procedure, that cost compounds quickly across every turn the Harness runs.
