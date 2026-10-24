"""Text of the offline test model of long-running-tasks (English)."""
from lessons.lesson_long_running_tasks.locales.fixture import Texts

TEXTS = Texts(
    waiting="The jobs are running in the background; I will wait for the results.",
    still_waiting="One result is in and the other job is still running; I will keep waiting.",
    gave_up="Row 6 of the late-score sheet is not an integer and the retry failed the same way. I cannot submit a complete report until the data is fixed.",
    restarted="I started deep_scan again and will wait for its result.",
)
