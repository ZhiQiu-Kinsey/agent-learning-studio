"""a2a-delegation offline test model text: English."""
from lessons.lesson_a2a_delegation.locales.fixture import Texts

TEXTS = Texts(
    claims=("How many items can a B2 research card borrow", "What time does the library close on Sunday"),
    answer="The reference checker returned evidence; check the passages themselves: {lines}",
    claim_line="{claim_id} \"{claim}\" is covered by {chunks}",
    superseded=" (old version {chunks} is superseded and not used)",
    line_separator="; ",
    not_delegated="This could not be checked ({error_type}): {error} So I give no answer; please ask again later.",
)
