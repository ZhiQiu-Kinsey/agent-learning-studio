---
name: unit-test-checklist
description: Use when the user gives the code of a function and wants unit tests designed or test cases listed for it. The output has at least 5 check items starting with "- [ ]", covering normal input, edge cases and invalid input.
---
# A checklist for writing unit tests for code

## When to use

- The user gave the code of a function or class and asks "what should I test" or "list test cases for me".
- When the user wants test code that runs as is, give the checklist first, then ask whether they need the code.

## Procedure

1. First state in one sentence what the function is responsible for, its input and its output.
2. Find cases in the order below, at least one per category:
   - normal input: the most common use;
   - edge cases: empty values, 0, maximum and minimum values, a single element;
   - invalid input: wrong type, missing argument, malformed format; state which error should be raised or what should be returned;
   - side effects: whether it changes the arguments passed in, files or global state.
3. For each case, write the input and the expected result; the expected result must be expressible as one assertion.
4. When you are unsure of the expected result, leave it to the user as a question instead of deciding for them.

## Output format

The first line states the responsibility, then one case per line:

- [ ] Input ..., expect ...

## Check before delivering

- At least 5 check items, each starting with "- [ ]".
- Normal input, edge cases and invalid input are all covered.
