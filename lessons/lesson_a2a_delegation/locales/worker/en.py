"""a2a-delegation remote agent text: English."""
from lessons.lesson_a2a_delegation.locales.worker import Texts

TEXTS = Texts(
    agent_description=("Reference checker of the Bluestone Library: finds handbook passages that bear on each claim "
                       "and marks old versions that a newer one has replaced. It does not judge whether a claim is true."),
    skill_name="Find handbook evidence",
    skill_description=("Takes 1 to 3 claims (data part claims, each with id and text) and returns up to 3 handbook "
                       "passages per claim; an old version is swapped for the current one and noted in superseded."),
    skill_examples=("How many items can a B2 research card borrow", "What time does the library close on Sunday"),
    status_received="Received {count} claims; searching {chunks} handbook chunks.",
    status_waiting_index="The archive index is being rebuilt; waited {seconds} s so far.",
    status_checked="{claim_id} checked: {evidence} evidence passages found.",
    status_done="Check finished.",
    status_failed="The archive index is damaged; no claim could be checked this time.",
    status_rejected=("The message has no valid claims: send 1 to 3 claims with id and text, "
                     "and name the skill in metadata.skill_id."),
    status_canceled="Canceled at the delegating agent's request.",
    artifact_summary="Handbook evidence for {count} claims; superseded old versions are noted.",
    superseded_note="{old} has been replaced by {new}; the current version applies.",
)
