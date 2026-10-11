# Layered course system for agent development

Version: 2.0.0. Environment: Python, multi-provider model access, a local web learning platform; Bailian is the currently verified configuration.

> Generated from `curriculum/catalog.json` and its English overlays. The catalog, the web pages and this document share one source; after a change run `python scripts/export_curriculum.py`. Text without an English translation yet is shown in Chinese.

> Lesson numbers follow catalog order and are for display only; the API and links use the lesson ID (slug). Sections of available lessons come from their lesson text; sections of planned lessons are plans.

The course is organized as **category → module → lesson → topics → experiments → acceptance**. Available now: Lesson 1, Lesson 2, Lesson 3, Lesson 4, Lesson 5, Lesson 6, Lesson 7, Lesson 8, Lesson 9, Lesson 10, Lesson 11, Lesson 12, Lesson 13, Lesson 14, Lesson 15, Lesson 16, Lesson 17, Lesson 18, Lesson 19, Lesson 20, Lesson 21, Lesson 22, Lesson 23, Lesson 24. The other lessons are registered as plans and will be added one by one.

## Learning principles

- This file is the single source of truth for course categories, lesson numbers, prerequisites, and planning status. The web pages, the API, and the course docs are all generated from it.
- Lessons are identified by a stable slug. When a lesson is renamed, its old slug is registered as an alias. Displayed lesson numbers are computed from the order of registration in the catalog, so inserting a new lesson does not change any ID. "available" means the platform has the experiments, not that the learner has mastered the lesson. "planned" lessons only show the plan and cannot be run yet.
- Each lesson moves through goals, principles, code reading, prediction, experiments, trace comparison, and self-check. The planned experiments listed below are requirements for later production; registering a lesson does not mean its material and code are finished.
- Prerequisites follow knowledge dependencies. RAG does not require persistent memory first, LangChain does not require finishing Agentic RAG first, and standalone evaluation can start after the task acceptance lesson.
- Starting from Lesson 8, build a minimal acceptance case, and keep success and edge cases through every stage. Lesson 40 then studies independent verification, held-out sets, and regression in one place.
- Use a provider-independent, unified model interface, with Bailian as the configuration tested so far. Other services are supported through a mature SDK or an adapter layer, and the raw HTTP and the adapter-layer input and output are kept separately. Controlled-variable experiments fix the model and configuration for that run and are not tied to one long-term provider. Each new framework is installed as an optional dependency per lesson; check the official docs and pin the version when it is implemented.
- From the document-loading lesson on, external text is treated as untrusted. The full permission and prompt injection experiments are done in Lesson 43. The program decides which tools may run; a prompt cannot replace permission control.
- Each stage adds capability to the same local study assistant while keeping small experiments that can run on their own. A stage's result is accepted by its citations, parameters, state, actual side effects, and terminal state.
- Course experiments use real models and real tools. Simulation is only for internal automated tests and is not the main learning path. Replay does not re-run tools or models. Model output, tool results, and state updates are recorded separately; provider-measured, estimated, and unknown metrics are clearly distinguished; and an animation is never presented as the model's internal thinking.
- Reference projects supply structure and engineering ideas; the course's descriptions and experiments are written from scratch. Having read a source, the source existing, historical tests, and a local reproduction are each stated separately, references are pinned to a fixed snapshot, and the course does not claim to have implemented a whole tutorial.

## Overview by category

| Category | Modules | Lessons |
| --- | --- | --- |
| Native foundations | Model call basics; Tool calling; Errors and execution boundaries | 1, 2, 3, 4, 5, 6, 7 |
| Tasks & interfaces | Task definition and result contract; Prompts and tool descriptions | 8, 9, 10 |
| Context & state | Messages and application state; Context budget and compression; Persistent memory; Caching and skills | 11, 12, 13, 14, 15, 16, 17, 18 |
| Reasoning & control | Action protocols and planning; Replanning and bounded revision; Workflow patterns | 19, 20, 21, 22, 23, 24 |
| Knowledge & retrieval | Document processing and retrieval; Evidence-based answers and iterative retrieval | 25, 26, 27, 28, 29, 30 |
| Frameworks & orchestration | LangChain comparison and adaptation; LangGraph and concurrent runs; Approval, human-in-the-loop, and recovery | 31, 32, 33, 34, 35, 36, 37 |
| Coding agents & sandboxes | Commands, files, and change evidence | 38, 39 |
| Quality & reliability | Evaluation sets and validators; Observability and usage; Reliable tools and trust boundaries | 40, 41, 42, 43 |
| Protocols & tool services | MCP principles and tool integration; Connection lifecycle and cross-process delegation | 44, 45, 46 |
| Capstone & delivery | Multi-agent division of work and coordination; Long-running tasks; Local delivery and the capstone project | 47, 48, 49, 50, 51, 52, 53 |

## A · Native foundations

Start from a single model request and work up to real Python tool calls, and learn to read the model's decisions, execution results, and failure boundaries.

### A0 · Model call basics

One request, multi-turn history, and sampling variance: every later lesson builds on these three things.

#### Lesson 1 · One model request

**Lesson ID:** `chat-request`

**Level:** Core · **Status:** Available · **Difficulty:** Beginner · **Time:** about 20 min · **Model:** calls a real model

**Prerequisites:** Python functions, dicts, exceptions and JSON basics

Send one real model request with no tools, and learn to read model and messages in the request body, and the answer, finish reason, and usage in the response.

**Terms in this lesson:** Agent, Token, Usage, Message role, Finish reason

**Sections**

1. **One request is one JSON object**: Every step of an agent starts with a model request, and a request is a JSON obj…
2. **Message role: who said each message**: Each message in messages uses role to say who spoke. That is the message role. …
3. **The response: the answer and the finish reason**: The response is also a JSON object. The answer is in choices[0].message.content…
4. **Usage: how many tokens this call cost**: usage in the response reports how many tokens this call used. The provider bill…
5. **The key stays in the backend**: A request event records the request body, and the body has no API key. The key …
6. **What one request cannot do**: A single request cannot do three things: remember the earlier conversation, gua…

**Objectives**

- Name the fields that make up a model request
- Find the answer, finish reason, and usage in a response
- Explain how the system prompt and the output length limit change an answer

**Topics**

- Every agent step starts with one model request
- The request body: model and messages
- Message roles: system, user, assistant
- The response: choices[0].message.content
- Finish reason finish_reason: stop and length
- Usage and tokens; reasoning tokens count as completion tokens
- The API key stays in the backend; the request body carries no credentials

**Experiments**

With or without a system prompt:

1. Predict first how many model requests this run will send.
2. Run "With system prompt" and "Remove the system prompt", and compare the messages of the two requests.
3. Compare prompt_tokens and the answer in the two responses, and say which differences come from the request itself.

Deliverable: A comparison of messages and prompt tokens across two real requests.

Output limit and finish reason:

1. Predict first what finish_reason and the answer will look like when max_tokens is set to 16.
2. Run "Set a tiny output limit" and expand finish_reason, content, and usage in the response.
3. Compare completion_tokens with reasoning_tokens to decide whether the reasoning or the answer was cut off.

Deliverable: Field annotations on one real response that was cut off.

**Acceptance**

- You can point to model, messages, and each message's role in the request body.
- You can read the answer, finish reason, and provider-reported usage from the response; usage the provider did not report is written as "未报告" ("not reported").
- You can explain why finish_reason is length when the output is cut off, and how to tell the cause from usage when content is empty.

**References**

