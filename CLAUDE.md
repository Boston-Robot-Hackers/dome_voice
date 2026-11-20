# CLAUDE.md

This file provides guidance to Claude Code when working with code in this repository.

Read and follow all rules in the `.claude/` folder:
- @.claude/process.md — development workflow, feature/task tracking rules, and
  agent model selection
- `process/02-doc/current.md` — session handoff; only the `## Open` section
  matters for new work, see `process/02-doc/history.md` for the completed-work
  log
- `process/02-doc/notes.md` — semi-permanent project notes

Before writing or reviewing code, read and follow `.claude/style_guide.md`
(coding standards, style rules, and review checklist) — apply it yourself
before committing; do not substitute a generic/plugin review for it.

We are developing dome_voice, the DOME robot's voice package: a ROS-free core
library plus ROS nodes (wake word, fixed-grammar or LLM commands, speech). All process files live under
`process/`: literate docs in `process/01-literate/`, project docs in
`process/02-doc/`, features in `process/03-features/`, tasks in
`process/04-tasks/`, issues in `process/05-issues/`, and the spec at
`process/02-doc/spec.md`.

## Commands

A ROS 2 (kilted) `ament_python` package, built with colcon; Python deps come
from pip, not `uv`. From the repo root:

- Tests: `python3 -m pytest test/`
- Lint: `ruff check <files>` and `ruff format <files>`, on changed files only.
- Build, so the robot runs the change: `colcon build --packages-select dome_voice`
  in `/home/pitosalas/ros2_ws`.

## Session Start

At session start, read `process/02-doc/current.md`'s `## Open` section for status and
next steps. If it is unreadable, fall back to `git log --oneline -15` and say
so. (The `/start` skill already does this in more depth — use it when
available; this is the fallback.)

## Workflow & Approval Gates

Do not run tests, commits, or multi-file changes until the user has explicitly
approved the plan. Present the plan, wait for "go", then execute. Never jump ahead
of a process gate.

- **Stuck-loop rule**: if the same tool call fails or returns unchanged output
  twice, stop retrying. Report the failure, what was tried, and a proposed
  workaround (e.g. `cat` via Bash instead of Read), then wait for direction.

## Accuracy Rules

Never state a fact about the environment (model backend, Docker availability,
schema semantics, file existence) from naming conventions or inference. Read the
config/file first, then state the finding and cite the source. If you cannot
verify, say "unverified" explicitly.

## Environment & Data Access

This checkout may not include required credentials or data files. Before any
live external-system or data-extract work, check for these and stop with a
short list of what's missing instead of improvising.

## Hazards before any edit

- The robot runs the **installed** package and `voice.yaml`: edits do nothing there until `colcon build`.
- The mic opens only once: a leftover `voice_input` or test script holding it makes the next one fail.
- `config/voice.yaml` must be committed with `record_dir: none` (a test checks it).
- The VM is a separate machine at the same paths; it gets changes only by `git pull` and a rebuild.

## Write Safety

Treat any live external system (database, API, SaaS platform) as read-only by
default. Do not write, update, or delete data through a live integration
unless the user has explicitly approved it. If the project has a dedicated
read-only client/wrapper, use it exclusively — do not construct or reach
through to the raw client elsewhere. If a task seems to need a write, stop
and ask; it is rarely the right default.

## Tone

No flattery, no praise openers ("Great question!", "You're absolutely right").
Lead with the answer or the finding. Be direct and terse.
