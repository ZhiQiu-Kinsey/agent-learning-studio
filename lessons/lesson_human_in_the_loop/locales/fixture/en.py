"""human-in-the-loop offline test model text: English."""
from lessons.lesson_human_in_the_loop.locales.fixture import Texts

TEXTS = Texts(
    draft="Exercise: {topic}\n\nWrite a function that takes a list of numbers and returns the even ones; an empty list gives an empty list. Then write two tests, one normal and one empty.",
    receipt="The exercise \"{title}\" ended as {status}, and the bank has {rows} row(s) for this operation.",
    edit_title_suffix=" (edited)",
    edit_note="Difficulty raised to challenge and the title marked",
)
