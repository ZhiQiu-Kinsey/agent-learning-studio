# Documentation

**English** · [简体中文](README.zh-CN.md)

Chinese is the source language of the project. Where a document has an English version, the English file is a translation; if the two disagree, the Chinese version is authoritative.

## Start here

| Document | What it covers | Languages |
| --- | --- | --- |
| [README](../README.md) | What the project is, setup, configuring a model provider | [English](../README.md) · [中文](../README.zh-CN.md) |
| [CONTRIBUTING](../CONTRIBUTING.md) | How to contribute: red lines, checks, commits and pull requests | [English](../CONTRIBUTING.md) · [中文](../CONTRIBUTING.zh-CN.md) |
| [AGENTS.md](../AGENTS.md) | Project rules for people and coding agents: red lines, commands, writing conventions | Chinese |
| [Course plan](course-plan.en.md) | The full syllabus, generated from `curriculum/catalog.json` | [English](course-plan.en.md) · [中文](course-plan.md) |

## Architecture and author guides

All in [architecture/](architecture/).

| Document | What it covers | Languages |
| --- | --- | --- |
| [Platform](architecture/platform.en.md) | Architecture, current boundaries and the long-term course design | [English](architecture/platform.en.md) · [中文](architecture/platform.md) |
| [Frontend workspace](architecture/frontend-workspace.en.md) | Frontend structure: pages, modules, honesty rules for the UI, motion, UI text and languages | [English](architecture/frontend-workspace.en.md) · [中文](architecture/frontend-workspace.md) |
| [Event envelope v2](architecture/event-envelope-v2.en.md) | Run events, spans, the run store and SSE resumption | [English](architecture/event-envelope-v2.en.md) · [中文](architecture/event-envelope-v2.md) |
| [Multi-provider review](architecture/multi-provider-review.en.md) | Raw HTTP and LiteLLM model access, and how execution evidence is labeled | [English](architecture/multi-provider-review.en.md) · [中文](architecture/multi-provider-review.md) |
| [Adding lessons](architecture/adding-lessons.en.md) | Scaffolding a lesson, manifests, content v2, pacing and code-reading rules, the multilingual runtime, custom runners and pages | [English](architecture/adding-lessons.en.md) · [中文](architecture/adding-lessons.md) |
| [Localizing a lesson](architecture/localizing-lessons.en.md) | Checklist for a bilingual runtime and the English overlay, pitfalls, English style | [English](architecture/localizing-lessons.en.md) · [中文](architecture/localizing-lessons.md) |
| [Terms and code names](architecture/terminology.en.md) | Glossary rules, code notes, the unified wording table, checks on English text | [English](architecture/terminology.en.md) · [中文](architecture/terminology.md) |
| [Validation](architecture/validation.en.md) | Which tests and validators exist and how to run them | [English](architecture/validation.en.md) · [中文](architecture/validation.md) |
| [Reference study](architecture/reference-study.en.md) | Pinned reference tutorials, licenses, reading scope and what each lesson borrowed | [English](architecture/reference-study.en.md) · [中文](architecture/reference-study.md) |

## Historical records (Chinese only)

These documents record research, plans and source notes from the time they were written. They are kept for traceability and are not translated. Where they disagree with the documents above, the documents above describe the current state.

| Document | What it records |
| --- | --- |
| [curriculum-research.md](architecture/curriculum-research.md) | Research comparing reference tutorials, and the constraints it set for the redesign (2026-10-01) |
| [redesign-plan.md](architecture/redesign-plan.md) | The five-phase platform redesign, completed 2026-10-02 |
| [curriculum-plan-2026-10.md](architecture/curriculum-plan-2026-10.md) | Implementation order and per-lesson decisions for the October 2026 curriculum work |
| [content-depth.md](architecture/content-depth.md) | The 2026-10-04 content audit and the depth rules for explanations that followed from it |
| [onboarding-sources.md](architecture/onboarding-sources.md) | Sources and scope of the "Before you start" onboarding chapters |
| [chapter2-sources.md](architecture/chapter2-sources.md) | Sources and choices for chapter 2 |
| [context-state-sources.md](architecture/context-state-sources.md) | Sources for `messages-context` and `application-state` |
| [budget-memory-sources.md](architecture/budget-memory-sources.md) | Sources for `context-budget`, `context-compaction`, `persistent-memory` and `memory-lifecycle` |

## Project policies

| Document | Languages |
| --- | --- |
| [SECURITY.md](../SECURITY.md) | English |
| [CODE_OF_CONDUCT.md](../CODE_OF_CONDUCT.md) | English |
| [THIRD_PARTY_NOTICES.md](../THIRD_PARTY_NOTICES.md) | Chinese |
