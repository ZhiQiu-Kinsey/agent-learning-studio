---
name: error-question
description: Use when the user pastes a program error and wants to turn it into a help request for a teacher or a forum. The output has five sections: symptom, original error, already tried, environment, my question. Do not use when the user only wants you to explain or fix the error directly.
---
# Turn an error into a help-request template

## When to use

- The user pasted an error (a traceback, an error code, console output) and wants to ask someone for help.
- When the user only wants you to explain or fix the error directly, do not use this skill.

## Procedure

1. Find two things in what the user said: what they meant to do, and what actually happened.
2. Keep the original error exactly as it is, in a code block, without cutting or translating it; if it is too long, keep the beginning and the last 10 lines.
3. List, one by one, the fixes the user mentioned having tried; if none were mentioned, write "(please add)".
4. For the environment, write the operating system, language version and versions of relevant libraries; write "(please add)" for what you do not know, and do not guess.
5. End with one sentence stating the concrete question; do not write questions like "why doesn't it work" that do not show where it is stuck.

## Output format

[Symptom] One or two sentences: what you meant to do, what actually happened.
[Original error] A code block.
[Already tried] A numbered list.
[Environment] Operating system / language version / relevant library versions.
[My question] One sentence.

## Check before delivering

- All five section titles are present, in this order.
- The original error is exactly what the user gave.
