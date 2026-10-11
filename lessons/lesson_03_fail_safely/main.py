"""When a tool fails, say so truthfully instead of guessing a result."""

from course.i18n import cli_locale
from course.runner import AgentSetup, run_cli
from lessons.lesson_03_fail_safely.locales import texts_for
from lessons.lesson_03_fail_safely.tools import available_tools, tool_definitions


def setup(locale):
    """What the native loop sends in one run: the system prompt and tools in the run's language, plus the allowlist."""
    return AgentSetup(
        system_prompt=texts_for(locale).system_prompt,
        tools=tool_definitions(locale),
        available_tools=available_tools(locale),
    )


def main(locale=None):
    locale = locale or cli_locale()
    t = texts_for(locale)
    run_cli(setup(locale), title=t.cli_title, examples=t.cli_examples, max_tool_rounds=2, locale=locale)


if __name__ == "__main__":
    main()
