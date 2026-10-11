# AgentStart: current course sources and teaching trade-offs

**English** · [简体中文](reference-study.md)

> Translated from the Chinese original; if they disagree, the Chinese version is authoritative.

Last updated: 2026-10-04. The reference sources for the course are the formal tutorials in the table in section 1. The pinned versions and reading scopes exist so that what was actually borrowed can be checked; the lesson explanations and Python experiments are written by this project.

## 1. Pinned reference snapshots

| Tutorial | Pinned commit | License | Main use |
| --- | --- | --- | --- |
| [Microsoft AI Agents for Beginners](https://github.com/microsoft/ai-agents-for-beginners) | `25b7985f3b2dc37a84f4a7387ccd3c9f0e5b1595` | MIT | Borrowed learning objectives, topic modules, the continuous teaching-assistant project, and the habit of acceptance by newly added capability. |
| [Hugging Face Agents Course](https://github.com/huggingface/agents-course) | `b3946b1d09d29c65736e219d48a8a736a2c52154` | Apache-2.0 | Borrowed the layered structure (basics to frameworks, scenario practice, evaluation), the optional framework branches, and the breakdown of State/Node/Edge and the RAG flow. |
| [深入理解 AI Agent：设计原理与工程实践](https://github.com/bojieli/ai-agent-book) (Understanding AI Agents: Design Principles and Engineering Practice) | `b789c97a8f3de5b405a6f6dfa8289208d679d0b8` | Apache-2.0 | Fills in task acceptance, context experiments, tool contracts, independent validators, the run lifecycle, cost, and multi-agent engineering trade-offs. |
| [Hello-Agents](https://github.com/datawhalechina/hello-agents) | `4b014ad47e2658af24b59f21e7bdb3f89a66205e` | CC BY-NC-SA 4.0 | Only chapter organization and the order of explanation are borrowed; no text, code or figures are copied (see section 8). |
| [mini-swe-agent](https://github.com/SWE-agent/mini-swe-agent) | `04d809ceab9df28f9adaed044884180159172930` | MIT (the repo's `LICENSE.md`, Copyright (c) 2025 Kilian A. Lieret and Carlos E. Jimenez) | Borrowed the approach of "text actions + strict parsing + a minimal agent loop", used for the text-actions lesson and the "workflow or agent" explanation in section 8. Only the structure is borrowed; no code is copied (see section 8). |

The reference tutorials take no part in running the platform. Files that were not read are not counted in the reading scope. When source code or text is reused, the corresponding license and copyright notices must be kept.

## 2. Microsoft: borrowing the topic catalog, objectives and the continuous project

The root has `00-course-setup` and lessons 01–18: concepts, frameworks, design patterns, tools, agentic RAG, trustworthiness, planning, multi-agent, reflection, production, protocols, context engineering, memory, Microsoft Agent Framework, browser, deployment, local agents, security.

What was actually viewed: `04-tool-use/README.md`, the tool sample directory, the file organization of `05-agentic-rag` and `13-agent-memory`, and the root `STUDY_GUIDE.md`. The course uses README explanations, learning objectives, videos and Python notebooks; the main runtime stack in the current README is Microsoft Agent Framework / Microsoft Foundry.

The most worthwhile things to borrow are clear learning objectives, an independent directory per lesson, and the continuous project in the study guide: after each lesson, answer "what did my agent gain?" We keep the existing `lessons/lesson_NN_*` layout, and each lesson contains:

1. Prerequisites, objectives and one verifiable question.
2. The actual Python entry point, tools and any required data.
3. A default success case and at least one boundary case.
4. An observation checklist: in which request, response or state the evidence should be found.
5. Exercises and pass criteria; having read the page does not mean mastery.

We keep Bailian and plain Python as the foundation, and for now do not introduce an Azure account, the Foundry service or the full notebook runtime dependencies. Cross-language notebooks can serve as extended reading without adding environment burden at the beginner stage.

## 3. Hugging Face: borrowing the stages, framework branches and evaluation loop

`units/en/_toctree.yml` and the related English units were read:

- Unit 1: agents, LLMs, messages, tools, the action/observation loop, with quizzes and practice.
- Unit 2: three framework branches — smolagents, LlamaIndex, LangGraph.
- Unit 3: building an agentic RAG scenario with tools.
- Unit 4: the final project and benchmark evaluation.
- Bonus Unit 2: traces/spans, latency, cost, errors, and offline/online evaluation.

`unit2/langgraph/building_blocks.mdx` breaks orchestration down into State, Node, Edge and StateGraph, which maps one-to-one onto our native Python state dicts, functions and conditional branches. `unit4/hands-on.mdx` shows a question set, answer submission and a scoring API; for now we borrow the repeatable question set and explicit scoring criteria, and decide later separately whether to join an external leaderboard.

Our teaching order builds the native loop first, then compares frameworks on the same task, so that skill with a framework's API is not mistaken for understanding of how agents work. Evaluation is not saved for the last lesson: tool selection, dependency order and error handling can be checked from the first stage.

## 4. 《深入理解 AI Agent》: mechanisms and engineering verification

From the pinned snapshot we draw on its treatment of the model, the run layer and the environment boundary, task acceptance, tool contracts, context compaction, persistent memory, cost, and multi-agent engineering trade-offs. For the chapters actually read, see [Chapter 2 sources](chapter2-sources.md), [Messages and state sources](context-state-sources.md) and [Budget and memory sources](budget-memory-sources.md). Companion experiments that have not been reproduced are not treated as capabilities the platform already has.

## 5. Platform and course boundaries

The platform uses React + TypeScript + Vite, FastAPI and local Python. Lessons follow "concept → minimal implementation → run evidence → experiment → self-check". Framework lessons re-check APIs and dependencies when they are produced; running and replay stay separate, and replay generates no new requests.

Currently 24 lessons are runnable across four units: "native foundations", "tasks and interfaces", "context and state" and "reasoning and control patterns" (sources are in section 6 and in each unit's source documents); the remaining lessons stay planned. The course catalog is maintained in one place, `curriculum/catalog.json`. For the implementation approach see the [guide to adding lessons](adding-lessons.en.md); for full acceptance see [Development verification](validation.en.md).

## 6. Sources for the new reasoning-and-control-pattern lessons (2026-10)

The "reasoning and control patterns" category was written according to decision 1 in section 9 of `curriculum-research.md`. Each lesson lists only the files actually read; pinned versions follow the snapshots in section 1 and section 1 of `curriculum-research.md`. Prompts, parsers, fixtures and experiments are written by this project; no code from the reference projects is copied.

| Lesson | Source and pinned version | Actually read | What was borrowed |
| --- | --- | --- | --- |
| 13 `text-actions` | Hugging Face Agents Course `b3946b1` (Apache-2.0) | `units/en/unit1/actions.mdx`, `units/en/unit1/dummy-agent-library.mdx` | The stop-and-parse way of teaching; the phenomenon that "without a stop sequence the model writes the Observation itself". This lesson substitutes a local grade sheet, strict parsing and a side-by-side record of fabricated content |
| 14 `todo-planning` | learn-claude-code 2026-10 shallow clone `ce8f9f1` (MIT) | `docs/zh/s03-todo-write.md`, `agents/s03_todo_write.py` (in this numbering TodoWrite is s03 and s05 is skill loading; the same commit also has a directory-organized `s05_todo_write/` with different chapter numbers — do not mix the two numberings) | todo_write replaces the whole list, only one item in progress at a time, and the run layer reminds after several rounds without an update. This lesson turns the reminder into a separate user message after the tool message in the OpenAI-compatible format, and adds an independent acceptor |
| 15 `plan-and-replan` | Microsoft AI Agents for Beginners `25b7985` (MIT) | `07-planning-design/README.md` (read via the raw URL at the pinned commit) | Task decomposition, representing the plan as structured output, and iterative planning when subtask results affect later steps. This lesson turns it into a planner / executor split for a single agent, with fixed faults, a revision limit and version diffs |
| 16 `reflection-revision` | Microsoft AI Agents for Beginners `25b7985` (MIT) | `09-metacognition/README.md` (read via the raw URL at the pinned commit) | Self-evaluation and correction, and the role of external feedback. This lesson makes the "external feedback" a really executed test case, and adds an iteration limit and a stop reason |
| 17 `workflow-patterns` | claude-cookbooks 2026-10 sparse clone `d7265d6` (MIT) | `patterns/agents/basic_workflows.ipynb` | The division into three workflows: prompt chaining, parallelization and routing. In the original example the router errors on an unknown label and there is no check between steps; this lesson adds check gates, a fallback record, a labelled comparison and server-side timing |
| 18 `orchestrator-evaluator` | claude-cookbooks `d7265d6` (MIT) | `patterns/agents/orchestrator_workers.ipynb`, `patterns/agents/evaluator_optimizer.ipynb` | The role split of the two patterns. In the originals the workers run serially, the evaluation loop has no limit and parsing uses XML; this lesson uses parallel workers (paired by branch), `max_iters`, a front-loaded format check and a call ledger |

## 7. Sources for the second batch of new lessons and split lessons (2026-10-03)

| Lesson | Material | What was used | What this lesson does |
| --- | --- | --- | --- |
| `chat-request`, `multi-turn-history`, `sampling-variance` | Hugging Face Agents Course `b3946b1` (Apache-2.0) | The message-role and generation concepts in `units/en/unit1/messages-and-special-tokens.mdx` and `what-are-llms.mdx` | Only the order "look at messages and generation first, then teach agents" is borrowed; the requests, comparisons and reports of the three lessons are written by this project, and conclusions come only from real runs |
| `tool-proposals` | Microsoft AI Agents for Beginners `25b7985` (MIT) | The tool definition and calling flow in `04-tool-use/README.md` | Splits "the model proposes a call" and "the program executes it" into two lessons; this lesson only observes proposals and executes nothing |
| `prompt-caching` | Provider docs (checked 2026-10-03): [Bailian context cache](https://help.aliyun.com/zh/model-studio/context-cache), [DeepSeek cache](https://api-docs.deepseek.com/guides/kv_cache), [Anthropic prompt caching](https://platform.claude.com/docs/en/docs/build-with-claude/prompt-caching) | The cache field names in each provider's usage | Used only for field normalization; the text states no concrete numbers such as minimum length or validity period, hits are whatever the response actually reports, and "not reported" is never recorded as 0 |
| `skills-disclosure` | — | — | The 4 skill files and the comparison experiment are written by this project; the idea of "a catalog plus on-demand loading" is common industry practice, and no upstream text is reused |
| `context-compaction`, `memory-lifecycle` | Inherit the sources of former lessons 9 and 10 before the split, see [Reference scope for context budget, compaction and persistent memory](budget-memory-sources.md) | — | The split added no new external material |

We also consulted the course organization of [Hello-Agents](https://github.com/datawhalechina/hello-agents) (`4b014ad`, CC BY-NC-SA 4.0): a fixed way of teaching each paradigm, code split into blocks by responsibility, and layered self-checks. That license forbids commercial use and requires share-alike, so only the organizing idea is borrowed; no text or code is reused. Section 8 records the specific reading scope used when expanding the onboarding.

## 8. Sources for the "Before you start" onboarding and the expansion of all lesson explanations (2026-10-04)

This section records the reading scope before the expansion. The onboarding covers where agents come from, how an LLM works, the model's limits, what an agent is made of, and workflow versus agent; the lessons deepen their concept explanations. The pinned versions are in the table below and match section 1. The onboarding's own earlier sources are in [Onboarding chapters: sources and trade-offs](onboarding-sources.md) and are not repeated here.

- What is registered here is the range each writing step actually used; if a file ended up not being read, it is removed from the table and does not count as borrowed. The pinned versions were all checked with `git rev-parse` and `git cat-file -e <commit>:<path>`.
- Explanations, illustrations, code, fixtures and experiments are all rewritten by this project; no text, code or figures from the reference projects were copied.
- Two ways of borrowing:
  - **Borrowing structure:** take only the chapter order, the way questions are asked, how examples are arranged and how concepts are divided, and rewrite them in our own words with our own run evidence.
  - **Adapting and reusing with attribution:** allowed only when the license is MIT or Apache-2.0. Adapted passages are registered here with their source, and the copyright notice and license text are added to `THIRD_PARTY_NOTICES.md`. There are currently no such passages.
- `THIRD_PARTY_NOTICES.md` lists only upstream code and resources that were copied or adapted. Every source in the table below is "borrowing structure" and does not go into that list.

| Material | Pinned version | License | Registered reading scope | How it was borrowed and what for |
| --- | --- | --- | --- | --- |
| [Hello-Agents](https://github.com/datawhalechina/hello-agents) | `4b014ad47e2658af24b59f21e7bdb3f89a66205e` | CC BY-NC-SA 4.0 (the repo's `LICENSE.txt`) | `docs/前言.md`; `docs/chapter1/第一章 初识智能体.md`, `docs/chapter2/第二章 智能体发展史.md`, `docs/chapter3/第三章 大语言模型基础.md`, `docs/chapter4/第四章 智能体经典范式构建.md` (Chinese edition) | Borrowing structure: chapter organization and order of explanation — question-driven, an example that runs through the chapter, and a ladder of rising capability. The license forbids commercial use and requires share-alike, so no text, code or figures are copied, and its paragraphs are neither translated nor closely paraphrased |
| [Microsoft AI Agents for Beginners](https://github.com/microsoft/ai-agents-for-beginners) | `25b7985f3b2dc37a84f4a7387ccd3c9f0e5b1595` | MIT | `01-intro-to-ai-agents/README.md`, `04-tool-use/README.md`, `07-planning-design/README.md`, `08-multi-agent/README.md`, `09-metacognition/README.md`, `13-agent-memory/README.md`, `STUDY_GUIDE.md` (the `code_samples/` and `images/` of each lesson are not read or used). The local clone is sparse, so these directories may not be checked out; read them at the pinned commit with `git show` or a raw URL. File existence was verified with `git cat-file -e` | Borrowing structure: the conceptual division of "what is an agent and which scenarios suit one" and how the components are listed, plus the explanation scope of tools, planning, multi-agent, metacognition and memory; wording and examples are rewritten |
| [Hugging Face Agents Course](https://github.com/huggingface/agents-course) | `b3946b1d09d29c65736e219d48a8a736a2c52154` | Apache-2.0 | Under `units/en/unit1/`: `what-are-llms.mdx`, `messages-and-special-tokens.mdx`, `tools.mdx`, `actions.mdx`, `observations.mdx`, `dummy-agent-library.mdx`. The Chinese pages of the same names are in `units/zh-CN/unit1/` and are not checked out locally; read them with `git show` when needed | Borrowing structure: the order "LLMs and messages → tools → the action / observation loop", and the idea of demonstrating stop-and-parse. `actions.mdx` and `dummy-agent-library.mdx` were already registered in section 6, and `messages-and-special-tokens.mdx` and `what-are-llms.mdx` in section 7; this fills in the scope |
| [深入理解 AI Agent](https://github.com/bojieli/ai-agent-book) (Understanding AI Agents) | `b789c97a8f3de5b405a6f6dfa8289208d679d0b8` | Apache-2.0 | `book/introduction.md`; `book/chapter1.md`, `chapter2.md`, `chapter3.md`, `chapter4.md`, `chapter5.md`, `chapter6.md`, `chapter7.md`, `chapter10.md` (Chinese edition; each chapter's companion experiment directory is out of scope) | Borrowing structure: the summaries of where agents come from, the division of work between the model and the run layer, model limitations, context and tools, memory, and planning and multi-agent. Every conclusion still rests on this project's own real runs |
| [claude-cookbooks](https://github.com/anthropics/claude-cookbooks) | `d7265d6ae994ccd8429db0594b000073b2f9ad43` | MIT (Copyright (c) 2023 Anthropic) | `tool_use/`: `calculator_tool.ipynb`, `parallel_tools.ipynb`, `extracting_structured_json.ipynb`, `tool_use_with_pydantic.ipynb`, `context_engineering/context_engineering_tools.ipynb`; `misc/`: `how_to_enable_json_mode.ipynb`, `prompt_caching.ipynb`, `speculative_prompt_caching.ipynb`; `patterns/agents/`: `README.md`, `basic_workflows.ipynb`, `orchestrator_workers.ipynb`, `evaluator_optimizer.ipynb`; `extended_thinking/extended_thinking.ipynb`, `capabilities/classification/guide.ipynb`, `skills/README.md` | Borrowing structure: how tool calling, structured output, prompt caching, workflow patterns, extended thinking, classification and skills are taught, and how the comparisons are arranged. The three notebooks under `patterns/agents/` were already registered in section 6. Examples, tools and data are rewritten by this project |
| [learn-claude-code](https://github.com/shareAI-lab/learn-claude-code) | `ce8f9f186058939da54c9d6fead78dfb5d0fd6c3` | MIT (Copyright (c) 2024 shareAI Lab) | `README-zh.md` (the opening section on "agency comes from the model; an agent product = model + harness" corresponds to where agents come from and the run layer); `s01_agent_loop/README.zh.md`, `s02_tool_use/README.zh.md`, `s08_context_compact/README.zh.md`, `s09_memory/README.zh.md`; `docs/zh/s03-todo-write.md`, `docs/zh/s05-skill-loading.md`, `agents/s03_todo_write.py` | Borrowing structure: the split of "the model decides, the run layer handles the environment", and the way of teaching one thing at a time across loop, tools, to-dos, skills, compaction and memory. The repo has two numbering schemes at the same commit: under `docs/zh/` and `agents/`, TodoWrite is s03 and skill loading is s05; in the directory-organized `s0N_*/`, to-dos are `s05_todo_write` and skill loading is `s07_skill_loading`. Cite the full path. Historical cases and claims in its text must be checked against their own sources separately and are not cited directly |
| [mini-swe-agent](https://github.com/SWE-agent/mini-swe-agent) | `04d809ceab9df28f9adaed044884180159172930` | MIT (the repo's `LICENSE.md`, Copyright (c) 2025 Kilian A. Lieret and Carlos E. Jimenez) | `src/minisweagent/agents/default.py`, `src/minisweagent/config/default.yaml`, `src/minisweagent/config/mini_textbased.yaml`, `src/minisweagent/models/utils/actions_text.py` | Borrowing structure: how to write a minimal agent loop, and having text actions (parse the action from the reply; return a format error when parsing fails) coexist with native tool calling. No code or config is copied. It passes `os.environ` through to subprocesses unchanged; this project does not follow that (see `curriculum-research.md`) |

Reference repositories are mostly sparse clones on this machine; a file not shown by `ls` does not mean the repo lacks it. To check the reading scope, use `git ls-tree -r --name-only <commit>`.

## 9. Claude Code official docs: the "compare with Claude Code's public practice" passages in lessons (2026-10-04)

Several lessons gained a "compare with Claude Code's public practice" passage that cites the official docs. They are registered here.

- **Material:** the [Claude Code official docs](https://code.claude.com/docs), read on 2026-10-04.
- **Nature:** product documentation with no pinned version; content changes as the product is updated. Every such passage in the lessons says "the official docs are authoritative" and is not treated as a stable specification.
- **How it was borrowed:** only behavior the page states explicitly is cited, summarized in our own words with a link; no text, examples or figures are copied. Behavior the page does not state is not inferred.
- This is **not** reuse of upstream code or text and does not go into `THIRD_PARTY_NOTICES.md`.

Pages cited (all paths are under `https://code.claude.com/docs/en/`, de-duplicated from the links in `lessons/*/content.json`):

| Page | Lessons that cite it |
| --- | --- |
| `permissions` | `tool-selection`, `fail-safely`, `tool-proposals` |
| `tools-reference`, `tools-reference#task-tool-availability` | `dependent-calls`, `fail-safely`, `text-actions`, `todo-planning` |
| `best-practices` (`#give-claude-a-way-to-verify-its-work`, `#explore-first-then-plan-then-code`, `#add-an-adversarial-review-step`) | `task-contract`, `reflection-revision`, `plan-and-replan`, `orchestrator-evaluator` |
| `hooks`, `hooks-guide` (`#stop-hook-hits-the-block-cap`) | `task-contract`, `reflection-revision`, `workflow-patterns` |
| `agent-sdk/structured-outputs` | `structured-output` |
| `agent-sdk/todo-tracking` | `todo-planning` |
| `memory` | `prompt-experiments`, `messages-context`, `persistent-memory`, `memory-lifecycle` |
| `context-window` | `messages-context`, `application-state`, `context-compaction` |
| `how-claude-code-works` | `application-state`, `context-compaction`, `multi-turn-history` |
| `costs` | `context-budget`, `chat-request`, `multi-turn-history` |
| `prompt-caching` | `prompt-caching` |
| `skills` | `skills-disclosure` |
| `sub-agents` | `orchestrator-evaluator` |
| `permission-modes#analyze-before-you-edit-with-plan-mode` | `plan-and-replan` |

The mapping between lesson slugs and directory names follows `curriculum/catalog.json`; the table above is written from the `lessons/lesson_*/content.json` directory names with the prefix and number removed.

## 10. Papers: research whose conclusions the text cites (2026-10-12)

Research papers that the lesson text names and discusses, but that belong to none of the tutorials above, are registered here. Only the papers' conclusions are cited, summarized in our own words with a link; no text, figures, prompts or code are copied, so they do not go into `THIRD_PARTY_NOTICES.md`.

| Material | Pinned version | License | Registered reading scope | How it was borrowed and what for |
| --- | --- | --- | --- | --- |
| [Self-Refine: Iterative Refinement with Self-Feedback](https://arxiv.org/abs/2303.17651v2) (Madaan et al., NeurIPS 2023) | arXiv `2303.17651v2` (2023-05-25) | Paper, CC BY 4.0; only the conclusions are cited, nothing is copied | Abstract and method overview | The deep dive "How research views self-correction by a model" in `reflection-revision`: one model takes turns writing a draft, giving feedback and revising, and the paper reports improvements on tasks such as dialogue response and code optimization. The text only relays this conclusion |
| [Reflexion: Language Agents with Verbal Reinforcement Learning](https://arxiv.org/abs/2303.11366v4) (Shinn et al., NeurIPS 2023) | arXiv `2303.11366v4` (2023-10-10) | Paper, CC BY 4.0; only the conclusions are cited, nothing is copied | Abstract and method overview | Same as the previous entry: the success-or-failure signal from the environment (whether this attempt succeeded, whether tests passed) is first written out as a verbal summary and carried into the next attempt. The text only relays this approach |
