"""Send Bailian chat-completion and embeddings requests over raw HTTP; the key goes into the header, never the body."""

import json
import urllib.error
import urllib.request

from course.i18n import SOURCE_LOCALE
from course.locales import texts_for


class ProviderHTTPError(RuntimeError):
    """The provider answered with an HTTP error; the status code is kept so lessons can record it honestly."""

    def __init__(self, message, status_code):
        super().__init__(message)
        self.status_code = status_code


def send_bailian(request_body, api_key, timeout_seconds=60, *, locale=SOURCE_LOCALE):
    """Send a request body that has already been recorded; web runs and the CLI share this transport."""
    from local_config import API_URL

    request = urllib.request.Request(
        API_URL,
        data=json.dumps(request_body).encode("utf-8"),
        headers={
            "Authorization": "Bearer " + api_key,
            "Content-Type": "application/json",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as error:
        detail = error.read().decode("utf-8", errors="replace")[:2000]
        # Never resend automatically: a retry could be billed twice.
        raise ProviderHTTPError(
            texts_for(locale).bailian_http_error.format(status=error.code, detail=detail),
            error.code,
        ) from None
    except urllib.error.URLError as error:
        raise RuntimeError(
            texts_for(locale).bailian_unreachable.format(reason=error.reason)
        ) from None


# ---------- Embedding requests ----------
# Bailian's OpenAI-compatible embeddings endpoint, checked against the Model Studio embedding
# guide (2026-10): text-embedding-v4 takes at most 10 input rows per request.
BAILIAN_EMBEDDING_MODEL = "text-embedding-v4"
BAILIAN_EMBEDDING_BATCH_LIMIT = 10
_CHAT_SUFFIX = "/chat/completions"


def bailian_embeddings_url():
    """The embeddings URL of the local Bailian configuration, or None when it cannot be known.

    local_config.EMBEDDING_API_URL wins when set. Otherwise the standard OpenAI-compatible
    chat URL (API_URL) is rewritten from /chat/completions to /embeddings in the same
    workspace; any other shape is not guessed at.
    """
    import local_config

    explicit = getattr(local_config, "EMBEDDING_API_URL", None)
    if explicit:
        return explicit if isinstance(explicit, str) and explicit.startswith("https://") else None
    chat = getattr(local_config, "API_URL", None)
    if isinstance(chat, str) and chat.startswith("https://") and chat.rstrip("/").endswith(_CHAT_SUFFIX):
        return chat.rstrip("/")[:-len(_CHAT_SUFFIX)] + "/embeddings"
    return None


def bailian_embedding_model():
    """local_config.EMBEDDING_MODEL when set, otherwise Bailian's general text embedding model."""
    import local_config

    value = getattr(local_config, "EMBEDDING_MODEL", BAILIAN_EMBEDDING_MODEL)
    return value.strip() if isinstance(value, str) else ""


def send_bailian_embeddings(request_body, api_key, timeout_seconds=60, *, locale=SOURCE_LOCALE):
    """Send an embeddings request body that has already been recorded, to the chat model's workspace.

    The transport mirrors send_bailian (kept inline there because the chat lesson reads it):
    key in the header, the recorded body unchanged, no automatic resend.
    """
    url = bailian_embeddings_url()
    if url is None:
        raise ValueError(texts_for(locale).embedding_not_configured)
    request = urllib.request.Request(
        url,
        data=json.dumps(request_body).encode("utf-8"),
        headers={"Authorization": "Bearer " + api_key, "Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as error:
        detail = error.read().decode("utf-8", errors="replace")[:2000]
        raise ProviderHTTPError(
            texts_for(locale).bailian_http_error.format(status=error.code, detail=detail),
            error.code,
        ) from None
    except urllib.error.URLError as error:
        raise RuntimeError(texts_for(locale).bailian_unreachable.format(reason=error.reason)) from None