- [Hugging Face Agents Course](https://github.com/huggingface/agents-course): `units/en/unit1/messages-and-special-tokens.mdx`.
- [深入理解 AI Agent：设计原理与工程实践](https://github.com/bojieli/ai-agent-book): `book/chapter1.md`.

#### Lesson 2 · Multi-turn conversation: the program resends history

**Lesson ID:** `multi-turn-history`

**Level:** Core · **Status:** Available · **Difficulty:** Beginner · **Time:** about 20 min · **Model:** calls a real model

**Prerequisites:** Lesson 1 One model request

Ask two questions in a row and compare the request that carries the previous turn with the one that doesn't. The model does not remember the last turn; a multi-turn conversation works because the program resends the message history.

**Terms in this lesson:** Message history, Context

**Sections**

1. **The model doesn't remember the last turn on its own**: The model does not remember the last turn on its own. Every request is independ…
2. **Message history lives in the program**: A multi-turn conversation depends on a list the program holds, the message hist…
3. **Context: everything in this one request**: Context is everything the model can see in this one request. In this lesson tha…
4. **The longer the history, the bigger each request**: The whole history is resent every turn, so each request is bigger than the last…
5. **The program decides which history to carry**: Which history to carry and how to arrange it is entirely up to the program. The…

**Objectives**

- Explain why no state is kept between model calls
- Put each assistant reply back into the message history, turn by turn
- See from usage that the longer the history, the larger each request

**Topics**

- A call keeps no state
- Message history and writing assistant replies back
- With history vs. without history
- The context is everything in this one request
- Prompt tokens grow with the number of turns

**Experiments**

With and without history:

1. Predict first how many model requests "Ask a follow-up without history" will send, and whether the model can give the name mentioned in the first turn.
2. Run "Ask a follow-up with history" and "Ask a follow-up without history", and compare the messages of the two second-turn requests.
3. In the lab report, check whether the second-turn request contains the fact from the first turn, and whether the answer used it.

Deliverable: A message comparison of the two kinds of second-turn request.

Prompt tokens over three turns:

1. Run "Three-turn conversation" and expand the messages of the third-turn request.
2. In the lab report, note the prompt_tokens of each turn and work out the difference between adjacent turns.

Deliverable: A record of how the message count and prompt tokens change across three turns.

**Acceptance**

- You can point out which messages in the second request come from the previous turn.
- You can explain why the model cannot answer when history is left out.
- You can use the usage record to show what a growing history costs.

**References**

- [Hugging Face Agents Course](https://github.com/huggingface/agents-course): `units/en/unit1/messages-and-special-tokens.mdx`.
- [深入理解 AI Agent：设计原理与工程实践](https://github.com/bojieli/ai-agent-book): `chapter1/context/agent.py`.

#### Lesson 3 · Sampling and uncertainty

**Lesson ID:** `sampling-variance`

**Level:** Core · **Status:** Available · **Difficulty:** Beginner · **Time:** about 25 min · **Model:** calls a real model

**Prerequisites:** Lesson 1 One model request

Run the same prompt several times and compare how answers differ at low and high temperature. See why one run proves nothing and why experiments must be repeated.

**Terms in this lesson:** Controlled experiment, Temperature, Sampling

**Sections**

1. **The same request can get different answers**: Send the same request again, unchanged, and the answer may differ. When Lesson …
2. **The answer is drawn one token at a time**: The model writes its answer one token at a time, and each token is a draw. Here…
3. **Temperature: only the draw changes**: Whether you want a stable answer or a look at several phrasings is set by tempe…
4. **Temperature 0 doesn't guarantee the same answer**: With temperature set to 0, answers are usually very stable, but the provider do…
5. **How the lab report counts "how many different answers"**: The number of different answers is counted by the program: it strips leading an…
6. **What one run can prove**: One run is just one sample: it shows what happened this time, not that it will …

**Objectives**

- Explain that model output comes from sampling
- Compare how sampling temperature affects the spread of answers
- Explain why a controlled experiment fixes the conditions and repeats the run

**Topics**

- Sampling and probability distributions
- Temperature changes only how the draw is made, not the information
- Temperature 0 does not guarantee identical output
- Repeated runs and the number of distinct answers
- Controlled experiments: change one condition, repeat each arm
- What one run can and cannot prove

**Experiments**

Low and high temperature, 5 runs each:

1. Predict first how many model requests one run will send, and how many distinct answers the 5 will give at temperature 0 and at 1.3.
2. Run "temperature set to 0" and "temperature set to 1.3"; each sends 5 identical requests in a row.
3. Compare the number of distinct answers and each run's completion tokens across the two arms, and explain why later controlled experiments need several runs.

Deliverable: A comparison table of 5 real answers per arm, for two arms.

**Acceptance**

- Every answer comes from a real response, and the number of distinct answers is counted by the program.
- You can explain that temperature changes only the way of sampling, not the information in the request.
- You can point out that a difference seen in one run may be just variance.

**References**

- [深入理解 AI Agent：设计原理与工程实践](https://github.com/bojieli/ai-agent-book): `book/chapter1.md`.
- [Hugging Face Agents Course](https://github.com/huggingface/agents-course): `units/en/unit1/what-are-llms.mdx`.

### A1 · Tool calling

From call proposal to executing and returning the result, and then to data dependencies between tools.

#### Lesson 4 · Tool definitions and call proposals

**Lesson ID:** `tool-proposals`

**Level:** Core · **Status:** Available · **Difficulty:** Beginner · **Time:** about 30 min · **Model:** calls a real model

**Prerequisites:** Lesson 1 One model request

Send tool definitions to the model with the request and look only at the calls it proposes: which tool it picks and what the arguments are. This lesson executes no tools.

**Terms in this lesson:** Tool calling, JSON Schema, Tool description, Tool call proposal

**Sections**

1. **The model can only write text, so it borrows the program to do things**: The model can only write text. To have it check the time or do a calculation, y…
2. **The request now has tools**: The request in Lesson 1 had only messages. This lesson adds two fields: tools i…
3. **JSON Schema describes the arguments**: The parameters of each tool definition is a piece of JSON Schema: it uses JSON …
4. **Tool call proposal: what tool_calls says**: When the model decides to use a tool, the message in the response has a tool_ca…
5. **A proposal is not execution**: tool_calls is only a tool call proposal the model wrote down, like an order a w…
6. **When no tool is needed, answer directly**: A small-talk question needs neither addition nor the time. The model then answe…

**Objectives**

- Read the name, description, and parameter JSON Schema in a tool definition
- Find tool_calls and the arguments, a JSON string, in a response
- Tell apart "the model proposes a call" and "the program executes a tool"

**Topics**

- tools and tool_choice
- The tool description decides when a tool gets picked
- The JSON Schema of the parameters
- tool_calls, and arguments as a JSON string
- finish_reason is tool_calls
- Answer directly when no tool is needed
- A call proposal is not an execution

**Experiments**

Sum, time, and small talk:

1. Predict first how many tool_result events "Ask for a sum" will produce, and for each of the three questions whether a call will be proposed and which tool.
2. Run the three exercises one by one and expand tool_calls, arguments, and finish_reason in the response.
3. Confirm that the events of all three runs contain no tool_call and no tool_result: this lesson only observes proposals.

Deliverable: Call-proposal annotations on three real responses.

**Acceptance**

- You can find the tool name and the JSON-string arguments in a response.
- You can explain why the small-talk question got no call proposal.
- You can point out that no tool was executed in this lesson's runs.

**References**

- [Microsoft AI Agents for Beginners](https://github.com/microsoft/ai-agents-for-beginners): `04-tool-use/README.md`.
- [Hugging Face Agents Course](https://github.com/huggingface/agents-course): `units/en/unit1/tools.mdx`.

#### Lesson 5 · Executing tools and returning results

**Lesson ID:** `tool-selection`

**Level:** Core · **Status:** Available · **Difficulty:** Beginner · **Time:** about 30 min · **Model:** calls a real model

**Prerequisites:** Lesson 4 Tool definitions and call proposals, Lesson 2 Multi-turn conversation: the program resends history

Have Python execute the model's proposed calls against an allowlist, write the tool result back into the message history under the same call id, and request the model once more. This is the smallest agent loop.

**Terms in this lesson:** Harness, Tool result, Agent loop, Allowlist

**Sections**

1. **From tool call proposal to execution**: Lesson 4 stopped at the tool call proposal: the model writes a tool name and JS…
2. **Send the tool result back as a tool message**: After the function returns, execute_tool wraps the return value as a tool resul…
3. **The second request: the first time the model sees the result**: After the tool runs, run_agent goes back to the top of the loop and sends the f…
4. **The smallest agent loop: four steps and a round limit**: run_agent has only four steps: 1. Build the message history from the system pro…
5. **The harness and replay**: The model only proposes calls and writes answers. Building requests, executing …
6. **What this loop still lacks**: At this point a minimal agent is complete: the model proposes a call, the progr…

**Objectives**

- Explain how the runner dispatches by name to a registered function
- Pair a call with its tool result using tool_call_id
- Trace how a tool result enters the next request and becomes the basis for the answer

**Topics**

- Registered tools and dispatch
- role=tool messages and tool_call_id
- The tool result in the second request
- The four steps of the smallest agent loop
- The round limit
- Replay reads only existing records

**Experiments**

Addition and time: one full loop:

1. Predict first how many model requests one addition will send and how many tool results it will produce.
2. Run "Add two numbers" and "Look up local time", and mark the call proposal, tool_call, tool_result, and second request in order.
3. In the messages of the second request, find the message whose role is tool, and say what the answer is based on.

Deliverable: Event annotations for one complete loop, with the call id traced through.

**Acceptance**

- You can match a call to its tool result by the same tool_call_id.
- You can point out which two messages the second request has that the first doesn't.
- You can explain that Python executes the tool, and that replay called neither the model nor the tool again.

**References**

- [Microsoft AI Agents for Beginners](https://github.com/microsoft/ai-agents-for-beginners): `04-tool-use/README.md`.
- [深入理解 AI Agent：设计原理与工程实践](https://github.com/bojieli/ai-agent-book): `book/chapter1.md`.

#### Lesson 6 · Dependent calls across rounds

**Lesson ID:** `dependent-calls`

**Level:** Core · **Status:** Available · **Difficulty:** Beginner · **Time:** about 30 min · **Model:** calls a real model

**Prerequisites:** Lesson 5 Executing tools and returning results

Read the real current time, then use the previous step's hour and minute as the arguments of the next addition. Then compare two independent calls that are proposed in one round and executed one by one.

**Terms in this lesson:** Trace

**Sections**

1. **Look at the data dependency first, then plan the steps**: When the arguments of a later step can only be decided once the earlier step's …
2. **The model does not know what time it is**: Data the model does not have can only be fetched by a tool and sent back to it.…
3. **Message history carries the result into the next decision**: All the arguments the model writes in a single response are fixed before it see…
4. **Check where the arguments came from, not just the final number**: A correct final number does not show it was computed from this run's time. Take…
5. **Independent calls: proposed in one round, executed one by one**: When two tasks do not depend on each other, the model can propose two calls at …
6. **Next: what if a tool fails**: Every step on a dependency chain assumes the previous step succeeded. If the ti…

**Objectives**

- Recognize data dependencies between tools
- Explain how the message history carries tool results
- Verify that the next arguments come from this run's real tool output

**Topics**

- Dependency graphs and independent tasks
- Tool results in messages
- Building the next round's arguments
- Checking where arguments came from along the trace
- A sourced answer vs. a lucky guess
- Several calls proposed in one round, executed one by one by the runner

**Experiments**

One step's result decides the next step's arguments:

1. Predict first how many model requests "Add the hour and minute" will send.
2. In the trace, mark this run's hour and minute and the later addition arguments, and check the result against them rather than against a hard-coded time.

Deliverable: A record of the dependent calls, with the source of each piece of data traced.

Two independent tasks: proposed in one round, executed one by one:

1. Run "Two independent tasks" and check whether the first-round response contains two call proposals.
2. Use the timeline to check the execution order of the two tools and the two tool messages in the second request.

Deliverable: A record of the execution order and call-id pairing of independent calls.

**Acceptance**

- The arguments of the second tool call match the hour/minute returned by the first.
- You can point to the message that carries the previous round's result, and explain why one model request cannot obtain data it has not yet observed.
- You can tell apart events that merely appear in order from arguments that were actually produced from the previous step's data.
- You can explain why independent calls can be proposed in one round, and why being proposed in one round does not mean being executed at the same time.

**References**

- [Hugging Face Agents Course](https://github.com/huggingface/agents-course): `units/en/unit1/observations.mdx`.
- [深入理解 AI Agent：设计原理与工程实践](https://github.com/bojieli/ai-agent-book): `chapter1/context/grounding.py`.

### A2 · Errors and execution boundaries

Use failure cases to pin down what validation, the allowlist, and stop conditions are responsible for.

#### Lesson 7 · Error handling and safety boundaries

**Lesson ID:** `fail-safely`

**Level:** Core · **Status:** Available · **Difficulty:** Beginner · **Time:** about 30 min · **Model:** calls a real model

**Prerequisites:** Lesson 6 Dependent calls across rounds

Run normal division and division by zero for real, then use fault injection to confirm that an unregistered tool and broken arguments cannot get past the runner's boundary.

**Terms in this lesson:** Stop condition, Structured error, Terminal state

**Sections**

1. **The earlier lessons walked only the happy path**: Tools fail, and the reason should go back to the model as it is, instead of cra…
2. **The schema describes the interface; Python holds the boundary**: The parameter descriptions in a tool definition are written for the model; what…
3. **A failure is also returned as a structured error**: When a tool fails, the runner returns three fields, ok=false, error_type, and e…
4. **Judge the loop ending and the computation's success separately**: The run's terminal state and the tool's success or failure are two questions, t…
5. **Fault injection: testing the paths a model rarely takes**: An unregistered tool name and broken arguments are hard to wait for reliably fr…
6. **Next: who judges that the task is done**: This lesson kept separating three things: the run ending, the tool succeeding, …

**Objectives**

- Return execution errors as structured results
- Confirm that only explicitly registered tools are executed
- Tell apart a run that finished, a task that succeeded, and an exhausted budget

**Topics**

- Parsing argument JSON and validating input
- The tool allowlist
- Tool exceptions and tool results with ok=false
- How the model behaves after receiving an error
- Round budget and stop conditions
- Real model behavior and independent program checks

**Experiments**

A failure is still paired and returned:

1. Run normal division and division by zero through the real model, changing only the divisor, and compare the tool results and the final answers.
2. In offline test mode, inject an unregistered tool name and unparseable arguments. Confirm the runner rejects them before calling any function, and returns error_type and error as a failure result paired with the call.
3. Keep the two kinds of evidence apart: a real model run shows what the model did this time; an injected fault, labeled with its source in the events, shows only the program's boundary.

Deliverable: Real run records for normal division and division by zero, and rejection records for the two injected faults.

**Acceptance**

- The unregistered tool was not executed, and the broken arguments did not get around parsing.
- Division by zero was returned as a structured result with ok=false, and the final answer did not treat the failure as a valid number.
- Every failure result is paired with its call, and the run ended normally.

**References**

- [Microsoft AI Agents for Beginners](https://github.com/microsoft/ai-agents-for-beginners): `04-tool-use/README.md`.
- [深入理解 AI Agent：设计原理与工程实践](https://github.com/bojieli/ai-agent-book): `book/chapter4.md`.

## B · Tasks & interfaces

Turn a requirement into a task that can be accepted, and constrain behavior with explicit input, output, and tool contracts.

### B1 · Task definition and result contract

Define success criteria and tell structurally valid output apart from business-correct output.

#### Lesson 8 · Task goals and acceptance

**Lesson ID:** `task-contract`

**Level:** Core · **Status:** Available · **Difficulty:** Beginner · **Time:** about 40 min · **Model:** no model calls

**Prerequisites:** Lesson 7 Error handling and safety boundaries

Before writing more agent code, spell out the input scope, output, constraints, evidence, failure handling, and stop conditions, and set up a minimal acceptance baseline. This lesson does not call the model.

**Terms in this lesson:** Acceptance criteria, Validator, Task card, Completion claim

**Sections**

1. **From "help me learn" to an executable task**: The program finishing and the executor saying "done" do not mean the task is co…
2. **The task card writes down the acceptance rules**: Before execution, the task card writes the acceptance criteria as six fields; t…
3. **The run ending and the acceptance check passing are two different things**: "Done" has at least three meanings, to be judged separately: the flow ended, th…
4. **One rule covers both normal and failure cases**: All the presets share the same piece of acceptance code; only the evidence chan…
5. **Claiming completion and proving completion**: A completion claim is only a statement the executor hands in; its job is to poi…
6. **The report traces back to actual evidence**: The passed of every check in lesson.report can be traced back to this run's too…
7. **Preview: the goal loop with a limit**: When the acceptance check fails, you can hand the reason back to the executor a…

**Objectives**

- Turn a vague requirement into a task card that can be checked
- Define success criteria for normal and edge-case inputs
- Tell apart a generated answer, a run that finished, and business completion

**Topics**

- User goals and executable tasks
- Input, output, and data scope
- Criteria for success and failure
- Evidence requirements and handling unknowns
- Dependencies and stop conditions
- Fixed cases and independent checks
- Claiming completion vs. proving completion
- Goal loops with a limit (preview)

**Experiments**

One task card, four cases:

1. Write the fixed task (19 + 23) as a task card: input, output, evidence requirements, failure handling, and stop conditions. This lesson does not call the model.
2. Use the same set of checks to judge four cases in turn: a normal result, a claim with no evidence, evidence present but the result wrong, and a claim that disagrees with the evidence.
3. Preview the goal loop with a limit: two arms, up to 3 attempts and only 1 attempt allowed. Watch how a failed check decides retry and stop.

Deliverable: One task card, and the verdict records for four cases: normal, missing evidence, wrong result, and claim that disagrees with the evidence.

**Acceptance**

- The task card contains the input scope, output requirements, evidence, failure handling, and stop conditions.
- The checks can be judged from tool results or artifacts, not from the agent's own claim of completion.
- At least one normal case and one edge case can be judged unambiguously by the same set of rules.

**References**

- [深入理解 AI Agent：设计原理与工程实践](https://github.com/bojieli/ai-agent-book): `book/chapter5.md`.
- [深入理解 AI Agent：设计原理与工程实践](https://github.com/bojieli/ai-agent-book): `book/chapter7.md`.
- [Microsoft AI Agents for Beginners](https://github.com/microsoft/ai-agents-for-beginners): `STUDY_GUIDE.md`.

#### Lesson 9 · Structured output and business validation

**Lesson ID:** `structured-output`

**Level:** Core · **Status:** Available · **Difficulty:** Beginner · **Time:** about 40 min · **Model:** calls a real model

**Prerequisites:** Lesson 8 Task goals and acceptance

Receive model output with a mature schema and validation library, and check the JSON format, field constraints, and business facts as separate layers.

**Terms in this lesson:** Structured output, Call budget

**Sections**

1. **Model text is input to be checked**: JSON the model writes exactly as asked is still just text until a program check…
2. **Layer 1: JSON syntax**: Layer 1 answers one question: can this text be parsed as JSON. inspect_output p…
3. **Layer 2: Pydantic field constraints**: Layer 2 checks the shape of the JSON: whether the required fields exist, whethe…
4. **Layer 3: independent business facts**: Layer 3 compares the lesson card, item by item, against trusted facts given in …
5. **Limited repair and explicit failure**: When a check fails, you can hand the reason back to the model for one fix, but …
6. **Next: use the check results to change the prompt**: The three layers give conclusions you can verify: at which layer this output fa…

**Objectives**

- Design an output schema that matches the task's acceptance criteria
- Locate three kinds of error: format, schema, and business
- Build bounded repair and an explicit failure return

**Topics**

- A unified model interface and differences in structured-output support
- Raw HTTP and adapter-layer input and output
- JSON format, field types, and a required-field schema
- Mature validation libraries such as Pydantic
- Business evidence and factual consistency
- Parse failures and bounded repair

**Experiments**

Three layers: which layer stops which error:

1. Using the same study task card (course ID, lesson name, prerequisites, exercises), run three arms: normal extraction, a deliberately missing field, and a deliberately wrong fact. Change only the user message.
2. Each output goes through three layers in turn: JSON parsing, the field schema, and business facts. The result of each layer is written into the report separately.
3. On failure, send the reason back to the model for one repair (can be turned off), and run the repaired draft through the same three layers. If it still fails, report the failure as it is.

Deliverable: The per-layer check results for three runs, and a before-and-after repair comparison.

**Acceptance**

- You can say which layer stops a missing field and which layer stops a wrong fact.
- Output that is structurally valid but factually wrong is not judged as passing.
- Repair is attempted at most once; if it still fails afterward, failure is reported rather than replaced with default success data.

**References**

- [Microsoft AI Agents for Beginners](https://github.com/microsoft/ai-agents-for-beginners): `04-tool-use/README.md`.
- [深入理解 AI Agent：设计原理与工程实践](https://github.com/bojieli/ai-agent-book): `book/chapter4.md`.

### B2 · Prompts and tool descriptions

Compare the effect of prompts and tool descriptions with controlled variables.

#### Lesson 10 · Prompts and tool descriptions

**Lesson ID:** `prompt-experiments`

**Level:** Core · **Status:** Available · **Difficulty:** Beginner · **Time:** about 40 min · **Model:** calls a real model

**Prerequisites:** Lesson 8 Task goals and acceptance, Lesson 9 Structured output and business validation

Fix the model, task, and budget, and change only one thing at a time, either the tool description or a process rule. Judge the effect by the actual calls and answers, not by how the wording sounds.

**Terms in this lesson:** LLM-as-a-judge

**Sections**

1. **Decide what you are comparing first**: Whether a prompt change is good has to be judged by a controlled experiment, no…
2. **A tool description is a decision input**: When the model decides whether to call a tool and how to fill its arguments, al…
3. **Process rules must be observable**: A rule written into the system prompt has to show up somewhere visible in the a…
4. **Do not make up missing arguments**: When information is missing, the right action is to ask, not to fill in a numbe…
5. **The paired report keeps regressions**: The report keeps the original text of both versions and the screening result si…
6. **Blank, good, misleading: a matrix of three descriptions**: The tool description matrix compares three descriptions at once, to see how the…
7. **From changing one text to removing part of the context**: Change one thing at a time is the rule shared by all experiments in this lesson…

**Objectives**

- Write prompts and tool descriptions with clear responsibilities
- Change one variable at a time in paired cases
- Use the full records to explain improvements and regressions

**Topics**

- Goal, process, and output rules
- Tool naming and narrow-responsibility descriptions
- What parameters mean and what failure means
- Paired experiments with the model and configuration fixed for that run
- Provider capability differences, sampling, and variance across repeated runs
- The tool description matrix: blank, good, misleading

**Experiments**

Change one thing at a time: tool description and system rules:

1. Request the same task once each: change only the description of add_numbers from "计算工具。" ("Calculation tool.") to one that states its responsibility and parameters, and compare the call proposals and arguments.
2. Change only the system rule: the baseline "请给出答案" ("Give the answer") against a version that spells out the steps of identifying, calculating, and checking. When the user gives no numbers, the comparison arm is told to ask only for the missing numbers.
3. The tool description matrix: run two questions each with the blank, good, and misleading descriptions, and see how the model's decision and the execution result diverge when the description disagrees with the code.

Deliverable: A comparison of each arm's request, call proposal, tool result, and answer, stating which one thing that arm changed.

**Acceptance**

- Each experiment states its single change and the conditions held fixed.
- Every judgment about an effect can be traced to an actual request, call proposal, tool result, or check result.
- A single run is only one observation: the report keeps regressions and variance, and does not infer a general effect from one success.

**References**

- [深入理解 AI Agent：设计原理与工程实践](https://github.com/bojieli/ai-agent-book): `chapter2/prompt-engineering/run_ablation.py`.
- [Microsoft AI Agents for Beginners](https://github.com/microsoft/ai-agents-for-beginners): `04-tool-use/README.md`.

## C · Context & state

Manage the next round of model input, application state, and cross-session memory, while keeping evidence and users isolated.

### C1 · Messages and application state

Tell message history apart from the task state the program maintains.

#### Lesson 11 · Context components and the message protocol

**Lesson ID:** `messages-context`

**Level:** Core · **Status:** Available · **Difficulty:** Intermediate · **Time:** about 40 min · **Model:** calls a real model

**Prerequisites:** Lesson 6 Dependent calls across rounds, Lesson 10 Prompts and tool descriptions

Split one request's context into four parts: the system prompt, earlier conversation, tool calls and tool results, and this turn's question. Remove one part at a time and compare answers. A tool call and its result must be removed together, and an invalid history is stopped before it is sent.

**Terms in this lesson:** Message protocol

**Sections**

1. **What goes into one request**: All the model can use when it answers is what is in this one request, so first …
2. **Remove one part at a time**: To find out which part an answer relies on, leave everything else word for word…
3. **Tool calls and tool results must come as a pair**: A tool call and its result must be paired one to one by call id. Rules like thi…
4. **What if only the tool result is removed**: If you remove only the tool result and keep the call, the history violates the …
5. **How to read this run**: Read the result in three layers, ruling things out layer by layer, and look at …
6. **Limits and cost**: One ablation sends several requests. It suits doing a few controlled comparison…

**Objectives**

- Name the parts a request's context is made of and what each provides
- Use valid ablation, removing one part at a time, to judge which part an answer depends on
- Handle tool calls and tool results as pairs under the message protocol, and stop an invalid history before sending

**Topics**

- Recap of Lesson 2: a multi-turn conversation works because the program resends the message history
- The four parts of the context: system prompt, earlier conversation, tool calls and tool results, this turn's question
- Valid ablation: remove one part at a time and leave the rest word for word unchanged
- The message protocol: a call and its result are paired by call id
- The pre-send protocol check validate_tool_history
- Keyword screening, and reading the original answer text

**Experiments**

Remove one part at a time:

1. Predict first: one of the five context arms removes only the tool result. How many model calls will this run make?
2. Run "Remove each of the four parts". Compare each arm's request messages with its answer, and mark which part the score, the review day, and the "依据：" ("Basis:") line each come from.
3. Find the arm stopped by the protocol check and say which rule it breaks. Then run once more with a failing student and see whether the answer follows the tool result.

Deliverable: A message comparison table for the five context arms, with attribution notes.

**Acceptance**

- You can say which parts each arm's request actually contains, and which part the score and the review day in the answer each depend on.
- Every request that is sent passes the protocol check. The arm that removes only the tool result is stopped before sending and has no request event.
- You can tell three cases apart: the request was stopped or rejected by the provider, that part was not in the request, or the answer did not use it.

**References**

- [Hugging Face Agents Course](https://github.com/huggingface/agents-course): `units/en/unit1/messages-and-special-tokens.mdx`.
- [深入理解 AI Agent：设计原理与工程实践](https://github.com/bojieli/ai-agent-book): `chapter1/context/agent.py`.

#### Lesson 12 · Application state and the run lifecycle

**Lesson ID:** `application-state`

**Level:** Core · **Status:** Available · **Difficulty:** Intermediate · **Time:** about 45 min · **Model:** no model calls

**Prerequisites:** Lesson 8 Task goals and acceptance, Lesson 11 Context components and the message protocol

This lesson does not call the model. A typed state machine tracks the task goal, evidence, steps, and terminal state, and keeps program state, message history, and model output apart.

**Terms in this lesson:** Application state

**Sections**

1. **What messages and state each manage**: How far a task has got and which facts have been checked should be recorded by …
2. **What a state looks like**: TaskState uses eight fields to answer a few basic questions: which run is this,…
3. **The step budget and state snapshots**: Each step deducts from the budget before it runs. When the budget is used up, t…
4. **Transition rules guard the boundaries**: status can only move along the transition table TRANSITIONS, and any transition…
5. **Waiting, failure, and the budget running out**: Missing material and an exhausted budget both end in failed, for different reas…
6. **Session isolation and cancellation**: Each run creates its own TaskState and run_id, so two runs' states do not inter…
7. **How state gets back in front of the model**: In this lesson the model cannot see this state. In a real agent, the runner for…

**Objectives**

- Say what each field of the application state records, and keep it separate from the message history
- Follow the state snapshots and trace which step caused each state change
- Tell waiting, completed, and failed (material missing or budget exhausted) apart, and write the reason for each terminal state

**Topics**

- What messages and application state each manage
- TaskState: goal, evidence, steps, artifacts, and the reason for the terminal state
- Step budget: deducted before each step runs
- Transition table and state machine: illegal transitions are rejected outright
- Waiting, failed, and completed are terminal states that each carry a reason
- Run ID, session isolation, and cancellation

**Experiments**

Three terminal states, each with a reason:

1. Predict first how many state snapshots the run with the material present and a step budget of 3 will publish.
2. Run the three presets in turn (complete with evidence, missing material, budget exhausted), and follow lesson.state to write out each arm's state transition order.
3. Compare the terminal-state reason, evidence count, executed steps, and message count in the report. Then set the step budget to 1, run once more, and compare the outcomes.

Deliverable: A record of each arm's state transition order and terminal-state reason.

**Acceptance**

- Every state change can be traced back to a lesson.state snapshot. A run can reach completed only when both evidence and artifacts exist, and model text cannot rewrite the state directly.
- Each run creates a new TaskState and run_id. messages always holds just one user goal, and is viewed separately from the application state.
- Missing material and an exhausted budget each end in a failed state with a stated reason, and the evidence already gathered is kept.

**References**

- [深入理解 AI Agent：设计原理与工程实践](https://github.com/bojieli/ai-agent-book): `chapter1/context/agent.py`.

### C2 · Context budget and compression

Within a limited budget, keep the goal, constraints, sources, and unfinished work.

#### Lesson 13 · Context budget and the truncation window

**Lesson ID:** `context-budget`

**Level:** Core · **Status:** Available · **Difficulty:** Intermediate · **Time:** about 40 min · **Model:** calls a real model

**Prerequisites:** Lesson 11 Context components and the message protocol, Lesson 12 Application state and the run lifecycle

Compare the full history with a window truncated by a character budget. See what the budget actually measures, what truncation drops, and why tool calls and tool results must be handled as a group when truncating.

**Terms in this lesson:** Context window, Context budget, Context rot

**Sections**

1. **How much fits in one request**: A request has a length limit, but the message history keeps growing, so sooner …
2. **Characters, tokens, and usage**: This lesson budgets with a local character count because it does not depend on …
3. **What the full history costs**: Sending the full history is the easiest option. The cost is that every request …
4. **Truncation window: fill from the newest message backward**: A truncation window first secures the system message and the current question, …
5. **Truncating by message count splits the pair**: If you truncate only by message count, the cut point can land between a tool ca…
6. **How to read the lab report**: The lab report puts the two layouts side by side: message count, JSON character…
7. **The most recent is not always the most important**: A truncation window decides only by recency and does not know which message mat…

**Objectives**

- Explain the context window and the context budget, and tell local character counts, tokens, and provider usage apart
- Implement a truncation window that cuts to a budget and moves tool calls and tool results in and out as a group
- Explain what happens when truncating by message count splits a tool pair

**Topics**

- The context window and the context budget
- Local character counts, tokens, and provider usage
- Side-discussion history makes the full history longer
- The truncation window: fill from the newest backward, and tool interactions go in and out as a group
- Truncating by message count splits a tool pair
- How a provider actually responds to an orphaned tool result

**Experiments**

Full history vs. truncation window:

1. Predict how many tool_call events this run has, and which messages the truncation window will drop.
2. Run with budgets of 600 and 4000 characters, and compare the message count, character count, sources, and answer of the two layouts.
3. In the window event, check the number of messages kept and dropped, and whether the tool result is still there.

Deliverable: A layout comparison under two budgets, with source checks.

Add more side-discussion history:

1. Raise the side discussion from 8 turns to 20 and leave everything else unchanged.
2. Compare how the character counts of the full history and the truncation window change.

Deliverable: A length comparison before and after the side discussion grows.

Split a tool call from its result:

1. Run the "Split a tool call from its result" exercise and record the verdict of the local protocol check.
2. Use a real model to see how the provider responds to an orphaned tool result.

Deliverable: Protocol checks for the two truncations, and the provider's response record.

**Acceptance**

- You can point out which source the truncation window dropped, and whether the window is within budget.
- Tool calls and tool results go in and out as a group, and the truncated request passes the protocol check.
- When the provider rejects a request, the status code and source are recorded as they are, with no retry and no rewriting. Offline, the record says it is simulated by a fixture.

**References**

- [深入理解 AI Agent：设计原理与工程实践](https://github.com/bojieli/ai-agent-book): `chapter2/context-compression/compression_strategies.py`.
- [Microsoft AI Agents for Beginners](https://github.com/microsoft/ai-agents-for-beginners): `STUDY_GUIDE.md`.

#### Lesson 14 · Context compression and probe questions

**Lesson ID:** `context-compaction`

**Level:** Core · **Status:** Available · **Difficulty:** Intermediate · **Time:** about 45 min · **Model:** calls a real model

**Prerequisites:** Lesson 13 Context budget and the truncation window

Compare three kinds of compression: rule-based compression, clearing old tool results, and a model-written summary. Use a probe question that only the earliest tool result can answer to check whether the information is still there.

**Terms in this lesson:** Context compression

**Sections**

1. **Another option besides cutting**: Old content that does not fit can be dropped as a whole group, or it can be rew…
2. **Probe question: only old information can answer it**: After compression, you cannot tell from length whether information was lost; yo…
3. **Rule-based compression: the program decides what to keep**: Rule-based compression has the program assemble one record from predefined fiel…
4. **Clearing old tool results: the position stays, the content is gone**: Clearing old tool results replaces only the content of the earlier tool message…
5. **Summary compression: the model decides what to keep**: Summary compression sends one extra request that has the model write the earlie…
6. **When to compress, and how much**: Real systems usually compress only when the length nears the budget; this lesso…
7. **How to read the lab report**: In the lab report, look first at the "原话还在上下文里" ("original wording still in the…

**Objectives**

- Tell rule-based compression, clearing old tool results, and model summaries apart
- Use a probe question to check information loss after compression, keeping local string checks separate from keyword screening
- Explain the cost and risk of each kind of compression

**Topics**

- Context compression rewrites only the earlier part
- Rule-based compression: goal, constraints, sources, facts, to-dos; report an error if it doesn't fit
- Clearing old tool results: keep the position, replace the content
- A model summary costs one more request, and the instruction affects what stays
- The probe question
- Character counts and usage before and after compression

**Experiments**

Three compression methods, one probe question:

1. Predict how many request events this run has.
2. Run the compression comparison exercise and look at each arm's compressed context and its probe answer.
3. Compare whether the original wording is still in the context, and whether the answer gets both the source and the original wording right.

Deliverable: Four contexts, the probe answers, and the loss record.

Rule-based compression's budget cannot hold the evidence:

1. Lower the character budget of rule-based compression from 300 to 100 and leave everything else unchanged.
2. Look at the rejection reason and compare the number of model calls in the two runs.

Deliverable: A comparison of the rejection event and the number of model calls.

The summary instruction decides what is kept:

1. Switch to a summary instruction that asks for only a sentence or two and leave everything else unchanged.
2. Compare the summary text of the two runs and the probe result of the summary-compression arm.

Deliverable: A comparison of the summaries and probe results under two instructions.

**Acceptance**

- The context after each kind of compression passes the protocol check.
- The probe conclusion records local string checks and keyword screening separately.
- The extra request for a model summary counts toward the number of model calls. When rule-based compression cannot fit the key evidence, it refuses and states the reason.

**References**

- [深入理解 AI Agent：设计原理与工程实践](https://github.com/bojieli/ai-agent-book): `chapter2/context-compression/compression_strategies.py`.

### C3 · Persistent memory

Manage where a memory comes from and how it is stored, retrieved, updated, and forgotten.

#### Lesson 15 · Persistent memory: save, reopen, and recall

**Lesson ID:** `persistent-memory`

**Level:** Core · **Status:** Available · **Difficulty:** Intermediate · **Time:** about 45 min · **Model:** calls a real model

**Prerequisites:** Lesson 12 Application state and the run lifecycle, Lesson 13 Context budget and the truncation window

Write explicitly given information to SQLite, close the connection and read it back, then recall it by namespace and put it into a real model request as data.

**Terms in this lesson:** Memory, Persistent memory, Recall, Namespace

**Sections**

1. **Memory is not in the model**: A model does not remember you because you talked once. For the next run to know…
2. **Store only values that were explicitly given**: This lesson stores only values you explicitly give, and records the source with…
3. **Close the connection, then read again**: Closing the connection after writing and reading back on a new one is what prov…
4. **A namespace is a partition, not a permission**: A namespace splits records into separate pieces, but it only decides which piec…
5. **Read-only recovery of the last memory**: Reading should not change anything, and this lesson makes the reading connectio…
6. **Recall: put memory in the next request**: Being stored in the database does not mean the model can see it. The program ha…
7. **The grounds for an answer must be findable in the request**: The answer is generated by the model. Do not judge it only by how plausible it …
8. **After it is stored**: Persistent memory handles only one thing: the next run still knows. The earlier…

**Objectives**

- Tell context, application state, and persistent memory apart
- Reopen the connection to prove that memory is really saved across runs
- Put recalled memory into the request as data, and find the basis for the answer in the request

**Topics**

- External storage, not model parameters
- Save only explicitly given values and their sources
- Read again after the connection is closed
- A namespace is a partition, not a permission
- Read-only recovery of the last memory
- Recall and put it in a data block in the user message

**Experiments**

Save, reopen, and read-only recovery:

1. Write a learning goal, close the connection and read it back with a new one, and check that another namespace was not changed.
2. Recover the last saved memory read-only, and confirm that the reading connection changed no row.

Deliverable: A report on saving, reopening, and read-only recovery.

Recall and put into the request:

1. Recall from the namespace that has memory, put it into one real model request, and check whether every key the answer cites is in the request's data block.
2. Switch to a namespace with no memory, ask the same question again, and compare what the answer is based on.

Deliverable: The real requests, answers, and check reports after two recalls.

**Acceptance**

- The value and version read back after reopening the connection match what was written.
- The same key in another namespace is not changed by this write. A namespace is only a partition, not permission isolation.
- Neither read-only recovery nor recall changes any row.
- Recalled content appears only in the data block of the user message, and every key the answer cites can be found in this request.

**References**

- [Microsoft AI Agents for Beginners](https://github.com/microsoft/ai-agents-for-beginners): `13-agent-memory/README.md`.
- [深入理解 AI Agent：设计原理与工程实践](https://github.com/bojieli/ai-agent-book): `book/chapter3.md`.

#### Lesson 16 · Memory updates, expiry, and recall scope

**Lesson ID:** `memory-lifecycle`

**Level:** Core · **Status:** Available · **Difficulty:** Intermediate · **Time:** about 45 min · **Model:** no model calls

**Prerequisites:** Lesson 15 Persistent memory: save, reopen, and recall

Two writers change the same memory one after the other, and a version number rejects the stale write. Let a record expire and then delete it, to tell "can't be read" from "deleted". Then recall by task scope, treating any "instruction" in the recalled text as data only. This lesson does not call the model.

**Terms in this lesson:** Optimistic concurrency control

**Sections**

1. **Memory changes, so reads and writes need rules**: Once memory is stored, it still gets rewritten and goes stale, and some of it i…
2. **Two writers, one version number**: When two writers change the same memory one after the other, the version number…
3. **After a rejection: read again, then decide**: A rejected write means what you read is already out of date, so you should look…
4. **Expiry is a read rule; deletion is a storage operation**: Expiry only makes a record invisible on read; deletion is what removes it from …
5. **persistent and current_task**: Not all memory should be carried all the time: what is valid long term and what…
6. **A recalled "instruction" is only data**: Recalled text is only data, even if it is written like a command. Memory comes …
7. **One memory from write to delete**: Chain the three exercises together and you get a memory's whole path from write…

**Objectives**

- Reject stale writes with optimistic concurrency control, and after a rejection read again before writing
- Tell expiry (a read rule) apart from deletion (a storage operation)
- Filter recall by scope, and handle recalled content as data

**Topics**

- Version numbers and stale writes
- Re-reading after a conflict
- Expiry is a read rule; deletion is a storage operation
- persistent and current_task
- Cleanup when a task ends
- Flagging suspected instructions is not a security boundary

**Experiments**

Stale write, expiry and deletion, and scope filtering:

1. Two writers read the same version and then write one after the other. Confirm the stale write is rejected and the current value is unchanged.
2. Let a reminder expire and then delete it, and use a fresh connection to check that it can neither be read nor found.
3. Recall by task scope, and see how the previous task's draft and the suspected instruction are handled.

Deliverable: A report on conflict, forgetting, and scope filtering.

**Acceptance**

- The stale write is rejected and the current value is unchanged. After re-reading, a write with the new version succeeds.
- An expired record can't be read but is still in the table. After deletion and reopening the connection, it can neither be read back nor found.
- The previous task's draft does not enter this task's recall result. A suspected instruction appears only as data and is not executed.

**References**

- [Microsoft AI Agents for Beginners](https://github.com/microsoft/ai-agents-for-beginners): `13-agent-memory/README.md`.
- [深入理解 AI Agent：设计原理与工程实践](https://github.com/bojieli/ai-agent-book): `book/chapter3.md`.

### C4 · Caching and skills

How a stable prefix is reused, and how skill instructions enter the context only when needed.

#### Lesson 17 · Prompt caching and the stable prefix

**Lesson ID:** `prompt-caching`

**Level:** Core · **Status:** Available · **Difficulty:** Intermediate · **Time:** about 45 min · **Model:** calls a real model

**Prerequisites:** Lesson 13 Context budget and the truncation window

Send the same long document in several requests in a row and compare three structures: dynamic content first, a stable prefix, and a warmup. Use the cache fields the provider actually reports and a local prefix hash to judge whether the start can be reused.

**Terms in this lesson:** Prompt caching, Stable prefix, Cached tokens

**Sections**

1. **The start is the same every round, yet it is reprocessed every round**: An agent's request often starts the same way every round, yet the provider proc…
2. **Only an identical start counts, from the first character**: The cache matches by prefix: it compares this request with earlier ones from th…
3. **Reading the hit count from usage**: How many tokens hit can only be read from how the provider reports it in the re…
4. **If it isn't reported, write not reported**: Some providers or endpoints don't return cache fields. In that case normalize_c…
5. **Prefix hash: confirm locally that the start didn't change**: The hit count comes from the provider and fluctuates for reasons such as cache …
6. **Warmup: move the first cold request earlier**: For the first request of the stable-prefix arm, the provider hasn't seen this p…
7. **The ways an agent most easily breaks the prefix**: In a real agent, each round's request usually starts with the system prompt and…
8. **What one run can tell you**: Whether a hit happens is up to the provider. Some providers cache only when the…

**Objectives**

- Explain that prompt caching reuses only a verbatim identical prefix, and that where dynamic content sits decides whether the start can be reused
- Read each provider's cache fields from usage and normalize them into cached tokens and hit ratio
- Tell "the provider reported 0" apart from "not reported", and use a prefix hash to check locally whether prefixes are identical

**Topics**

- Prefix matching and the position of dynamic content
- Cached tokens and hit ratio
- Normalizing the cache fields of Bailian, DeepSeek, and Anthropic
- "Reported as 0" vs. "not reported"
- Prefix hash and the number of identical prefix characters
- Warmup requests and isolation between runs
- Common ways agents break the prefix
- The limits of a single run and of timing

**Experiments**

Where the dynamic content goes:

1. With the same rules, a handbook of over 2,700 characters, and the same question, put the dynamic line (request number and send time) first in the system prompt in one arm, and at the end of the last user message in the other.
2. Each arm sends 4 requests in a row (adjustable from 3 to 5). Record each request's prefix hash, the number of prefix characters identical to the previous request, the provider-reported cached tokens, the hit ratio, and the elapsed time.
3. Compare the prefix hash columns of the two arms and point out which line breaks the prefix.

Deliverable: A per-request usage table for two arms, with a prefix hash comparison.

The warmup request:

1. Before the stable-prefix arm, send one warmup request that asks only for the reply "已读" ("read"), then send 4 measured requests in a row.
2. Compare the hit reported by the first measured request with and without the warmup.
3. When a response has no cache field, the report shows "未报告" ("not reported") and does not record it as 0.

Deliverable: For two arms of measured requests, the number of hits, the overall hit ratio, and a note on the "not reported" state.

**Acceptance**

- Each request's cached tokens and hit ratio come from fields the response actually reports, and the report states where the field comes from.
- You can use the prefix hash to point out the line that breaks the prefix in the "dynamic content first" arm.
- A cache field that was not reported is shown as "未报告" ("not reported") and not recorded as 0. The normalization function has unit tests for the fields of all three providers.

**References**

- [深入理解 AI Agent：设计原理与工程实践](https://github.com/bojieli/ai-agent-book): `book/chapter2.md`.

#### Lesson 18 · Skills and progressive disclosure

**Lesson ID:** `skills-disclosure`

**Level:** Core · **Status:** Available · **Difficulty:** Intermediate · **Time:** about 45 min · **Model:** calls a real model

**Prerequisites:** Lesson 17 Prompt caching and the stable prefix

Compare injecting all skill instructions at once with "a catalog plus on-demand loading", and test how precisely a skill is described affects whether it gets triggered.

**Terms in this lesson:** Progressive disclosure, Skill

**Sections**

1. **The more procedures, the longer the system prompt**: If you write every procedure into the system prompt, every request carries all …
2. **What a skill looks like**: A skill is a written procedure for the model, in two parts: a header and a body…
3. **Catalog first, load when needed**: Progressive disclosure splits a skill into two layers: only the catalog stays r…
4. **load_skill accepts only registered names**: load_skill's parameter is written by the model, and the runner uses it only to …
5. **The description decides whether a skill gets picked**: With on-demand loading, the model's only basis for deciding which skill to load…
6. **One more round trip, in exchange for a smaller resident context**: What on-demand loading saves is the resident cost; the price is one more reques…
7. **The resident catalog is the stable prefix**: The system prompt of on-demand loading holds only the catalog, so as long as yo…
8. **Limits: read the events, not the answer**: On-demand loading leaves "whether to use a skill" to the model, so whether a sk…

**Objectives**

- Explain how progressive disclosure shrinks the always-present context
- Implement on-demand loading with a skill catalog plus load_skill, reading only registered skills
- Use prompts that should not trigger a skill to test false triggers, and judge from the events whether it was loaded

**Topics**

- SKILL.md: name, description, and body
- Full injection vs. a skill catalog
- load_skill and the skill allowlist
- Missed triggers, false triggers, and loading the wrong skill
- Prompt tokens per request (from usage)
- The always-present catalog and the stable prefix

**Experiments**

Full injection vs. on-demand loading:

1. Run the same task first with everything injected (one request), then with the catalog plus load_skill (two requests when a skill is needed). Run making review cards and small talk once each.
2. From each request's record, read the prompt tokens and which skill bodies are in the context.
3. In the report, compare the per-request prompt tokens and totals of the two approaches, the load verdicts, and the format screening.

Deliverable: A prompt-token comparison table and loading records for the two approaches.

Description precision and triggering:

1. Change only the description of review-cards: a precise version and a vague one, "帮助学习。" ("Helps with learning.").
2. Run once each on making review cards (should load) and a review question (should not load), and record missed triggers and false triggers.
3. Compare the load verdicts and the format screening of the answers, and explain why you cannot tell from the answer alone whether the skill was loaded.

Deliverable: The load verdicts of four runs, and examples of false triggers.

**Acceptance**

- Every load maps to a specific request: the record states which request proposed it and which skill was loaded.
- At least one prompt that should not trigger a skill is correctly ignored, or is honestly recorded as a false trigger.
- Prompt tokens come from the provider-reported usage; when not reported, this is stated explicitly and not recorded as 0.

**References**

- [深入理解 AI Agent：设计原理与工程实践](https://github.com/bojieli/ai-agent-book): `book/chapter2.md`.
- [深入理解 AI Agent：设计原理与工程实践](https://github.com/bojieli/ai-agent-book): `book/chapter4.md`.

## R · Reasoning & control

From text actions to planning, reflection, and workflow patterns, compare the reliability and cost that each way of controlling the model brings.

### R1 · Action protocols and planning

Text actions compared with native calls, and TODO planning.

#### Lesson 19 · Text actions and native tool calling

**Lesson ID:** `text-actions`

**Level:** Core · **Status:** Available · **Difficulty:** Intermediate · **Time:** about 50 min · **Model:** calls a real model

**Prerequisites:** Lesson 7 Error handling and safety boundaries, Lesson 9 Structured output and business validation

Do the same set of tasks with a regex-parsed text protocol and with native tool_calls, and see how the model makes up an Observation when stop is removed.

**Terms in this lesson:** Function calling, Stop sequence, Observation, ReAct, Text action protocol

**Sections**

1. **The model only outputs text**: A model's output is just text. To make it "do something", the program first has…
2. **stop: make the model stop where it should**: In a text protocol, getting the model to stop after the action relies on the st…
3. **Without stop: the model writes the Observation for you**: Remove stop, and the model may keep writing and produce even the tool result an…
4. **Record parse failures; don't quietly fix them**: When the parser meets output that doesn't follow the format, it should record a…
5. **Native tool calling hands parsing to the provider**: Native tool calling hands the step of "finding the action in the text" to the p…
6. **Choosing between the two protocols**: Use native tool calling when you can, and keep text protocols for places that l…

**Objectives**

- Compare the reliability of the text action protocol and native tool calling
- Recognize an Observation the model made up
- Record parse failures instead of silently ignoring them

**Topics**

- The ReAct text format
- The stop sequence (stop)
- Parse-failure events
- finish_reason
- Native calls vs. the text protocol

**Experiments**

Two action protocols, one task:

1. For the same set of tasks, implement two runners: a regex text protocol and native tool calling.
2. Run the text protocol without the stop sequence, and put the Observation the model wrote next to the real tool result.
3. Count the parse-failure events and finish_reason values.

Deliverable: A record with the raw content and tool_calls side by side, and parse-failure counts.

**Acceptance**

- The interface shows the raw content and tool_calls side by side.
- The difference between a made-up Observation and the real result is backed by evidence.
- A parse failure is recorded as an event and not swallowed.

**References**

- [Hugging Face Agents Course](https://github.com/huggingface/agents-course): `units/en/unit1/actions.mdx`.
- [深入理解 AI Agent：设计原理与工程实践](https://github.com/bojieli/ai-agent-book): `book/chapter2.md`.

#### Lesson 20 · Planning: TODO lists and status reminders

**Lesson ID:** `todo-planning`

**Level:** Core · **Status:** Available · **Difficulty:** Intermediate · **Time:** about 50 min · **Model:** calls a real model

**Prerequisites:** Lesson 12 Application state and the run lifecycle, Lesson 19 Text actions and native tool calling

Have the agent keep a task list with todo_write. Compare completion with and without the list and with the reminder on and off, and judge it with an independent acceptance function.

**Terms in this lesson:** TODO list

**Sections**

1. **Why long tasks need a checklist**: The longer a task gets, the easier it is for the model to skip steps, because t…
2. **todo_write: replace as a whole, with a version**: Each time, todo_write receives the complete list and replaces the old one as a …
3. **Three arms: one addition at a time**: Each arm adds exactly one thing to the one before it, so any difference can be …
4. **Harness reminders: who is speaking**: A model may write a checklist and then never update it. The harness can count f…
5. **The validator decides completion**: A done on the checklist is the model's claim; whether the task is finished has …
6. **What a checklist can and can't prove**: What a checklist can prove is which step the model believed it had reached in e…

**Objectives**

- Break a multi-step task into trackable TODOs
- Tell the plan the model wrote apart from the reminder the harness injected
- Judge completion with an independent validator

**Topics**

- The todo_write tool
- TODO snapshots and diffs
- Reminders injected by the harness
- Rounds since the last update
- The completion verdict

**Experiments**

With and without TODO and reminders:

1. Run the same multi-step task under three conditions: "No TODO", "TODO, no reminder", and "TODO, with reminder".
2. Record each round's TODO snapshot and diff, and label the reminder as injected by the harness.
3. Use this lesson's independent acceptance function to decide whether the task finally completed, not the model's own claim.

Deliverable: The TODO timelines and acceptance results of three runs.

**Acceptance**

- The TODO snapshots can be replayed round by round.
- The interface labels the reminder as injected by the harness, not as model output.
- Completion is decided by the validator, not by what the model says.

**References**

- [Microsoft AI Agents for Beginners](https://github.com/microsoft/ai-agents-for-beginners): `07-planning-design/README.md`.
- [深入理解 AI Agent：设计原理与工程实践](https://github.com/bojieli/ai-agent-book): `book/chapter2.md`.

### R2 · Replanning and bounded revision

Revising the plan after a failure, and a bounded review loop.

#### Lesson 21 · Plan-and-execute and replanning

**Lesson ID:** `plan-and-replan`

**Level:** Core · **Status:** Available · **Difficulty:** Intermediate · **Time:** about 50 min · **Model:** calls a real model

**Prerequisites:** Lesson 20 Planning: TODO lists and status reminders

When the primary data source is set to fail at step 2, compare how a static plan, replanning after the failure, and a ReAct baseline perform.

**Terms in this lesson:** Plan-and-execute

**Sections**

1. **Why write a plan first**: An agent that thinks as it goes is flexible, but you only learn what it meant t…
2. **A plan is data you can validate**: The plan the planner outputs is a JSON object. The program validates it first a…
3. **A step that always fails**: In this lesson the primary score source is set to always fail, so all three str…
4. **Static plan: run it to the end**: A static plan is never changed once written, and execution continues even after…
5. **Replan after failure: go back with the error**: Replan after failure pauses when a step fails, goes back to the plan with the r…
6. **One validator for all three strategies**: All three strategies are judged by the same validator, and how well the plan is…
7. **When a plan up front is worth it**: Writing a plan first is worth it when the steps can be worked out in advance, w…

**Objectives**

- Tell plan versions apart from execution state
- Revise a plan after a failure, on good grounds
- Compare three strategies on the same task

**Topics**

- Plan versions
- Step dependencies and acceptance conditions
- The reason for a revision
- Plan diffs
- The ReAct baseline

**Experiments**

Three strategies when step 2 fails:

1. The primary data source always fails at step 2. This is a controlled fault hard-coded in the runner: the Python tool really executes and returns a failure, and the backup data source returns normally.
2. Run the static plan, replanning after the failure, and the ReAct baseline in turn.
3. Record the versioned plans, step states, plan diffs, and revision reasons. All three strategies are judged by the same validator.

Deliverable: A comparison of the plan versions and results of the three strategies.

**Acceptance**

- Every revision has a reason and a diff.
- Step states come from real execution results.
- The three strategies are compared on the same task and under the same acceptance criteria.

**References**

- [Microsoft AI Agents for Beginners](https://github.com/microsoft/ai-agents-for-beginners): `07-planning-design/README.md`.

#### Lesson 22 · Reflection, review, and bounded revision

**Lesson ID:** `reflection-revision`

**Level:** Core · **Status:** Available · **Difficulty:** Intermediate · **Time:** about 50 min · **Model:** calls a real model

**Prerequisites:** Lesson 21 Plan-and-execute and replanning

Compare a model's self-review with a review grounded in real test results, and put an iteration limit on the revision loop.

**Terms in this lesson:** Reflection, Iteration limit

**Sections**

1. **Something written in one shot needs a second look**: Reflection has an agent go back and check its own output, then revise it accord…
2. **This lesson's task: a regex that is easy to get wrong**: This lesson's task is to write a regular expression that matches student IDs. I…
3. **Model self-review: reading the same information again**: In the self-review arm, the same model reads its own regex once more. It has no…
4. **Test review: failing cases are the comments**: The test arm does not ask the model to review. The failing cases themselves are…
5. **Four reasons to stop**: A revision loop has to be able to stop. This lesson spells out four stop reason…
6. **Review evidence ranges from strong to weak**: The closer the review's basis is to real execution, the more reliable it is. Th…

**Objectives**

- Tell model self-review apart from external verification
- Structure the review result as JSON that can be checked
- Constrain revision with an iteration limit and a stop reason

**Topics**

- Differences between draft versions
- Review JSON and the rubric
- Validator output
- The stop reason
- Cumulative tokens

**Experiments**

Self-review vs. test results as the basis for review:

1. On the same small task (write a regular expression that matches a student ID), drive revision once with the model's self-review and once with real test results. The tests run Python's re.fullmatch on 9 fixed cases and do not run code the model wrote.
2. Set the iteration limit (1 to 3 rounds), and record each draft, the review comments, and the test results.
3. Check both arms' final versions against the same set of tests, and compare the stop reasons and cumulative usage.

Deliverable: Each draft version, the review records, the test results, and the stop reason.

**Acceptance**

- The stop reason is explicit: review passed, iteration limit reached, no change after revision, or the review output was malformed.
- A test-based review cites real test output.
- Cumulative usage comes from what the provider reported, and usage that was not reported is written as "not reported".

**References**

- [Microsoft AI Agents for Beginners](https://github.com/microsoft/ai-agents-for-beginners): `09-metacognition/README.md`.

### R3 · Workflow patterns

Chaining, routing, parallelization, orchestration, and review-and-revise.

#### Lesson 23 · Workflow patterns: prompt chaining, routing, and parallelization

**Lesson ID:** `workflow-patterns`

**Level:** Core · **Status:** Available · **Difficulty:** Intermediate · **Time:** about 50 min · **Model:** calls a real model

**Prerequisites:** Lesson 22 Reflection, review, and bounded revision

Compare three workflow patterns: a prompt chain with gates, routing over 20 human-labeled tickets, and serial vs. parallel execution.

**Terms in this lesson:** Prompt chaining, Routing, Workflow, Parallelization, Gate

**Sections**

1. **When the agent does not need to decide**: For a task whose steps can be written out in advance, you can fix the flow in t…
2. **Prompt chaining: a gate between steps**: Prompt chaining splits one task into several model calls in a fixed order, wher…
3. **Routing: the model outputs one label**: Routing first has the model classify the input, and then the program decides wh…
4. **Whether routing is good is decided by human annotation**: To tell whether a router is good, compare it against samples whose answers were…
5. **Parallel: it saves waiting, not calls**: Parallelization sends subtasks that do not depend on each other to the model at…
6. **How to choose a pattern**: To choose a pattern, first look at the shape of the task, then at how many extr…

**Objectives**

- Choose the workflow pattern that fits the task
- Evaluate routing with labeled data
- Measure the time difference that parallelization brings

**Topics**

- Prompt chaining
- Routing decisions and the fallback
- Parallel branches
- Confusion matrix
- Wall-clock time

**Experiments**

Prompt chaining, routing, and parallelization:

1. The prompt chain has three fixed steps, and each step's output must pass the program's gate before it becomes the next step's input. If the format is wrong, the chain stops at that step.
2. Test routing with 20 human-labeled tickets, and compute the accuracy and the confusion matrix. Labels outside the list take the fallback, and the original text is recorded.
3. Run the same three mutually independent subtasks serially and in parallel, and compare the wall-clock time.

Deliverable: The gate records, the routing confusion matrix, and the serial and parallel timelines.

**Acceptance**

- Routing accuracy comes from comparison against the labels.
- The parallel and serial times come from backend timestamps.
- The fallback path is recorded.

**References**

- [深入理解 AI Agent：设计原理与工程实践](https://github.com/bojieli/ai-agent-book): `book/chapter1.md`.

#### Lesson 24 · Orchestrator-workers and evaluator-optimizer

**Lesson ID:** `orchestrator-evaluator`

**Level:** Core · **Status:** Available · **Difficulty:** Intermediate · **Time:** about 50 min · **Model:** calls a real model

**Prerequisites:** Lesson 23 Workflow patterns: prompt chaining, routing, and parallelization

Implement two patterns: an orchestrator that splits a task among workers, and an evaluator that drives optimization. Measure the cost of the extra calls.

**Terms in this lesson:** Orchestrator-workers, Evaluator-optimizer

**Sections**

1. **From a fixed flow to dynamic splitting**: When you only know how to split the subtasks after reading the task, you can ha…
2. **The orchestrator's output is a plan: validate it, then dispatch**: The orchestrator's reply decides how many requests go out next, so like the pla…
3. **Keep the workers' input small**: Each worker gets only the one instruction the orchestrator gave it, plus the ke…
4. **One writes, one reviews, in turns with a limit**: Evaluator-optimizer has one role write and another review against a rubric. If …
5. **Whatever the program can determine, the program checks first**: Before asking the evaluator there is a program check. If the question's format …
6. **The call ledger: what the extra calls bought**: Before you call the model more times, you should be able to say how much more i…

**Objectives**

- Explain the N+1 call cost of orchestration
- Set max_iters for the evaluator-optimizer
- Track parallel worker requests separately on the timeline

**Topics**

- The plan artifact
- Parallel worker requests with branches
- The review verdict
- The iteration limit
- Cost accounting

**Experiments**

Orchestration and review-and-revise:

1. The orchestrator produces a plan, and the workers each send one parallel request carrying a branch in the same round.
2. The evaluator reviews and the generator revises, repeating within the iteration limit max_iters, and each round's review verdict is recorded.
3. Count the extra cost relative to a single call.

Deliverable: A request timeline with branches, the review records, and a cost comparison.

**Acceptance**

- Each worker's request is shown separately by branch on the timeline.
- Review and revision always stop within the iteration limit.
- Cost comes from actual usage.

**References**

- [深入理解 AI Agent：设计原理与工程实践](https://github.com/bojieli/ai-agent-book): `book/chapter1.md`.

## D · Knowledge & retrieval

Turn local documents into retrievable evidence, and build answers that cite their sources and recognize when the documents are not enough.

### D1 · Document processing and retrieval

Loading and chunking, then comparing keyword, vector, and hybrid retrieval.

#### Lesson 25 · Document loading and chunking

**Lesson ID:** `document-loading`

**Level:** Core · **Status:** Planned · **Difficulty:** Intermediate · **Time:** about 45 min · **Model:** calls a real model

**Prerequisites:** Lesson 9 Structured output and business validation, Lesson 11 Context components and the message protocol

Turn a fixed set of local documents into chunks that carry their source, compare chunking strategies, and mark the trust boundary of external text at load time.

**Terms in this lesson:** Chunking

**Sections**

1. **Why load and chunk first**: A model can't read a whole document set at once, so retrieval works on small chunks, and each chunk must point back to the original.
2. **Loading and cleanup**: Read local Markdown, text, and similar files as plain text, recording source path, title, and version.
3. **Chunk size and overlap**: Cut the same document with different sizes and overlaps, then compare the chunk count and sentences split across chunks.
4. **Chunk IDs and locating the original**: Each chunk has a stable ID and a line range, so later citations can be checked.
5. **External text is untrusted**: An "instruction" inside a document is just data; mark its trust level from the loading step.
6. **Failure cases**: Record empty documents, duplicate content, and parse failures separately instead of skipping them silently.

**Objectives**

- Keep each chunk's source, version, and location
- Compare chunk size and overlap trade-offs with real queries
- Tell document content apart from trusted program instructions

**Topics**

- Document loading and format cleanup
- Source path, title, and version
- Chunk size, overlap, and context
- Chunk IDs and locating the original text
- External text is untrusted
- Empty documents, duplicate content, and parse failures

**Experiments**

Chunking a fixed course document set:

1. Pick a small public set of course documents and record each document's path, version, and permitted use.
2. Generate chunks with two sets of chunking parameters, keeping title, source, and original position, and compare the evidence a cross-chunk question needs.
3. Add an empty document, duplicate paragraphs, and document text disguised as instructions, then check the loading log and trust marks.

Deliverable: A list of the fixed corpus, two chunk catalogs, and a log of loading exceptions.

**Acceptance**

- Every chunk can be traced back to a real document and position, and cleanup does not lose key source information.
- At least one cross-chunk query explains the information trade-off caused by chunk size or overlap.
- Instructions inside documents are marked as untrusted content, and empty documents and parse failures have explicit outcomes.

**References**

- [Hugging Face Agents Course](https://github.com/huggingface/agents-course): `units/en/unit2/llama-index/components.mdx`.
- [深入理解 AI Agent：设计原理与工程实践](https://github.com/bojieli/ai-agent-book): `book/chapter3.md`.

#### Lesson 26 · Keyword retrieval and BM25

**Lesson ID:** `keyword-retrieval`

**Level:** Core · **Status:** Planned · **Difficulty:** Intermediate · **Time:** about 45 min · **Model:** no model calls

**Prerequisites:** Lesson 25 Document loading and chunking

Retrieve over local documents with keywords and BM25, see the hits, ranking, and misses, and set up a comparable baseline for later vector retrieval.

**Sections**

1. **What retrieval has to answer**: Given a query, find the few chunks most likely to contain the answer, and explain why they rank first.
2. **Term frequency and inverse document frequency**: Common words get low weight and rare words get high weight. This is where BM25 starts.
3. **How to read a BM25 score**: Break a hit's score into its parts and see what length normalization does.
4. **Query set and hit table**: Mark the chunks each query should hit, then count top-k hits.
5. **Where misses come from**: Queries that use different wording or synonyms get missed. That is the problem vector retrieval is meant to solve.

**Objectives**

- Explain term frequency and inverse document frequency
- Implement BM25 retrieval and read the scores
- Record hits and misses with a query set

**Topics**

- Tokenization and stop words
- BM25 score
- top-k and ranking
- Misses caused by synonyms
- A retrieval baseline

**Experiments**

Keyword retrieval on one query set:

1. Mark the document chunks that each query in a set should hit.
2. Run BM25 retrieval and record the top-k results and scores.
3. Find the queries that were missed because the wording changed.

Deliverable: The query set, a hit table, and examples of misses.

**Acceptance**

- Every hit maps to a document chunk and a score.
- Each missed example comes with a reason.
- The query set and document version are recorded so the run can be repeated later.

**References**

- [Hugging Face Agents Course](https://github.com/huggingface/agents-course): `units/en/unit2/llama-index/components.mdx`.

#### Lesson 27 · Embeddings and vector retrieval

**Lesson ID:** `embedding-retrieval`

**Level:** Core · **Status:** Planned · **Difficulty:** Intermediate · **Time:** about 45 min · **Model:** calls a real model

**Prerequisites:** Lesson 26 Keyword retrieval and BM25

Turn document chunks into embeddings, retrieve by cosine similarity, and compare hits and misses with the keyword baseline on the same query set.

**Sections**

1. **An embedding is a list of numbers**: Map text to a vector. Texts with similar meaning get similar vectors.
2. **Cosine similarity**: Compare similarity by the angle between vectors, and read what the score range means.
3. **Build and save the index**: Record the embedding model, dimension, and document version so the index can be reused.
4. **Compare with keyword retrieval**: Compare hits on the same query set to see which queries each method handles well and which it misses.
5. **Cost and limits**: Generating embeddings calls a model, and vector retrieval is not necessarily better for queries with numbers or proper nouns.

**Objectives**

- Explain embeddings and semantic similarity
- Build and persist a vector index
- Compare against keyword retrieval on the same query set

**Topics**

- An embedding is a list of numbers
- Cosine similarity
- Vector index and persistence
- Metadata filtering
- Comparison with BM25

**Experiments**

Vector retrieval against the keyword baseline:

1. Generate embeddings for the document chunks and save the index.
2. Run vector retrieval on the same query set.
3. Compare the hits and misses of the two methods side by side.

Deliverable: A table comparing the hits of the two retrieval methods.

**Acceptance**

- The embedding model and dimension are recorded.
- Both retrieval methods use the same query set.
- Stale results are not reused after the index is updated.

**References**

- [Microsoft AI Agents for Beginners](https://github.com/microsoft/ai-agents-for-beginners): `05-agentic-rag/README.md`.

#### Lesson 28 · Hybrid retrieval and reranking

**Lesson ID:** `hybrid-retrieval`

**Level:** Core · **Status:** Planned · **Difficulty:** Intermediate · **Time:** about 45 min · **Model:** calls a real model

**Prerequisites:** Lesson 27 Embeddings and vector retrieval

Merge and rerank keyword and vector results, compare the three retrieval methods on one query set, and handle index updates and deletions.

**Terms in this lesson:** Vector retrieval, Hybrid retrieval

**Sections**

1. **Why mix**: Keyword and vector retrieval each miss some things, and merging the two result lists is usually steadier.
2. **Merging results (RRF)**: Merge by rank rather than score, because the two score scales differ.
3. **Reranking**: Use a more expensive model to reorder a small set of candidates, and compare hits before and after reranking.
4. **Metadata filtering and top-k**: Filter by source or time, then take the top k, and record what was filtered out.
5. **Index updates and deletions**: When a document changes or is deleted, its old chunks must stop being retrieved.

**Objectives**

- Build keyword and vector retrieval that can be inspected
- Compare recall and ranking of each strategy with fixed queries
- Maintain the index, metadata filters, and knowledge updates

**Topics**

- Merging results (RRF)
- Reranking
- Metadata filtering and top-k
- Index version, updates, and deletions
- The three methods on the same query set

**Experiments**

Comparing three retrieval methods on one question set:

1. Write exact-name queries, paraphrased queries, no-answer queries, and cross-chunk queries for the fixed documents, and mark the chunks each should hit.
2. Run keyword, vector, and hybrid strategies separately. Show the actual hits, scores, and sources each time, without directly comparing score scales that aren't comparable.
3. Change or delete one document and update the index, then check filtering, recovery after a restart, and that old chunks are invalidated.

Deliverable: A hit comparison table for the three methods and a record of index update checks.

**Acceptance**

- The results of each strategy can be viewed on their own, and hits and the generated answer are not folded into one score.
- The comparison uses the same corpus and queries, and can explain at least one strategy's advantage and one failure example.
- After an update or deletion, old chunks no longer count as current evidence, and the index version matches the sources.

**References**

- [Hugging Face Agents Course](https://github.com/huggingface/agents-course): `units/en/unit3/agentic-rag/invitees.mdx`.
- [Hugging Face Agents Course](https://github.com/huggingface/agents-course): `units/en/unit2/llama-index/components.mdx`.
- [深入理解 AI Agent：设计原理与工程实践](https://github.com/bojieli/ai-agent-book): `book/chapter3.md`.

### D2 · Evidence-based answers and iterative retrieval

Validate citations, then study bounded Agentic RAG.

#### Lesson 29 · RAG answers and citations

**Lesson ID:** `rag-citations`

**Level:** Core · **Status:** Planned · **Difficulty:** Intermediate · **Time:** about 45 min · **Model:** calls a real model

**Prerequisites:** Lesson 9 Structured output and business validation, Lesson 28 Hybrid retrieval and reranking

Give the model the chunks that were actually retrieved, generate traceable answers, and handle insufficient or conflicting sources.

**Terms in this lesson:** Retrieval-augmented generation, Citation

**Sections**

1. **Hand the retrieval results to the model**: Put retrieved chunks in the request, labeled separately from the question, so the model can tell documents from instructions.
2. **Citation format**: The answer writes chunk IDs, and the program checks that each cited ID exists.
3. **Does the citation really support the conclusion**: Existing is not supporting: check, citation by citation, whether the cited chunk contains what the answer claims.
4. **When sources are insufficient**: If retrieval finds no basis, say you don't know, rather than letting the model fill in the gap.
5. **Conflicts and freshness**: When two chunks disagree, the answer lists the disagreement and each chunk's source.
6. **Retrieval quality and generation quality are separate**: When an answer is wrong, first check whether retrieval found the evidence, then whether the model used it correctly.

**Objectives**

- Build the evidence chain from retrieval to answer
- Check that citations exist and support the conclusion
- Tell retrieval failures apart from evidence misuse

**Topics**

- Retrieval context and the generation prompt
- Chunk IDs, sources, and citation format
- Citation existence and support
- No answer and uncertainty
- Conflicting sources and freshness
- Separating retrieval quality from generation quality

**Experiments**

Questions with evidence, without evidence, and with conflicting sources:

1. Prepare fixed questions that can be answered, questions whose answer is not in the documents, and questions where two versions conflict, and mark the evidence scope of each.
2. Run retrieval and answering, and save the chunks actually sent to the model and each answer's citations.
3. Check one by one whether each citation exists and supports the conclusion, and check the stated explanation when sources are missing or conflicting.

Deliverable: A Q&A record, a citation check table, and a classification of retrieval and generation failures.

**Acceptance**

- Every citation points back to a chunk actually retrieved in this run, and none points to a source that was never provided.
- When sources are insufficient the answer says so, and conflicting sources are listed separately with their origin and limits.
- A retrieval miss and misuse after a hit are located separately, and a fluent answer does not stand in for sufficient evidence.

**References**

- [Hugging Face Agents Course](https://github.com/huggingface/agents-course): `units/en/unit3/agentic-rag/agentic-rag.mdx`.
- [Microsoft AI Agents for Beginners](https://github.com/microsoft/ai-agents-for-beginners): `05-agentic-rag/README.md`.
- [深入理解 AI Agent：设计原理与工程实践](https://github.com/bojieli/ai-agent-book): `book/chapter3.md`.

#### Lesson 30 · Agentic RAG and bounded iteration

**Lesson ID:** `agentic-rag`

**Level:** Advanced · **Status:** Planned · **Difficulty:** Intermediate · **Time:** about 45 min · **Model:** calls a real model

**Prerequisites:** Lesson 12 Application state and the run lifecycle, Lesson 29 RAG answers and citations

Let the model decide within a budget whether to rewrite the query, retrieve again, or stop, and use the same question set to judge whether the extra retrieval improves results.

**Terms in this lesson:** Agentic RAG

**Sections**

1. **What static RAG lacks**: When one retrieval finds nothing, a static flow has no chance to rewrite the query or search again.
2. **Retrieval as a tool**: Let the model decide when to retrieve and what to look for, so retrieval calls and results go into the trace.
3. **Query rewriting and sub-questions**: Split a complex question into sub-queries and see which piece of evidence each retrieval adds.
4. **Bounded iteration**: Limit the number and duration of retrievals, and stop honestly when the limit is reached.
5. **Comparison with static RAG**: On the same question set, compare accuracy, model calls, and cost to judge whether the extra retrieval is worth it.

**Objectives**

- Wrap retrieval as a tool with a clear contract
- Manage retrieval history and evidence coverage
- Set stop conditions for iteration and compare the gain

**Topics**

- Retrieval tool and query routing
- Query rewriting and sub-questions
- Observation feedback and evidence coverage
- Repeated queries and attempt records
- Budgets for calls, rounds, and time
- Static RAG vs. Agentic RAG

**Experiments**

Multi-hop document verification:

1. Pick questions that need two chunks to answer and questions with no answer, and record the static RAG baseline.
2. Give the agent the retrieval tool and the remaining budget, and let it save attempts and evidence before deciding its next step.
3. Compare citation correctness, repeated calls, and the number of calls, and check how the run ends when evidence is sufficient or the budget runs out.

Deliverable: A paired report of static and iterative retrieval, the retrieval trace, and the stop reasons.

**Acceptance**

- Every retrieval has an actual query and returned evidence, and the next action can be matched to an existing observation.
- Repeated searches and tasks with no answer end within budget and state why the task wasn't completed.
- The gain from extra calls is supported by fixed cases, and any regression and added cost are reported too.

**References**

- [Microsoft AI Agents for Beginners](https://github.com/microsoft/ai-agents-for-beginners): `05-agentic-rag/README.md`.
- [Hugging Face Agents Course](https://github.com/huggingface/agents-course): `units/en/unit3/agentic-rag/agent.mdx`.
- [深入理解 AI Agent：设计原理与工程实践](https://github.com/bojieli/ai-agent-book): `book/chapter3.md`.

## E · Frameworks & orchestration

Use one task to understand what LangChain wraps, then use LangGraph to express state, branches, and long-running tasks.

### E1 · LangChain comparison and adaptation

Map native models, tools, and result contracts onto it, and reuse mature components.

#### Lesson 31 · LangChain vs. the native implementation

**Lesson ID:** `langchain-vs-native`

**Level:** Core · **Status:** Planned · **Difficulty:** Intermediate · **Time:** about 50 min · **Model:** calls a real model

**Prerequisites:** Lesson 7 Error handling and safety boundaries, Lesson 11 Context components and the message protocol

Compare the native loop with LangChain on the same task and tools, and explain which messages, calls, and result handling the framework takes over.

**Sections**

1. **The same task, two implementations**: Take a task the native loop already did and do it again with LangChain.
2. **What the framework does for you**: Compare message formats, tool registration, and the loop, and mark every step the framework wraps.
3. **The request is still the same request**: Capture the request the framework actually sends and compare it field by field with the native request.
4. **Callbacks and a unified trace**: Use callbacks to feed the framework's internal steps into the platform's event record.
5. **Dependency versions**: Pin versions and record capability differences, so the comparison can be rerun after a framework upgrade.

**Objectives**

- Map the native model, messages, and tools to framework concepts
- Reuse the existing task and acceptance rules
- Locate where the wrapping is responsible, using raw and adapted events

**Topics**

- Model interface and provider adapters
- Framework messages vs. native messages
- Tool registration and the agent loop
- Deterministic chains vs. autonomous calls
- Callbacks and a unified trace
- Checking dependency versions and capabilities

**Experiments**

Redo an existing tool task with the framework:

1. Pick one normal task and one failing task from the first three lessons, keeping the model configuration, tool implementation, and budget the same.
2. Integrate LangChain through the official interface at a pinned version, and convert its callbacks into the existing event types.
3. Compare the requests, calls, errors, and results of the native and framework versions, keeping each one's raw data.

Deliverable: Paired traces of the two implementations and a table mapping framework responsibilities.

**Acceptance**

- Both implementations use the same task, tools, and acceptance rules, and failure cases are not hidden by framework defaults.
- You can say which work on messages, dispatch, and tool results the framework manages.
- Framework-adapted events and raw provider data can be viewed separately, and tool call evidence is not lost.

**References**

- [Microsoft AI Agents for Beginners](https://github.com/microsoft/ai-agents-for-beginners): `04-tool-use/README.md`.
- [深入理解 AI Agent：设计原理与工程实践](https://github.com/bojieli/ai-agent-book): `book/chapter1.md`.

#### Lesson 32 · LangChain tools and structured adapters

**Lesson ID:** `langchain-tools`

**Level:** Core · **Status:** Planned · **Difficulty:** Intermediate · **Time:** about 50 min · **Model:** calls a real model

**Prerequisites:** Lesson 9 Structured output and business validation, Lesson 31 LangChain vs. the native implementation

Plug existing business contracts into the framework's model, tool, and validation components, and compare the unified interface with the provider's raw response.

**Sections**

1. **Tool decorators and parameter schemas**: Generate a tool definition from type annotations and compare it with a hand-written JSON Schema.
2. **Structured results and parsers**: Let the framework parse the model output, and see how it reports errors when parsing fails.
3. **A unified interface and provider differences**: Behind one interface, different providers support different capabilities, so check them one by one.
4. **Error conversion and bounded repair**: On a parse failure, retry at most once and record the raw output.

**Objectives**

- Reuse business tools and output schemas
- Handle capability differences between the framework and providers
- Verify that the adapter does not weaken error and evidence semantics

**Topics**

- Tool decorators and typed schemas
- Structured results and parsers
- Unified model interface and capability differences
- Raw HTTP vs. framework data
- Error conversion and bounded repair
- Component reuse and dependency management

**Experiments**

Adapting tools for a structured learning task:

1. Register the existing task card schema and the retrieval tool through framework components, keeping business validation separate.
2. Use a normal sample, a missing-field sample, and a tool-error sample to compare the raw response, the framework output, and the final validation result.
3. Record what the current provider supports and what is unverified, and design an explicit fallback for unsupported capabilities.

Deliverable: Notes on the tool and result adapters, a capability matrix, and records of three kinds of samples.

**Acceptance**

- Both the framework's inputs and outputs and the raw provider data are available as viewable evidence.
- A valid schema cannot bypass business validation, and tool errors keep their explicit failure semantics.
- The capability matrix separates what was measured now, adapter fallbacks, and what is unverified, and does not broadly claim that providers behave identically.

**References**

- [Microsoft AI Agents for Beginners](https://github.com/microsoft/ai-agents-for-beginners): `04-tool-use/README.md`.
- [Hugging Face Agents Course](https://github.com/huggingface/agents-course): `units/en/unit3/agentic-rag/invitees.mdx`.
- [深入理解 AI Agent：设计原理与工程实践](https://github.com/bojieli/ai-agent-book): `book/chapter4.md`.

### E2 · LangGraph and concurrent runs

Build a state graph you can explain, and decide the boundaries for dependencies, concurrency, and cancellation.

#### Lesson 33 · LangGraph state and branching

**Lesson ID:** `langgraph-state`

**Level:** Core · **Status:** Planned · **Difficulty:** Intermediate · **Time:** about 50 min · **Model:** calls a real model

**Prerequisites:** Lesson 12 Application state and the run lifecycle, Lesson 32 LangChain tools and structured adapters

Describe the task flow with State, Node, and Edge, and orchestrate tool calls and validation as a graph with terminal states.

**Sections**

1. **Why draw it as a graph**: Branches, loops, and terminal states are easier to check as a graph than as nested ifs.
2. **State, Node, Edge**: State is shared data, nodes read and write it, and edges decide the next step.
3. **Conditional routing and tool nodes**: Pick the next edge from the state, and make a tool call a node.
4. **Loop budget and terminal states**: A loop in the graph needs a limit too, and every path must reach END.
5. **Node events and state diffs**: Record the state difference before and after each node, so a replay shows how the graph ran.

**Objectives**

- Design the state passed between nodes and its update rules
- Choose conditional branches from business state
- Verify that loops, failures, and the normal path all terminate

**Topics**

- State, Node, Edge, and StateGraph
- Typed state and updates
- Message merging and reducers
- Conditional routing and tool nodes
- Loop budget and START/END
- Node events and state diffs

**Experiments**

A plan, call, verify, answer graph:

1. First draw a task graph with normal, missing-argument, and failure branches, and define each node's input and update fields.
2. Implement the nodes and routing with LangGraph, and record model events, tool results, and state diffs in the same way.
3. Run each of three fixed inputs, checking branch conditions and loop termination, without random routing.

Deliverable: A state graph, node contracts, and three reproducible execution paths.

**Acceptance**

- Each path's branch maps to the state values at that moment, and the normal, missing-argument, and failure paths each have an explicit terminal state.
- State updates don't accidentally overwrite messages or evidence that should be kept, and the merge rules can be explained.
- Node state changes are not recorded as made-up model responses, and the loop is bounded by a program budget.

**References**

- [Hugging Face Agents Course](https://github.com/huggingface/agents-course): `units/en/unit2/langgraph/building_blocks.mdx`.
- [Hugging Face Agents Course](https://github.com/huggingface/agents-course): `units/en/unit2/langgraph/document_analysis_agent.mdx`.
- [深入理解 AI Agent：设计原理与工程实践](https://github.com/bojieli/ai-agent-book): `book/chapter1.md`.

#### Lesson 34 · Streaming and cancellation

**Lesson ID:** `streaming-cancel`

**Level:** Core · **Status:** Planned · **Difficulty:** Intermediate · **Time:** about 50 min · **Model:** calls a real model

**Prerequisites:** Lesson 6 Dependent calls across rounds, Lesson 12 Application state and the run lifecycle, Lesson 33 LangGraph state and branching

Receive model output chunk by chunk, tell apart a user pressing stop, a client disconnecting, and the backend actually finishing, and record what had already arrived when cancellation happened.

**Sections**

1. **What streaming is**: The model returns chunks as it generates, and time to first token affects the experience more than total time.
2. **Assembly and the final answer**: Join the chunks into the full answer, and check that its format matches the non-streaming result.
3. **Cancel requests**: After the user presses stop, no new chunks are accepted, and the part already received is recorded.
4. **Client disconnects and the backend run**: Closing the browser doesn't mean the backend stopped, so the terminal state must follow the backend's record.

**Objectives**

- Read the chunks of a streaming response
- Implement a cancellable streaming request
- Tell a cancel request, a disconnect, and the run's terminal state apart

**Topics**

- Stream chunks and time to first token
- Assembling the full answer
- Cancel requests
- Client disconnects and the backend run
- Recording partial results

**Experiments**

Cancelling a stream midway:

1. Run one full stream and record the time to first token and the chunks.
2. Cancel midway through the output and record the part already received.
3. Disconnect the client and confirm the backend's terminal state.

Deliverable: Three run records: complete, cancelled, and disconnected.

**Acceptance**

- Time to first token comes from real timing.
- No new chunks are recorded after cancellation.
- The run's terminal state matches what the frontend shows.

**References**

- [深入理解 AI Agent：设计原理与工程实践](https://github.com/bojieli/ai-agent-book): `book/chapter2.md`.

#### Lesson 35 · Parallelism, timeouts, and concurrency limits

**Lesson ID:** `async-concurrency`

**Level:** Advanced · **Status:** Planned · **Difficulty:** Intermediate · **Time:** about 50 min · **Model:** calls a real model

**Prerequisites:** Lesson 34 Streaming and cancellation

Check data dependencies first, then run independent tasks in parallel, set a concurrency limit and timeouts, and record partial results.

**Sections**

1. **First decide whether it can run in parallel**: Only tasks that don't depend on each other can run at the same time. Dependencies set the execution order.
2. **async/await and tasks**: Send requests in parallel with Python tasks, and compare wall-clock time with serial execution.
3. **Concurrency limit**: Cap the number of simultaneous requests to protect the provider's quota and local resources.
4. **Timeouts and partial results**: One task timing out doesn't bring down the whole run. Report which tasks finished and which timed out.
5. **Cancellation and terminal state**: Cancellation must reach every subtask, and the final terminal state must be consistent.

**Objectives**

- Decide which tool calls can run concurrently
- Handle timeouts, partial failures, and cancellation propagation
- Verify dependencies and terminal states with events

**Topics**

- Python async/await and tasks
- Independence and data dependencies
- Concurrency limit and resource budget
- Timeouts and partial results
- Cancel requests and execution terminal state

**Experiments**

Concurrent long tasks vs. cancellation:

1. Build two independent tools and one dependent tool, predict which parts can run concurrently, and record a serial baseline.
2. Set a concurrency limit, add one task that times out, and check the partial results, event order, and exception attribution.
3. Send a cancel request and disconnect the client separately, and check whether the backend tasks actually stop or keep running.

Deliverable: A dependency graph, a serial vs. parallel timing comparison, and lifecycle records for timeout and cancellation.

**Acceptance**

- A dependent tool runs only after the result it needs is valid, and the event evidence shows no data race.
- Timeouts and partial failures have explicit attribution, and concurrency never exceeds the set limit.
- A client disconnect or cancel request is not treated as the backend having already finished, and the final state can be checked independently.

**References**

- [深入理解 AI Agent：设计原理与工程实践](https://github.com/bojieli/ai-agent-book): `book/chapter6.md`.

### E3 · Approval, human-in-the-loop, and recovery

Add a gate before execution, pause and resume later, and recover from a checkpoint.

#### Lesson 36 · Hooks and approval gates

**Lesson ID:** `hooks-approval`

**Level:** Core · **Status:** Planned · **Difficulty:** Intermediate · **Time:** about 50 min · **Model:** calls a real model

**Prerequisites:** Lesson 35 Parallelism, timeouts, and concurrency limits

Add hooks and human approval before tool execution, so the run enters a paused state and resumes after approval or rejection.

**Sections**

1. **Why hooks**: Insert checks before and after a tool runs without changing every tool's code.
2. **Approval request**: A high-risk call first produces an approval card that states the tool, an argument summary, and the risk.
3. **Pause and resume**: The run stops at the approval point and continues from there after approval, or ends honestly after rejection.
4. **The argument summary must resist substitution**: What gets approved is the set of arguments the summary stands for, so check it once more before execution.

**Objectives**

- Tell a hook's stage from its verdict
- Implement approval that can pause and resume
- Make the approval summary match the actual arguments

**Topics**

- Hook stages and handlers
- Approval request and decision
- Pause and resume
- Risk level
- Normalized argument summary

**Experiments**

Approval before a high-risk tool:

1. Add an approval gate to an example tool that writes a file.
2. The run enters paused, the learner approves or rejects in the UI, and the run resumes or ends accordingly.
3. Check that the approval summary matches the arguments actually executed.

Deliverable: The approval card record and the pause and resume timeline.

**Acceptance**

- The tool has not run before approval.
- After a rejection the run ends honestly and gives the reason.
- The approval summary matches the actual arguments item by item.

**References**

- [Microsoft AI Agents for Beginners](https://github.com/microsoft/ai-agents-for-beginners): `06-building-trustworthy-agents/README.md`.
- [深入理解 AI Agent：设计原理与工程实践](https://github.com/bojieli/ai-agent-book): `book/chapter4.md`.

#### Lesson 37 · Human-in-the-loop, checkpoints, and recovery

**Lesson ID:** `human-in-the-loop`

**Level:** Advanced · **Status:** Planned · **Difficulty:** Intermediate · **Time:** about 50 min · **Model:** calls a real model

**Prerequisites:** Lesson 33 LangGraph state and branching, Lesson 35 Parallelism, timeouts, and concurrency limits

Pause before actions with side effects, use checkpoints to save the execution position, and verify recovery after a restart or a human edit.

**Terms in this lesson:** Human-in-the-loop, Checkpoint, Idempotency

**Sections**

1. **When a person is needed**: When an action has side effects, can't be undone, or lacks evidence, hand the decision to a person.
2. **Checkpoints**: Save the execution position and state, so a pause can be resumed exactly.
3. **Editing state by hand**: A person can change arguments or the plan, and the edit itself must be recorded.
4. **Recovery after a restart**: After a process restart, continue from the checkpoint without repeating completed side effects.
5. **Recovery permissions and error paths**: Who may resume and what happens when resuming fails both need explicit rules.

**Objectives**

- Tell pausing, terminal states, and resumable execution apart
- Manage checkpoints and thread IDs
- Verify that completed side effects are not repeated on recovery

**Topics**

- Checkpoint and thread ID
- Pausing and human input
- Inspecting and editing state
- Process restart and recovery position
- Confirmation before side effects (see Lesson 42 for idempotency details)
- Recovery permissions and error paths

**Experiments**

Confirming before saving an exercise, and restart recovery:

1. Build a graph that generates an exercise and waits for confirmation before saving, and record a unique operation ID for the save action.
2. Inspect or edit the state at the pause, then resume; also run one resume after pausing and restarting.
3. Check the completed nodes, the actual number of saves, and the failure recovery path, and record what the framework and the business logic each guarantee.

Deliverable: Checkpoint records, the trail of human edits, and a table checking side effects after a restart.

**Acceptance**

- A paused state can be told apart from normal and failed terminal states, and recovery uses the correct session and thread.
- A human edit can be traced in later state and results, and actions that weren't confirmed did not run.
- Recovery does not save an already completed result twice, and the existence of a checkpoint alone does not justify claiming that every external action is naturally idempotent.

**References**

- [Hugging Face Agents Course](https://github.com/huggingface/agents-course): `units/en/unit2/langgraph/building_blocks.mdx`.
- [深入理解 AI Agent：设计原理与工程实践](https://github.com/bojieli/ai-agent-book): `book/chapter6.md`.
- [深入理解 AI Agent：设计原理与工程实践](https://github.com/bojieli/ai-agent-book): `book/chapter4.md`.

## K · Coding agents & sandboxes

Let an agent run commands and edit files in an isolated environment, with the platform doing the acceptance check independently.

### K1 · Commands, files, and change evidence

Sandboxed command execution and file edits that can be verified.

#### Lesson 38 · A single-bash-tool coding agent and its sandbox

**Lesson ID:** `bash-coding-agent`

**Level:** Core · **Status:** Planned · **Difficulty:** Challenge · **Time:** about 60 min · **Model:** calls a real model

**Prerequisites:** Lesson 36 Hooks and approval gates

In a fixture repository with a failing test, let the agent fix the code with a single bash tool, and have the platform rerun the tests for acceptance.

**Sections**

1. **Task and acceptance**: The fixture repository has one failing test. The agent fixes it, and the platform reruns the tests for acceptance.
2. **One bash tool is enough**: Give the agent a single tool that runs commands, and watch how it reads files, edits code, and runs tests.
3. **Temporary workspace and environment cleanup**: Run in an isolated directory that doesn't inherit the machine's secrets or environment variables.
4. **Timeouts and killing the process tree**: When a command hangs, time it out and end every child process it started.
5. **Command policy and output truncation**: Dangerous commands are denied by default. Long output keeps only the head and tail, with the truncation marked.
6. **"I fixed it" doesn't count**: The result of the platform's rerun is what counts. Record the commands, exit codes, and diffs.

**Objectives**

- Set a workspace, timeout, and environment variable cleanup for command execution
- Record command evidence rather than trust the agent's own account
- Let the platform do the acceptance check independently

**Topics**

- Independent temporary workspace
- Environment variable cleanup
- Timeouts and killing the process tree
- Command policy verdicts
- Head-and-tail output truncation

**Experiments**

Fixing the failing test in a fixture repository:

1. Create an independent temporary workspace for each run and copy in the fixture repository with the failing test.
2. The agent has only one bash tool. Record each command's cwd, policy verdict, exit code, head and tail of output, and duration.
3. When the run ends, the platform reruns pytest to decide whether the bug is fixed.

Deliverable: Command records, file diffs, and the platform's acceptance result.

**Acceptance**

- Child processes can't get any secrets.
- A timeout terminates the whole process tree.
- The acceptance result comes from tests the platform reruns.

**References**

- [深入理解 AI Agent：设计原理与工程实践](https://github.com/bojieli/ai-agent-book): `book/chapter5.md`.

#### Lesson 39 · File tools, edit strategies, and change evidence

**Lesson ID:** `file-edit-evidence`

**Level:** Core · **Status:** Planned · **Difficulty:** Challenge · **Time:** about 60 min · **Model:** calls a real model

**Prerequisites:** Lesson 38 A single-bash-tool coding agent and its sandbox

Replace bash file editing with dedicated read, write, and edit tools, compare edit strategies, and prove changes with before-and-after hashes and diffs.

**Sections**

1. **Why not edit files with bash**: Dedicated read and write tools can validate paths and record content before and after, which makes errors easier to locate.
2. **Whole-file writes and local replacements**: Compare the success rate and risk of the two edit methods on large files.
3. **Before-and-after hashes and diffs**: Use hashes to prove a file really changed and a diff to show what changed.
4. **Conflict and staleness detection**: If the file was changed after it was read, the edit must be rejected instead of overwriting it.

**Objectives**

- Design safe file read, write, and edit tools
- Compare whole-file rewrites with local replacements
- Leave change evidence with hashes and diffs

**Topics**

- Path validation
- Whole-file writes and local replacements
- Before-and-after hashes
- Unified diff
- Conflict and staleness detection

**Experiments**

Comparing two edit strategies:

1. Do the same editing task once with a whole-file rewrite and once with local replacement.
2. Record the before-and-after hashes and the unified diff of each change.
3. Simulate the file being changed externally after it was read, and check whether the tool detects that it is stale.

Deliverable: Diff records for the two strategies and the staleness detection results.

**Acceptance**

- Every path is resolved and confined to the workspace.
- Every change has before-and-after hashes and a diff.
- A stale write is rejected instead of overwriting the file.

**References**

- [深入理解 AI Agent：设计原理与工程实践](https://github.com/bojieli/ai-agent-book): `book/chapter5.md`.

## F · Quality & reliability

Judge and improve an agent's behavior with independent evaluation, real observation, and constraints on the execution side.

### F1 · Evaluation sets and validators

Build a fixed question set and held-out cases, and tell apart finished, correct, and well-evidenced.

#### Lesson 40 · Independent evaluation sets and validators

**Lesson ID:** `evaluation-sets`

**Level:** Core · **Status:** Planned · **Difficulty:** Intermediate · **Time:** about 50 min · **Model:** calls a real model

**Prerequisites:** Lesson 8 Task goals and acceptance

Build independent validators, a fixed question set, and held-out cases on tasks that already work, compare versions, and keep every failure record.

**Terms in this lesson:** Evaluation

**Sections**

1. **One successful run doesn't mean it works**: Only a fixed question set and a held-out set let you compare which of two versions is better.
2. **Validators and scoring rules**: Judge with a program whenever a program can, and write the rules in the scoring sheet.
3. **Results, traces, and evidence**: Look beyond the final answer: also check what was called and what the answer rests on.
4. **Judge model and human calibration**: Before scoring with a judge model, check how well it agrees with human annotation.
5. **Structured comparison of tool calls**: Parse and compare call names and arguments, in four kinds: simple, multiple, parallel, and calls that shouldn't happen.
6. **Variance and regression**: Run the same version several times to see the variance, and make a new version pass the old failure cases.

**Objectives**

- Design a task set that covers normal and edge cases
- Verify correctness, evidence, and violations separately
- Find improvements and regressions by comparing versions

**Topics**

- Task-specific rubric
- Fixed set, held-out set, and case versions
- Run completed vs. task succeeded
- Checking results, traces, and evidence
- LLM-as-a-judge and human calibration
- Regression, failure attribution, and sample variance

**Experiments**

Independent regression evaluation of the first three lessons:

1. Pick tool tasks that already run, and write cases covering normal, dependent, failing, no-tool-needed, and missing-evidence situations.
2. Have a validator outside the agent check the actual calls, argument sources, errors, and answers, and mark unevaluable items.
3. Change only one prompt or piece of code, run the fixed set and the held-out cases, and keep both the improvements and the regressions.

Deliverable: A versioned question set, independent validators, and a complete version comparison report.

**Acceptance**

- Scoring rests on predefined criteria and run evidence, and an agent's self-score cannot stand in for accuracy.
- Run finished, task correct, evidence sufficient, and process violations are shown separately.
- Held-out cases were not used for tuning, and failures and unevaluable items are kept rather than counting only hand-picked successes.

**References**

- [深入理解 AI Agent：设计原理与工程实践](https://github.com/bojieli/ai-agent-book): `book/chapter7.md`.
- [深入理解 AI Agent：设计原理与工程实践](https://github.com/bojieli/ai-agent-book): `chapter1/context/grounding.py`.
- [Hugging Face Agents Course](https://github.com/huggingface/agents-course): `units/en/unit4/hands-on.mdx`.

### F2 · Observability and usage

Connect run events, latency, failure attribution, and the usage the provider actually reports.

#### Lesson 41 · Observability, usage, and cost

**Lesson ID:** `observability-cost`

**Level:** Core · **Status:** Planned · **Difficulty:** Intermediate · **Time:** about 50 min · **Model:** calls a real model

**Prerequisites:** Lesson 12 Application state and the run lifecycle, Lesson 40 Independent evaluation sets and validators

Correlate the requests, tools, state, latency, and usage of one real run, and use the raw data to find repeated calls and slow steps.

**Terms in this lesson:** Observability, Span

**Sections**

1. **The whole picture of one run**: String requests, tools, state, and timing into one trace, layered by span.
2. **Finding slow steps and repeated calls**: Locate the slowest step and the repeated requests from real data.
3. **Usage and cost**: Separate provider-reported usage, local estimates, and unknown usage, and compute cost by price version.
4. **Caching and optimization regressions**: After an optimization, rerun the same question set to confirm it saved money without getting worse.

**Objectives**

- Tell a whole trace from a single-step span
- Record real timing, usage, and failure attribution
- Compare optimizations without letting quality regress

**Topics**

- Trace, span, and correlation IDs
- Model, tool, and state events
- Raw HTTP vs. adapter-layer data
- End-to-end and per-step latency
- Measured, estimated, and unknown usage
- Price versions, caching, and optimization regressions

**Experiments**

Locating a slow run and repeated calls:

1. For a fixed task, record the actual duration of the whole run and of each step, the number of requests, the usage from the raw response, and the terminal state.
2. Use a mature observability component or a unified inspector to find slow steps and repeated calls, and keep usage unknown where it is missing.
3. Change only one call or caching strategy, rerun the same question set, and compare quality, latency, and usage together.

Deliverable: An expandable full trace, an explanation of the performance bottleneck, and a before-and-after quality report for the optimization.

**Acceptance**

- Every statistic traces back to actual events, times, or raw usage, and unknown values are never written as zero.
- An estimated cost carries the model, the price source, and the date, and is not presented as a provider bill.
- After an optimization the same acceptance cases still run, and quality regressions and changes in failures are reported.

**References**

- [Hugging Face Agents Course](https://github.com/huggingface/agents-course): `units/en/bonus-unit2/what-is-agent-observability-and-evaluation.mdx`.
- [深入理解 AI Agent：设计原理与工程实践](https://github.com/bojieli/ai-agent-book): `book/chapter7.md`.
- [深入理解 AI Agent：设计原理与工程实践](https://github.com/bojieli/ai-agent-book): `chapter7/agent-cost-analysis/tracer.py`.

### F3 · Reliable tools and trust boundaries

Control the effects of retries, idempotency, permissions, and untrusted text.

#### Lesson 42 · Reliable tools, retries, and idempotency

**Lesson ID:** `reliable-tools`

**Level:** Core · **Status:** Planned · **Difficulty:** Intermediate · **Time:** about 50 min · **Model:** no model calls

**Prerequisites:** Lesson 7 Error handling and safety boundaries, Lesson 9 Structured output and business validation, Lesson 40 Independent evaluation sets and validators

Handle read and write tools separately, and verify timeouts, bounded retries, idempotency, and failure receipts on real local tools.

**Sections**

1. **Treat reads and writes differently**: A read can be retried. Before retrying a write, confirm it won't run twice.
2. **Timeouts and error classification**: Separate transient errors worth retrying from argument errors that should not be retried.
3. **Bounded retries and backoff**: Both the number of retries and the interval have limits, and every attempt is recorded.
4. **Idempotency keys**: Give the same operation the same key, and a repeated submission runs only once.
5. **Partial completion and compensation**: When a multi-step write fails midway, say which steps took effect and how to compensate.

**Objectives**

- Classify transient failures and errors that must not be retried
- Limit retries and keep each actual result
- Avoid re-running side effects that already completed

**Topics**

- Reads vs. writes
- Timeouts and error classification
- Retry limit and backoff
- Idempotency keys and operation records
- Result validation and degradation
- Partial completion and the boundary of compensation

**Experiments**

Fault recovery for a save-exercise tool:

1. Implement a narrow tool that writes local exercise records, saving a unique ID and the actual result for each operation.
2. Inject controlled transient failures and business rejections into the real file or storage operation, and run bounded retries by category.
3. Submit the same operation repeatedly and check the file, the database, and the tool result, then explain how partial completion is handled.

Deliverable: An error classification, a retry trace, and a table checking the actual number of writes.

**Acceptance**

- Business rejections and invalid arguments don't enter pointless retries, and transient failures are bounded by an attempt and time budget.
- A repeated operation did not create multiple real records, and the basis for idempotency can be seen in storage.
- Failure, degradation, and partial completion are all stated explicitly, and a written final answer alone never justifies claiming the write succeeded.

**References**

- [深入理解 AI Agent：设计原理与工程实践](https://github.com/bojieli/ai-agent-book): `book/chapter4.md`.
- [深入理解 AI Agent：设计原理与工程实践](https://github.com/bojieli/ai-agent-book): `book/chapter5.md`.
- [Microsoft AI Agents for Beginners](https://github.com/microsoft/ai-agents-for-beginners): `04-tool-use/README.md`.

#### Lesson 43 · Prompt injection and tool permissions

**Lesson ID:** `prompt-injection`

**Level:** Core · **Status:** Planned · **Difficulty:** Intermediate · **Time:** about 50 min · **Model:** calls a real model

**Prerequisites:** Lesson 25 Document loading and chunking, Lesson 29 RAG answers and citations, Lesson 42 Reliable tools, retries, and idempotency

Bring untrusted documents into a real retrieval chain, observe how injection affects the model, and let the execution side control tools, paths, and side effects.

**Terms in this lesson:** Prompt injection

**Sections**

1. **Instructions inside documents**: Retrieved web pages and files may hide text like "ignore the previous rules".
2. **Direct and indirect injection**: A user saying it directly and a document smuggling it in are different attack paths, with defenses in different places.
3. **Test with a real model**: Put the injected documents into the retrieval chain and record whether the model went along.
4. **Permissions on the execution side**: The program decides tools, paths, and side effects. What prompts can't stop, permissions stop.
5. **Failing closed and regression**: Stop the injection without hurting normal tasks.

**Objectives**

- Mark the boundary between trusted instructions and untrusted data
- Verify that permissions take effect on the program's execution side
- Evaluate the trade-offs of defenses with attack and normal cases

**Topics**

- Direct and indirect prompt injection
- Trust levels of documents and tool results
- Permissions for tools, paths, and actions
- Input and output business validation
- Side-effect confirmation and audit
- Failing closed and regression on normal tasks

**Experiments**

Indirect injection in course documents:

1. Add text to the fixed documents that asks to ignore the task, read a file out of bounds, or call an unauthorized action, and record its source and trust level.
2. Run Q&A with a real model, keeping the actions the model actually proposes, and check the execution-side allowlist, path, and confirmation constraints.
3. Rerun the same question set with normal documents and several kinds of distracting text, and record blocked operations, false rejections, and remaining risk.

Deliverable: A trust boundary diagram, real injection test records, and a permission check report.

**Acceptance**

- Instructions in documents cannot change the tools or file scope the program grants, and unauthorized operations did not actually run.
- Cases where the model did not propose a dangerous call are recorded as such, and are not passed off as evidence of execution-side blocking.
- Normal tasks get regression checks, and a defense is not proven by the prompt, a keyword gate, or the model's verbal promise alone.

**References**

- [深入理解 AI Agent：设计原理与工程实践](https://github.com/bojieli/ai-agent-book): `book/chapter2.md`.
- [深入理解 AI Agent：设计原理与工程实践](https://github.com/bojieli/ai-agent-book): `book/chapter4.md`.

## G · Protocols & tool services

Understand how MCP connects tool services, and manage real protocol calls and the connection lifecycle.

### G1 · MCP principles and tool integration

Reuse existing business tools to do service discovery and calls.

#### Lesson 44 · MCP basics and tool integration

**Lesson ID:** `mcp-basics`

**Level:** Core · **Status:** Planned · **Difficulty:** Intermediate · **Time:** about 45 min · **Model:** calls a real model

**Prerequisites:** Lesson 7 Error handling and safety boundaries, Lesson 9 Structured output and business validation, Lesson 43 Prompt injection and tool permissions

Use the official SDK to expose an existing course retrieval tool as a service, complete real discovery, calls, and error return, and tell the protocol apart from agent scheduling.

**Terms in this lesson:** Model Context Protocol

**Sections**

1. **What problem MCP solves**: Make a tool an independent service that any client supporting the protocol can discover and call.
2. **Client, server, and transport**: Local processes talk over standard input and output, so you can see the raw messages of one call.
3. **Tool discovery and input schema**: The client lists the tools first, then calls them according to the schema.
4. **Protocol errors vs. business failures**: A failed connection and a tool returning an error are different things, recorded separately.
5. **Permission boundary**: What the service can do is decided by the server. The client can only make requests.

**Objectives**

- Explain the roles of the MCP client, server, and agent
- Discover and call an existing tool through the real protocol
- Keep evidence of the tool schema, results, and exceptions

**Topics**

- MCP vs. plain function calling
- Client, server, and transport
- Tool discovery and input schema
- Real calls and returning results
- Protocol errors vs. business failures
- Permission boundary and SDK version

**Experiments**

A course retrieval MCP service:

1. Reuse the existing narrow retrieval function and its input schema, and build a minimal server and client with the official SDK at a pinned version.
2. Actually establish a connection, list the tools, and call retrieval, then test invalid arguments and a business no-result case.
3. Connect the service's tool to the existing agent, and view the protocol record, the model's decisions, and the actual retrieval evidence separately.

Deliverable: A minimal MCP service that can be called, discovery and call records, and a note on how responsibilities are layered.

**Acceptance**

- Tool discovery and calls come from real protocol exchanges, and a running process is not evidence of connectivity.
- The schema, tool arguments, results, and errors can all be traced, and protocol faults are kept apart from business no-result cases.
- You can explain that MCP provides the connection and the tool contract, while the agent and the program decide whether and when to call and when to stop.

**References**

- [深入理解 AI Agent：设计原理与工程实践](https://github.com/bojieli/ai-agent-book): `book/chapter4.md`.
- [深入理解 AI Agent：设计原理与工程实践](https://github.com/bojieli/ai-agent-book): `chapter4/DOCKER_DEPLOYMENT.md`.

### G2 · Connection lifecycle and cross-process delegation

Manage connections to several services, and compare how MCP and A2A divide the work.

#### Lesson 45 · MCP connection lifecycle and multiple servers

**Lesson ID:** `mcp-lifecycle`

**Level:** Advanced · **Status:** Planned · **Difficulty:** Intermediate · **Time:** about 45 min · **Model:** calls a real model

**Prerequisites:** Lesson 35 Parallelism, timeouts, and concurrency limits, Lesson 44 MCP basics and tool integration

Manage the connections, naming, exit, and reconnection of several tool servers, and verify state and permissions in real disconnects.

**Sections**

1. **The lifecycle of a connection**: Start, initialize, call, close: every step can fail.
2. **Multiple servers and naming**: When two servers both have a tool called search, use a namespace to tell them apart.
3. **Disconnect and reconnect**: After a server process crashes, restart it and discover its tools again.
4. **A changed tool list must be reconfirmed**: When a server updates its tool definitions, the client must notice the change instead of keeping the old ones.

**Objectives**

- Manage connection setup, closing, and reconnection
- Resolve tool name and permission conflicts across servers
- Keep a clear run state when a server fails

**Topics**

- Server registration and namespaces
- Connection, process, and session lifecycle
- Differences between stdio and remote transport
- Timeout, disconnect, and reconnect strategy
- Server-level permissions and identity
- Multi-server budgets and availability probes

**Experiments**

Discovery, disconnect, and recovery across two servers:

1. Start two tool servers with different responsibilities, and register their server IDs, tool namespaces, and minimal permissions.
2. Have the agent finish a task that needs both kinds of tools, then actually stop one of the servers and observe the calls and connection state.
3. Reconnect or degrade within the budget, close all connections, and check for leftover processes, repeated side effects, and the task's terminal state.

Deliverable: A multi-server registry, a disconnect and recovery trace, and exit check records.

**Acceptance**

- Tools with the same name can be told apart exactly by server ID, and discovery information doesn't grant extra permissions.
- A server stopping is recorded as a connection or call failure, and reconnection is bounded and doesn't repeat completed writes.
- When the task ends, connections and child processes are released as agreed, and a state probe can verify that the tools are actually available.

**References**

- [深入理解 AI Agent：设计原理与工程实践](https://github.com/bojieli/ai-agent-book): `book/chapter4.md`.
- [深入理解 AI Agent：设计原理与工程实践](https://github.com/bojieli/ai-agent-book): `chapter4/docker-compose.yml`.
- [深入理解 AI Agent：设计原理与工程实践](https://github.com/bojieli/ai-agent-book): `chapter4/DOCKER_DEPLOYMENT.md`.

#### Lesson 46 · A2A and cross-process delegation

**Lesson ID:** `a2a-delegation`

**Level:** Elective · **Status:** Planned · **Difficulty:** Intermediate · **Time:** about 45 min · **Model:** calls a real model

**Prerequisites:** Lesson 45 MCP connection lifecycle and multiple servers

Let agents in two independent processes delegate tasks through the A2A protocol, and observe capability discovery, task state, and returned results.

**Sections**

1. **How agents collaborate**: One agent hands a task to an agent in another process, rather than just calling a tool.
2. **Capability discovery**: Learn what the other side can do through its Agent Card.
3. **Task state and returned results**: A delegated task has its own state, and a returned result must match the task.
4. **Difference from MCP**: MCP connects tools and A2A connects agents. The two can be used together.

**Objectives**

- Explain how A2A and MCP divide the work
- Trace state changes of a cross-process task
- Handle delegation failures and timeouts

**Topics**

- Agent Card and capability discovery
- Task state
- Cross-process messages
- Failures and timeouts
- Comparison with MCP

**Experiments**

Delegation between two local agents:

1. Start agents in two independent processes on the local machine, and have one delegate a subtask to the other through A2A.
2. Record capability discovery, task state changes, and the returned result.
3. Make the delegate time out, and check how the delegator handles it.

Deliverable: A cross-process delegation timeline and a record of how failures were handled.

**Acceptance**

- Task state changes can be replayed.
- A timeout is handled explicitly, with no endless waiting.
- You can explain why this scenario uses A2A rather than MCP.

**References**

- [Microsoft AI Agents for Beginners](https://github.com/microsoft/ai-agents-for-beginners): `11-agentic-protocols/README.md`.

## H · Capstone & delivery

Compare the benefits and costs of multiple agents, and deliver a local study assistant that has passed acceptance.

### H1 · Multi-agent division of work and coordination

Design delegation, context isolation, result merging, and the overall budget.

#### Lesson 47 · Multi-agent patterns and trade-offs

**Lesson ID:** `multi-agent-patterns`

**Level:** Advanced · **Status:** Planned · **Difficulty:** Challenge · **Time:** about 60 min · **Model:** calls a real model

**Prerequisites:** Lesson 12 Application state and the run lifecycle, Lesson 33 LangGraph state and branching, Lesson 40 Independent evaluation sets and validators

Compare a single agent, a fixed workflow, role switching, and independent multi-agent setups on the same task, and judge the benefit of splitting from evidence.

**Terms in this lesson:** Multi-agent

**Sections**

1. **First ask whether to split**: Multiple agents add calls and coordination cost, so you need evidence that splitting pays off.
2. **Ways to organize**: What kinds of task the manager, peer, and hierarchical patterns each suit.
3. **Context isolation**: A subagent sees only the context it needs, which cuts distraction but can also lose information.
4. **Comparison on one question set**: Compare quality and cost of a single agent, a fixed workflow, and multiple agents on the same question set.

**Objectives**

- Tell role prompts from independently running agents
- Choose a collaboration pattern that matches the task's complexity
- Compare quality, latency, and extra calls

**Topics**

- Single agent and deterministic workflows
- Role switching and context isolation
- Manager, peer, and hierarchical patterns
- Planning and execution roles
- Collaboration overhead and failure types
- A shared question set and baseline comparison

**Experiments**

Comparing patterns for research, question writing, and review:

1. For the study-assistant task, fix the input, the evidence scope, and the acceptance set, and first record the single-agent and plain-workflow baselines.
2. Run role switching and independent research, question-writing, and review roles with a real model, keeping the total budget comparable.
3. Count evidence correctness, task completion, number of calls, and merge errors, and explain when splitting is worth it.

Deliverable: A task graph for the four patterns and a paired quality and cost report.

**Acceptance**

- Role switching and independent agents can be told apart exactly by context, tools, and run identity.
- A multi-agent benefit is supported with the same cases, and the extra calls and failures are reported too.
- A task with no benefit or one over budget can reasonably stay with a single agent, and the number of roles is not a measure of capability.

**References**

- [深入理解 AI Agent：设计原理与工程实践](https://github.com/bojieli/ai-agent-book): `book/chapter10.md`.
- [Hugging Face Agents Course](https://github.com/huggingface/agents-course): `units/en/unit2/smolagents/multi_agent_systems.mdx`.
- [Microsoft AI Agents for Beginners](https://github.com/microsoft/ai-agents-for-beginners): `STUDY_GUIDE.md`.

#### Lesson 48 · Delegation, context merging, and budgets

**Lesson ID:** `delegation-budget`

**Level:** Advanced · **Status:** Planned · **Difficulty:** Challenge · **Time:** about 60 min · **Model:** calls a real model

**Prerequisites:** Lesson 35 Parallelism, timeouts, and concurrency limits, Lesson 41 Observability, usage, and cost, Lesson 47 Multi-agent patterns and trade-offs

Specify inputs, outputs, evidence, and stop conditions for subtasks, isolate their context, and verify merged results and the shared budget.

**Sections**

1. **Subtask contract**: A task handed off states its inputs, outputs, evidence, and stop conditions.
2. **Merging results and conflicts**: When merging subtask results, list conflicts instead of picking one arbitrarily.
3. **Shared budget**: Split the global budget among subtasks, so that any one of them overspending can be stopped.
4. **Cancellation propagation**: When the main task is cancelled, the subtasks stop together.

**Objectives**

- Design a delegation contract that can be checked at acceptance
- Keep handoff evidence and avoid polluting the context
- Control global and subtask budgets and terminal states

**Topics**

- Subtask contract and role capabilities
- Shared and isolated context
- Evidence packets and source metadata
- Merging results and resolving conflicts
- Global, subtask, and time budgets
- Cancellation propagation and collaborative termination

**Experiments**

Study-assistant collaboration with evidence:

1. Have a coordinator assign looking up documents, generating exercises, and independent review, giving each role explicit inputs, outputs, sources, and a budget.
2. Run it for real and save the handoff packets, add a piece of conflicting evidence or an overlong text, and check whether summarizing and merging lose facts.
3. Set one subtask to time out, and check the cancellation, budget deduction, the note on unfinished work, and the final result.

Deliverable: Delegation contracts, evidence handoff packets, and a table checking budgets and terminal states.

**Acceptance**

- Each subtask has its own identity and a finite budget, and the whole run can't grow without bound through recursive delegation.
- The final conclusion cites real subtask evidence, and conflicts and truncation are shown explicitly rather than hidden by a summary.
- Timeouts, cancellations, and unfinished subtasks affect the final acceptance, and all subtasks returning is not treated as business success.

**References**

- [深入理解 AI Agent：设计原理与工程实践](https://github.com/bojieli/ai-agent-book): `book/chapter10.md`.

### H2 · Long-running tasks

The boundaries of background execution, scheduled triggers, and goal loops.

#### Lesson 49 · Background and scheduled tasks

**Lesson ID:** `long-running-tasks`

**Level:** Core · **Status:** Planned · **Difficulty:** Challenge · **Time:** about 60 min · **Model:** calls a real model

**Prerequisites:** Lesson 48 Delegation, context merging, and budgets

Run slow tasks in the background, inject their results in later rounds, and repeat execution with scheduled triggers.

**Sections**

1. **Which tasks belong in the background**: A slow task shouldn't block the conversation. Its result comes back later.
2. **When to inject the result**: A background result is injected into the next request, with its source and time marked.
3. **Scheduled triggers**: Repeat execution on a schedule, and give each run its own record.
4. **Cancellation and terminal state of background tasks**: A background task must be stoppable too, and its terminal state must be findable.

**Objectives**

- Manage a background task's start, end, and exit code
- Inject background results at the right round
- Constrain long loops with goal evaluation

**Topics**

- Background tasks
- When to inject results
- Scheduled triggers
- Cancellation and terminal state of background tasks
- Labeling the source of injected results

**Experiments**

A background task and a goal loop:

1. Start a slow background fixture task, and record its start and end, exit code, and the round it was injected.
2. Use goal evaluation each round to judge ok, impossible, or keep going.
3. Set a budget limit and observe what happens when it is reached.

Deliverable: A background lane timeline and the goal evaluation record.

**Acceptance**

- The model did not see the background result before the round it was injected.
- The reasons for goal evaluation are recorded.
- When the budget is reached, the run stops explicitly.

**References**

- [深入理解 AI Agent：设计原理与工程实践](https://github.com/bojieli/ai-agent-book): `book/chapter6.md`.

#### Lesson 50 · Goal loops and give-up conditions

**Lesson ID:** `goal-loops`

**Level:** Core · **Status:** Planned · **Difficulty:** Challenge · **Time:** about 60 min · **Model:** calls a real model

**Prerequisites:** Lesson 49 Background and scheduled tasks

Use an independent goal evaluation to decide whether to continue, finish, or give up, set a budget and give-up conditions for the loop, and record the evidence behind each round's evaluation.

**Sections**

1. **A goal has to be checkable**: Write the goal as a condition the program can judge, not "until it's good".
2. **Independent goal evaluation**: The executor saying it's done doesn't count. The evaluator decides by the conditions whether to continue, finish, or give up.
3. **Budget and give-up conditions**: Rounds, time, and cost all have limits, and when they are reached the loop gives up honestly.
4. **Round-by-round records**: Keep the basis of every round's evaluation, so a replay shows why it continued or stopped.

**Objectives**

- Implement goal evaluation independent of the executor
- Set a budget and give-up conditions
- Record the basis for continuing or stopping in each round

**Topics**

- Goal evaluation
- Continue, finish, and give up
- Budget and timeout
- Give-up conditions
- Evaluation records

**Experiments**

A bounded goal loop:

1. Define a checkable goal and give-up conditions.
2. Run the goal loop and record each round's evaluation.
3. Construct a goal that can't be reached, and confirm the loop gives up according to the conditions.

Deliverable: Round-by-round evaluation records of the goal loop.

**Acceptance**

- Every round's decision to continue or stop has an evaluation basis.
- When the budget is reached, the run stops and reports honestly.
- The executor's "done" does not replace the evaluation's conclusion.

**References**

- [深入理解 AI Agent：设计原理与工程实践](https://github.com/bojieli/ai-agent-book): `book/chapter2.md`.

### H3 · Local delivery and the capstone project

Produce a complete application that can start, resume, and be evaluated.

#### Lesson 51 · Local delivery: startup, configuration, and credentials

**Lesson ID:** `local-delivery`

**Level:** Core · **Status:** Planned · **Difficulty:** Challenge · **Time:** about 60 min · **Model:** no model calls

**Prerequisites:** Lesson 37 Human-in-the-loop, checkpoints, and recovery, Lesson 41 Observability, usage, and cost, Lesson 42 Reliable tools, retries, and idempotency, Lesson 44 MCP basics and tool integration

Turn the learning tool into a local app that can be started, configured, and observed, and verify that the real service works.

**Sections**

1. **From running to deliverable**: The minimum for delivery is that another machine can start it by following the instructions.
2. **Pinned dependencies and configuration**: Pin dependency versions, keep configuration apart from secrets, and keep secrets only on the backend.
3. **Start, stop, and probes**: Provide a startup script and a health check to confirm the service really works.
4. **Logs and sensitive data**: Error logs must help locate a problem, but must not contain secrets or personal data.

**Objectives**

- Separate configuration, credentials, and runtime data
- Build availability checks for the real model and tools
- Verify restart recovery, log diagnosis, and upgrade rollback

**Topics**

- Runtime environment and pinned dependencies
- Provider configuration and credential management
- Start, stop, and service probes
- Error logs and handling sensitive data

**Experiments**

Starting from an empty environment and recovering from interruption:

1. Install and start in a separate local environment following the delivery instructions, pick a verified model configuration, and make sure no credentials end up in source code or the trace.
2. Check service availability with a real model request and MCP discovery and calls, then shut down and restart at a paused task.
3. Check the recovered content, the actual side effects, the diagnostic logs, and the data backup, and try one configuration upgrade that can be rolled back.

Deliverable: Local startup instructions, a real availability report, and recovery and rollback records.

**Acceptance**

- Following the instructions, the app starts from a clean environment, and the model and the tools each pass a real probe.
- After a restart, state and documents are restored as agreed, completed writes aren't repeated, and unknown providers are not marked as verified.
- Configuration errors can be located from the UI or the logs, credentials don't leak, and backup and rollback have actual check records.

**References**

- [深入理解 AI Agent：设计原理与工程实践](https://github.com/bojieli/ai-agent-book): `chapter4/DOCKER_DEPLOYMENT.md`.
- [深入理解 AI Agent：设计原理与工程实践](https://github.com/bojieli/ai-agent-book): `book/chapter7.md`.
- [Microsoft AI Agents for Beginners](https://github.com/microsoft/ai-agents-for-beginners): `STUDY_GUIDE.md`.

#### Lesson 52 · Backup, recovery, and upgrade rollback

**Lesson ID:** `backup-upgrade`

**Level:** Core · **Status:** Planned · **Difficulty:** Challenge · **Time:** about 60 min · **Model:** no model calls

**Prerequisites:** Lesson 51 Local delivery: startup, configuration, and credentials

Back up run records and memory data, verify they work after recovery, and roll back to the previous version when an upgrade fails.

**Sections**

1. **What to back up**: How and how often to back up run records, the memory store, and configuration templates.
2. **Recovery must be verified**: After restoring into a new directory, run the acceptance checks to confirm the data really works.
3. **Upgrade and data migration**: When a new version changes the data format, the migration must be repeatable and checkable.
4. **Rollback**: When an upgrade fails, go back to the previous version and keep the data consistent.

**Objectives**

- Decide the scope and frequency of backups
- Verify that data is usable after recovery
- Rehearse rollback after a failed upgrade

**Topics**

- Backup scope
- Recovery verification
- Data migration
- Upgrade and rollback
- Data consistency after rollback

**Experiments**

A backup, recovery, and rollback drill:

1. Back up the run store and the memory store.
2. Restore into a new directory and run the acceptance checks.
3. Simulate a failed upgrade and roll back.

Deliverable: A backup inventory, recovery acceptance, and a rollback record.

**Acceptance**

- After recovery, run records are readable and memory can be recalled.
- After rollback, the data matches what it was before.
- Backup files contain no secrets.

**References**

- [深入理解 AI Agent：设计原理与工程实践](https://github.com/bojieli/ai-agent-book): `book/chapter2.md`.

#### Lesson 53 · Capstone: a local coding or study assistant

**Lesson ID:** `capstone-study-assistant`

**Level:** Core · **Status:** Planned · **Difficulty:** Challenge · **Time:** about 180 min · **Model:** calls a real model

**Prerequisites:** Lesson 15 Persistent memory: save, reopen, and recall, Lesson 29 RAG answers and citations, Lesson 32 LangChain tools and structured adapters, Lesson 37 Human-in-the-loop, checkpoints, and recovery, Lesson 40 Independent evaluation sets and validators, Lesson 41 Observability, usage, and cost, Lesson 43 Prompt injection and tool permissions, Lesson 44 MCP basics and tool integration, Lesson 51 Local delivery: startup, configuration, and credentials

Integrate the course materials, task contract, learning progress, tools, and state graph into a study assistant that works from a real model and evidence.

**Sections**

1. **Pick a topic and a task contract**: Choose one route, coding assistant or study assistant, and write the task card and acceptance criteria first.
2. **Combine what you've learned**: Use tools, memory, retrieval, planning, and approval as needed, and explain each trade-off.
3. **Evaluation and replay**: Score with a fixed question set and a hidden one, and submit a replay of a real run as evidence.
4. **Delivery notes**: The README states installation, configuration, running, evaluation results, known limitations, and next steps.
5. **Self-check before submitting**: Go through the checklist: no secrets in the repo, tests pass, the replay is readable, limitations are written down.
6. **Scoring rubric**: Score by feature completeness, evidence sufficiency, reliability, code readability, and quality of the instructions.

**Objectives**

- Integrate what you've learned into an application with a clear scope
- Accept real learning tasks with a predefined question set
- Deliver results that run, can be diagnosed, and can recover

**Topics**

- Project scope and task contract
- Document citations and exercise generation
- Learning progress and controllable memory
- Framework and tool service integration
- Stage state, human confirmation, and recovery
- Full regression, delivery, and limitations

**Experiments**

A study assistant based on source code and traces:

1. First define the supported courses, document scope, exercise outputs, and failure rules, and freeze the acceptance set and the held-out tasks.
2. Reuse the existing model adapter, retrieval, memory, state graph, and MCP tools to actually look up material, explain a trace, generate exercises, and save progress.
3. Run every normal, no-answer, injection, tool-failure, and restart-recovery case and deliver the report. Add multiple agents only if the comparison shows they help.

Deliverable: A complete local app, a reproducible acceptance report, usage instructions, and known limitations.

**Acceptance**

- Answers and exercises cite real documents or run evidence, and unknown facts and missing data are stated explicitly.
- The fixed set and the held-out tasks have complete results, and failure, permission, and recovery criteria are all checked.
- The app can be installed, started, and recovered by following the instructions, planned courses are kept apart from implemented capabilities, and the limitations can be rechecked with concrete cases.

**References**

- [Microsoft AI Agents for Beginners](https://github.com/microsoft/ai-agents-for-beginners): `STUDY_GUIDE.md`.
- [Hugging Face Agents Course](https://github.com/huggingface/agents-course): `units/en/unit4/hands-on.mdx`.
- [深入理解 AI Agent：设计原理与工程实践](https://github.com/bojieli/ai-agent-book): `book/chapter7.md`.

## Electives

Electives have no main-line lesson number; add them as your interests and projects need.

### X1 · smolagents: code actions and tool calling

Take this after finishing the tool boundaries, framework comparison, and permissions lessons. Use one task to compare generated code with JSON tool calls. Executing generated code needs isolation and a budget designed separately.

Prerequisites: Lesson 31, Lesson 42, Lesson 43

- How CodeAgent and ToolCallingAgent represent actions
- Comparison on the same task and validator
- Execution isolation for generated code
- Tool results and evidence from running code

### X2 · LlamaIndex: retrieval components and workflows

Take this after finishing RAG answers with citations. Keep the corpus, query set, and citation criteria fixed, and compare components and index organization, rather than starting a separate case that can't be compared.

Prerequisites: Lesson 28, Lesson 29

- Documents, nodes, and metadata
- Loading, indexing, storing, querying, evaluating
- QueryEngine as an agent tool
- Paired comparison of retrieval and generation quality

### X3 · Microsoft Agent Framework and Foundry

Take this as needed after understanding the native loop and the LangChain adapter. Use a separate environment and account configuration, and compare the session, tool, and orchestration abstractions. Cloud deployment carries its own cost and permissions.

Prerequisites: Lesson 31, Lesson 32, Lesson 41

- Model providers and client adaptation
- Session and tool abstractions
- Workflows and server-side responsibilities
- Foundry integration and an observability comparison

### X4 · Browser and multimodal agents

Take this after finishing the human-in-the-loop, independent evaluation, and permissions lessons. Start with a fixed web page or image task, define the actions and evidence, and add cases for misrecognition, page changes, and confirmation.

Prerequisites: Lesson 37, Lesson 40, Lesson 43

- Image and interface evidence
- Browser actions and run feedback
- Human confirmation and execution scope
- Misrecognition, page changes, and repeatable evaluation

### X5 · Local models and offline runs

Take this after mastering the model request, RAG, and usage lessons, depending on your machine. Check the hardware, the model license, and the capabilities for real, then compare Bailian with a local model on the same question set.

Prerequisites: Lesson 28, Lesson 31, Lesson 41

- Local compatible interfaces and model loading
- Hardware, quantization, and latency
- Measuring tool-calling ability
- Offline material and swapping the model provider

### X6 · Fine-tuning for tool calling and reinforcement learning

Take this after finishing independent evaluation and the capstone project, and after filling in the machine learning, data, and training basics. First show that the errors come from the model's capability, and compare against improvements to the prompt, tool design, or retrieval.

Prerequisites: Lesson 40, Lesson 43, Lesson 53

- Training data and held-out evaluation
- Supervised fine-tuning for function calling
- Task rewards and reinforcement learning basics
- Training cost, capability regression, and version rollback

## What each reference contributes

### [Microsoft AI Agents for Beginners](https://github.com/microsoft/ai-agents-for-beginners)

What we borrow: Borrows the learning goals, the topic modules, the continuing study-assistant project, and the practice of accepting each stage by the capability it adds.

How we adapt it: Mainly draws on the downloaded STUDY_GUIDE and the tool, RAG, and memory material. Azure, Foundry, and Microsoft Agent Framework accounts and dependencies are not made foundational prerequisites. Bailian is the configuration tested so far, and other providers are verified separately. Content in the sparse checkout that was not downloaded cannot be counted as read or reproduced.

Reference snapshot: `25b7985f3b2dc37a84f4a7387ccd3c9f0e5b1595`.

### [Hugging Face Agents Course](https://github.com/huggingface/agents-course)

What we borrow: Borrows the layered structure from basics to frameworks, scenario practice, and evaluation; the optional framework branches; and the split of State/Node/Edge and the RAG pipeline.

How we adapt it: Uses local Chinese course material and the unified model interface, with Bailian as the configuration tested so far. Starts from keyword retrieval, then compares vector and hybrid retrieval. Public leaderboards, certificates, HF Spaces, and specific model providers are not graduation requirements. Framework APIs are checked again when the lessons are actually built.

Reference snapshot: `b3946b1d09d29c65736e219d48a8a736a2c52154`.

### [深入理解 AI Agent：设计原理与工程实践](https://github.com/bojieli/ai-agent-book)

What we borrow: Fills in task acceptance, context experiments, tool contracts, independent validators, the run lifecycle, cost, and the engineering trade-offs of multi-agent systems.

How we adapt it: Draws on the text and concrete implementations of a pinned snapshot, while the exercises are written from scratch for this platform. It does not claim that all the companion experiments have been reproduced. Unknown usage is not counted as zero cost, deployment needs real protocol probing, and training and external environments are optional electives placed later.

Reference snapshot: `b789c97a8f3de5b405a6f6dfa8289208d679d0b8`.

## Next

Check the catalog and the plan first, then implement lessons in learning order. The next lesson is Lesson 25, Document loading and chunking. Library versions and framework APIs of planned lessons are checked again when each lesson is built.
