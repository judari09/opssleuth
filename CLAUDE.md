# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project status

OpsSleuth is a diagnostic tool for critical systems: it aims to reduce error-investigation
time by leveraging observability mechanisms exposed by the target applications. Feature
001 (Recepción de Incidencia — incident intake) and feature 002 (Búsqueda en Archivos de
Logs — log evidence search) are implemented under `src/opssleuth/`: a CLI conversational
agent that captures the initial problem description, maintains conversation context, asks
clarification questions, and — once intake is complete — invites the user to provide log
evidence, locates entries related to the incident via a LangGraph tool-calling agent, and
produces a consolidated initial appreciation. Both flows share a single `BaseChatModel`
built by `crear_modelo_chat()` (`src/opssleuth/llm/factory.py`, Claude or local Ollama). See
`specs/ESTADO_SPECS.md` for the full spec registry — **read it before starting or planning
any new spec** (see "Spec Kit workflow" below). Consult `.specify/memory/constitution.md`
for the governing project principles.

## Commands

- Install dependencies: `uv sync`.
- Run the CLI: `uv run python -m opssleuth.cli` (defaults to the Claude provider; set
  `OPSSLEUTH_LLM_PROVIDER=ollama` + `OPSSLEUTH_OLLAMA_MODEL=<model>` to use a local Ollama
  model instead, or `OPSSLEUTH_LLM_PROVIDER=gemini` + `GOOGLE_API_KEY=<key>` to use Gemini's
  free tier — see `specs/001-recepcion-incidencia/quickstart.md`). Copy `.env.example`
  to `.env` to configure these without exporting them manually — loaded automatically by
  `main()` via `python-dotenv`.
- Run tests: `uv run pytest tests/` (72 tests as of feature 002).

## Constitution (non-negotiable project principles)

The full governing document is `.specify/memory/constitution.md` (v1.0.0). Every code
change, backend or frontend, must satisfy:

1. **SOLID compliance** across all layers — reviews must explicitly check this.
2. **Modular, replaceable architecture** — modules (e.g. an observability-source
   connector, a log analyzer, a correlation engine) must sit behind stable
   contracts/abstractions so they can be swapped or extended without touching
   consumers or the core.
3. **Mandatory docstrings** on every class/function: numpydoc format in backend
   (Python) code, JSDoc format in frontend (JS/TS) code. Missing docstrings block
   approval.
4. **Simplicity over engineering** — no abstraction, layer, or dependency without a
   present, concrete justification; prefer the simplest solution that satisfies the
   actual requirement.

## Spec Kit workflow

This repo uses Spec Kit (`.specify/`) for spec-driven development, integrated via Claude
Code skills under `.claude/skills/speckit-*`. Typical flow: `/speckit-constitution` →
`/speckit-specify` → `/speckit-clarify` → `/speckit-plan` → `/speckit-tasks` →
`/speckit-implement`, with `/speckit-analyze` and `/speckit-checklist` available for
cross-artifact consistency checks. Feature work lands under `specs/[###-feature-name]/`
(spec.md, plan.md, tasks.md, etc.). Every `plan.md` must include a "Constitution Check"
gate verified against the four principles above.

**Before starting or planning any new spec** (`/speckit-specify`, `/speckit-plan`), read
`specs/ESTADO_SPECS.md` first. It is the central registry of every spec's status plus the
architectural decisions, shared contracts, domain entities, and env vars already
established by prior specs — the whole point is to prevent spec drift (contradictory
decisions, duplicated entities/contracts, or silently breaking something an earlier spec
already built). When a spec introduces something future specs need to know about, update
`specs/ESTADO_SPECS.md` in the same turn — not as an afterthought.
