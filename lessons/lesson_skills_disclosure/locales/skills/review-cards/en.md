---
name: review-cards
description: Use when the user gives the original text of study notes and asks to turn them into review cards (Q&A cards, flashcards). The input is the original notes; the output is 3–5 "Q:/A:" cards. Do not use without original notes, for example for study advice, answering questions or writing summaries.
---
# Turn study notes into review cards

## When to use

- The user pasted the original notes and wants review cards, Q&A cards or flashcards.
- A request with only a question and no original notes does not use this skill.

## Procedure

1. Read the notes and pick 3–5 points worth remembering: prefer one each of a definition, a comparison, a cause and effect, and a common mistake.
2. Write each point as one card: the question asks about one thing only, and the answer keeps the wording of the notes, in one or two sentences.
3. A question must make sense on its own: do not write "What is it?"; name the subject.
4. Do not add anything the notes do not say; where the notes are wrong, copy them as they are and add "(as written in the notes; please check)" after the answer.

## Output format

Two lines per card, one blank line between cards; no title, no opening or closing remarks.

Q: ...
A: ...

Q: ...
A: ...

## Check before delivering

- There are 3 to 5 cards.
- Every "Q:" is directly followed by an "A:".
- No fact appears that is not in the notes.
