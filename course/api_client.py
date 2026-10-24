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


# ---------- Streaming chat requests ----------
# Bailian's OpenAI-compatible endpoint streams with "stream": true (checked against the Model
# Studio streaming guide, 2026-10): Server-Sent Events whose data lines each carry one
# chat.completion.chunk JSON object, then a final "data: [DONE]". With
# stream_options.include_usage the last chunk has empty choices and the usage.


class BailianStream:
    """Iterate the JSON chunks of one streamed Bailian response; the request body was recorded before.

    Opening sends the request (same transport rules as send_bailian: key in the header, no
    automatic resend). Iterating yields each SSE data payload parsed as JSON, in arrival order.
    ``done_marker`` turns True when the provider's closing "[DONE]" line arrived, so a stream that
    simply stopped can be told apart from one the provider finished. Only the thread that
    iterates may call close(); RunContext.complete_stream keeps to that.
    """

    def __init__(self, request_body, api_key, timeout_seconds=60, *, locale=SOURCE_LOCALE):
        from local_config import API_URL

        self.locale = locale
        self.done_marker = False
        request = urllib.request.Request(
            API_URL,
            data=json.dumps(request_body).encode("utf-8"),
            headers={"Authorization": "Bearer " + api_key, "Content-Type": "application/json",
                     "Accept": "text/event-stream"},
            method="POST",
        )
        try:
            self._response = urllib.request.urlopen(request, timeout=timeout_seconds)
        except urllib.error.HTTPError as error:
            detail = error.read().decode("utf-8", errors="replace")[:2000]
            raise ProviderHTTPError(
                texts_for(locale).bailian_http_error.format(status=error.code, detail=detail), error.code,
            ) from None
        except urllib.error.URLError as error:
            raise RuntimeError(texts_for(locale).bailian_unreachable.format(reason=error.reason)) from None

    def __iter__(self):
        data_lines = []
        try:
            for raw in self._response:
                line = raw.decode("utf-8").rstrip("\r\n")
                if line:
                    # SSE fields: only data lines carry the payload; comments (":") and other
                    # fields are framing.
                    if line.startswith("data:"):
                        data_lines.append(line[5:].removeprefix(" "))
                    continue
                if not data_lines:
                    continue
                payload, data_lines = "\n".join(data_lines), []
                if payload.strip() == "[DONE]":
                    self.done_marker = True
                    return
                yield json.loads(payload)
            if data_lines and "\n".join(data_lines).strip() != "[DONE]":
                yield json.loads("\n".join(data_lines))
        except (OSError, ValueError) as error:
            # A broken connection or a payload that is not JSON: the caller keeps what arrived.
            raise RuntimeError(texts_for(self.locale).stream_interrupted.format(reason=error)) from None
        finally:
            self.close()

    def close(self):
        self._response.close()


def stream_bailian(request_body, api_key, timeout_seconds=60, *, locale=SOURCE_LOCALE):
    """Open one streamed chat request; RunContext.complete_stream iterates and records the chunks."""
    return BailianStream(request_body, api_key, timeout_seconds, locale=locale)
