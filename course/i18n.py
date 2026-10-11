"""Runtime locales: the language a run speaks, and typed message catalogs.

Every run has one locale, fixed when it starts (server/app.py records it in the
``run_start`` event). Code that sends text to the model or into events reads that
text from a catalog for the run's locale instead of hardcoding it:

    <package>/locales/__init__.py   Texts: a frozen dataclass, one field per message
    <package>/locales/zh_CN.py      TEXTS = Texts(...)   # source language
    <package>/locales/en.py         TEXTS = Texts(...)

Catalogs are plain Python data on purpose. Prompts are long and structured, and a
learner must be able to read them verbatim: the catalog file shown in the Code
scene is exactly the text that runs. (gettext-style message ids would hide the
real prompt behind a key, and a Chinese reader would read an English msgid.)
"""
from __future__ import annotations

import dataclasses
import re
import string
import sys
from importlib import import_module
from pathlib import Path
from typing import Any, Callable, Iterator, TypeVar

SOURCE_LOCALE = "zh-CN"
# Every locale a run can use. A lesson declares the subset it supports in
# lesson.json (runtime.locales); the source locale is always part of it.
RUNTIME_LOCALES = ("zh-CN", "en")

T = TypeVar("T")


def module_name(locale: str) -> str:
    """Catalog module for a locale: "zh-CN" -> "zh_CN", "en" -> "en"."""
    return locale.replace("-", "_")


def resolve_locale(requested: str | None, supported=(SOURCE_LOCALE,)) -> str:
    """Pick the run locale from what the UI asked for and what the lesson supports.

    The rule, in order:
    1. an exact match ("en" -> "en");
    2. the same language ("en-US" -> "en", "zh" or "zh-TW" -> "zh-CN");
    3. otherwise the source locale. Nothing requested also means the source locale.
    """
    if SOURCE_LOCALE not in supported:
        raise ValueError(f"supported locales must include the source locale {SOURCE_LOCALE}")
    if not requested:
        return SOURCE_LOCALE
    if requested in supported:
        return requested
    language = requested.split("-", 1)[0].lower()
    return next((locale for locale in supported if locale.split("-", 1)[0].lower() == language), SOURCE_LOCALE)


def catalog(package: str, texts_type: type[T]) -> Callable[[str], T]:
    """Build ``texts_for(locale)`` for the catalog package ``package`` (a ``locales`` package).

    ``texts_for`` imports ``<package>.<module_name(locale)>`` once and returns its
    ``TEXTS``. A runtime locale without a catalog module falls back to the source
    locale's catalog, so a lesson that only speaks Chinese keeps working when it is
    asked for English. A string that is not a runtime locale is a programming error.
    """
    cache: dict[str, T] = {}

    def texts_for(locale: str = SOURCE_LOCALE) -> T:
        if locale not in RUNTIME_LOCALES:
            raise ValueError(f"not a runtime locale: {locale!r}")
        if locale not in cache:
            try:
                module = import_module(f"{package}.{module_name(locale)}")
            except ModuleNotFoundError as error:
                if locale == SOURCE_LOCALE or error.name != f"{package}.{module_name(locale)}":
                    raise
                cache[locale] = texts_for(SOURCE_LOCALE)
                return cache[locale]
            texts = getattr(module, "TEXTS", None)
            if not isinstance(texts, texts_type):
                raise TypeError(f"{module.__name__}.TEXTS must be a {texts_type.__name__}")
            cache[locale] = texts
        return cache[locale]

    texts_for.package = package  # type: ignore[attr-defined]
    texts_for.texts_type = texts_type  # type: ignore[attr-defined]
    return texts_for


def available_locales(package: str) -> list[str]:
    """Runtime locales that have a catalog module in ``package`` (the source locale first)."""
    found = []
    for locale in RUNTIME_LOCALES:
        try:
            import_module(f"{package}.{module_name(locale)}")
        except ModuleNotFoundError as error:
            if error.name != f"{package}.{module_name(locale)}":
                raise
            continue
        found.append(locale)
    return found


def localized_file(directory, locale: str, suffix: str) -> Path:
    """A per-language data file such as ``locales/handbook/en.md``; the source locale's file when this one is missing."""
    path = Path(directory) / f"{module_name(locale)}{suffix}"
    return path if path.is_file() else Path(directory) / f"{module_name(SOURCE_LOCALE)}{suffix}"


def placeholders(template: str) -> set[str]:
    """Named ``str.format`` fields in a template: "Round {round} of {limit}" -> {"round", "limit"}."""
    return {field.split(".", 1)[0].split("[", 1)[0]
            for _, field, _, _ in string.Formatter().parse(template) if field is not None}


def leaves(value: Any, path: str = "") -> Iterator[tuple[str, Any]]:
    """Every leaf of a catalog value with its path; mappings by key, sequences by index."""
    if dataclasses.is_dataclass(value) and not isinstance(value, type):
        for item in dataclasses.fields(value):
            yield from leaves(getattr(value, item.name), item.name)
    elif isinstance(value, dict):
        for key, item in value.items():
            yield from leaves(item, f"{path}.{key}")
    elif isinstance(value, (list, tuple)):
        for index, item in enumerate(value):
            yield from leaves(item, f"{path}[{index}]")
    else:
        yield path, value


def parity_problems(reference: Any, other: Any) -> list[str]:
    """Differences between two catalogs of one Texts type: shape, leaf types and placeholders.

    Used by tests/test_runtime_locales.py. The dataclass already forces both catalogs
    to fill every field; this also catches a missing key, an extra list item or a
    template whose ``{fields}`` differ, which would break ``str.format`` at run time.
    """
    expected, actual = dict(leaves(reference)), dict(leaves(other))
    problems = [f"{path}: missing" for path in expected if path not in actual]
    problems += [f"{path}: unexpected" for path in actual if path not in expected]
    for path in expected.keys() & actual.keys():
        left, right = expected[path], actual[path]
        if type(left) is not type(right):
            problems.append(f"{path}: {type(left).__name__} vs {type(right).__name__}")
        elif isinstance(left, str):
            if not right.strip():
                problems.append(f"{path}: empty")
            elif placeholders(left) != placeholders(right):
                problems.append(f"{path}: placeholders {sorted(placeholders(left))} vs {sorted(placeholders(right))}")
        elif left != right and not isinstance(left, (int, float)):
            problems.append(f"{path}: {left!r} vs {right!r}")
    return sorted(problems)


_LOCALE_FLAG = re.compile(r"--locale(?:=(?P<value>\S+))?\Z")


def cli_locale(argv: list[str] | None = None) -> str:
    """Locale for a command-line run: ``--locale en`` (or ``--locale=en``); default is the source locale."""
    args = sys.argv[1:] if argv is None else argv
    for index, arg in enumerate(args):
        match = _LOCALE_FLAG.match(arg)
        if match:
            value = match.group("value") or (args[index + 1] if index + 1 < len(args) else "")
            if value not in RUNTIME_LOCALES:
                raise SystemExit(f"--locale must be one of: {', '.join(RUNTIME_LOCALES)}")
            return value
    return SOURCE_LOCALE
