# Web Outline Smoke Test and Context Slimming Design

Date: 2026-05-27
Status: Approved design, pending implementation plan

## Context

The Web UI already has outline generation, chapter generation, and outline-stage debug hooks. What is still missing is a reliable way to verify the full Web flow with a real model and a disciplined way to reduce avoidable prompt waste after we see the logs.

The user goal is specific:

- run the Web flow from project creation through outline generation and first chapter generation
- use a faster real model for verification, preferably DeepSeek
- inspect the debug output for repeated or useless content
- slim the chain so later stages do not carry unnecessary repeated text or irrelevant forward context

This is not a request to redesign the workflow. It is a verification-first performance pass on the existing pipeline.

## Chosen Approach

Use a two-phase change set:

1. Add or formalize a Web end-to-end smoke path that can run with a real provider, ideally DeepSeek, so the outline-to-chapter-1 path can be exercised without manual log inspection.
2. Use the outline-stage diagnostics and the current artifact model to trim duplicated forward inputs, while preserving each stage's contract and editable decision shape.

The intent is to shorten prompts where the same information is already available in a smaller form, not to remove required worldbuilding, chapter planning, or lock-state context.

## What The Smoke Run Must Prove

The smoke path should verify a single realistic sequence:

- create or load a Web project
- ensure the project has an initial idea or onboarding state
- generate at least one outline stage path through the normal Web API
- generate the first chapter from the resulting outline state
- persist the expected artifacts to `projects/<project>/`
- write outline-stage diagnostics that expose prompt-size and context-size data

The smoke path should be usable with a real provider configuration. DeepSeek is the preferred provider for this pass because it is faster than the default real-model path in this repository.

## Diagnostics Contract

The outline-stage diagnostic record should stay compact and answer the performance questions directly. One JSONL entry per run is enough.

Required fields:

- `created_at`
- `project_id`
- `stage`
- `mode`
- `instruction_chars`
- `author_craft_chars`
- `previous_stage_context_chars`
- `current_stage_context_chars`
- `role_prompt_count`
- `role_prompt_chars`
- `synthesizer_prompt_chars`
- `output_chars`
- `structure_repair_triggered`
- `elapsed_ms`
- `status`
- `error`

If it is cheap to add, include a compact `context_sources` array with `{name, chars}` entries for the major inputs that were actually fed into the stage. That should help distinguish:

- stage summary / stage memory
- full previous-stage Markdown
- current artifact text
- author craft brief
- framework guidance
- user instruction

The diagnostics should not store full prompts or long source text.

## Context Slimming Rules

The optimization should start from evidence in the diagnostics, not from a blanket prompt rewrite.

Preferred rules:

- if a prior stage already has a useful summary and `stage_memory`, use those first
- only include full previous-stage Markdown when the next stage needs exact wording or structure
- do not pass the same information through both `synthesis` and `summary` unless there is a clear reason
- do not keep old editor notes, stale user requests, or unrelated stage content in the forward context
- keep structure contracts, lock constraints, and current-stage editable instructions

For outline generation, the main savings should come from reducing duplicated forward context. For revision flows, the main savings should come from sending only the current artifact plus the precise revision instruction, not the whole historical narrative again.

## Scope

In scope:

- a real-provider Web smoke path for outline generation through first-chapter generation
- outline-stage diagnostics that expose prompt and context sizes
- focused trimming of outline-stage context construction
- tests or smoke checks that validate the new diagnostic data and preserve artifact output
- documentation updates in `docs/IMPLEMENTATION_PLAN.md` and `docs/SESSION_SUMMARY.md` during implementation

Out of scope:

- a new performance dashboard
- database-backed metrics
- a fast/full generation mode split
- changing stage contracts or the overall outline workflow semantics
- unrelated frontend redesign

## Testing Plan

Verification should cover both the smoke path and the smaller unit surfaces.

Expected checks:

- a real-provider Web smoke run completes outline generation and chapter 1 generation
- the outline-stage diagnostic JSONL file is written for each run
- the diagnostic record captures the stage-size and prompt-size fields above
- context-building tests confirm that prior-stage summaries and stage memory are preferred over repeated full Markdown when the stage does not need exact source text
- the relevant Python tests pass, plus any Web build check already used by the project

## Risks

The main risk is trimming too aggressively and losing a constraint that later stages actually need. The safe guardrail is to keep the stage contracts intact and only shorten the repeated material around them.

The second risk is treating the smoke run as a unit test when it really depends on live model availability. The implementation should therefore separate:

- deterministic unit coverage for context construction and diagnostics payloads
- a live smoke path for the real DeepSeek-backed Web flow

