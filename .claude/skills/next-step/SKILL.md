---
description: Picks up the next unfinished step in docs/build-plan.md and works through it test-first
disable-model-invocation: true
---

Work on the next unfinished build step.

1. Read `docs/build-plan.md` and find the first step with unticked boxes.
2. Read the sections of `docs/design.md` that the step names, and its cases in `docs/test-plan.md`.
3. If the step says to ask the owner something, or `CLAUDE.md` lists an open decision for it, ask now and wait.
4. Say in a few lines what you will build and in what order, then wait for a go-ahead.
5. Write the tests for the step's case IDs first, with the ID in each test name, then the code that passes them.
6. Run `pytest` and `ruff check .` and fix what fails.
7. Tick the finished boxes in `docs/build-plan.md`.
8. Summarize: what changed, which cases pass, which Manual or Sandbox cases a person still has to run, and any dependency you added.
