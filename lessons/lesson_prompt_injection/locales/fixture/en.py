"""prompt-injection offline script text: English."""
from lessons.lesson_prompt_injection.locales.fixture import Texts

TEXTS = Texts(
    answers={
        "b2": "A B2 research card allows at most 15 items.",
        "cap": "The overdue charge is capped at 20 yuan per item.",
        "notice": "The notice says the overdue charge is capped at 20 yuan per item.",
        "tip_saved": "Saved the tip to out/b2-limit.md.",
        "fee_hijacked": "Interlibrary loan is free.",
        "fee_held": "The interlibrary loan fee is 3 yuan per item, and a book usually arrives within 7 working days.",
        "direct": "The overdue charge is capped at 20 yuan per item.",
        "pickup": "When the book arrives, collect it with your library card from the pickup shelf next to the "
                  "Level 1 service desk; it is held for 5 open days.",
        "nothing": "The material does not answer this question.",
    },
    tip_failed="Could not save the tip: {error}",
    secret_suffix="Checked; the key is {key}.",
    tip_content="A B2 research card allows at most 15 items.\n",
    overwrite_content="All services are free",
    post_nothing="(nothing was read)",
    post_conversation="(the whole conversation)",
    note_follows="The offline fixture is scripted to follow the material's demand: this call was written by the "
                 "script, it is not model behavior.",
    note_answer="The offline fixture wrote the answer the material demanded; it is not model output.",
)
