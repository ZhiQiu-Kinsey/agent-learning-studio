"""Reuse LiteLLM's provider adapters; lessons keep their own agent loop and tool execution."""
from dataclasses import dataclass
import os
import threading

from course.i18n import SOURCE_LOCALE
from course.locales import texts_for

_sdk = None
_sdk_lock = threading.Lock()


@dataclass(frozen=True)
class ModelProfile:
    id: str
    label: str
    model: str
    api_key: str
    api_base: str | None
    config_ready: bool
    requires_key: bool = True
    supports_custom_base_url: bool = True
    # Embedding model of this provider ("" when none is configured) and how many inputs one
    # embeddings request may carry. Lessons split their texts into batches of this size.
    embedding_model: str = ""
    embedding_batch_limit: int = 10

    @property
    def representation(self):
        return "http_body" if self.id == "bailian" else "sdk_standardized"


def load_sdk():
    """Before importing, use the bundled model cost map and skip .env; turn off telemetry and logging callbacks."""
    global _sdk
    with _sdk_lock:
        if _sdk is None:
            os.environ["LITELLM_LOCAL_MODEL_COST_MAP"] = "True"
            os.environ["LITELLM_MODE"] = "PRODUCTION"
            import litellm
            litellm.telemetry = False
            litellm.callbacks = []
            litellm.input_callback = []
            litellm.success_callback = []
            litellm.failure_callback = []
            _sdk = litellm
    return _sdk


def sdk_completion(**kwargs):
    """Load the SDK on demand; offline lessons and the default raw HTTP path never import it."""
    return load_sdk().completion(**kwargs)


def sdk_embedding(**kwargs):
    """Load the SDK on demand, like sdk_completion."""
    return load_sdk().embedding(**kwargs)


# The prefix only picks LiteLLM's adapter; the model id is the provider's own, as configured.
_CHAT_PREFIXES = {
    "openai": "openai", "anthropic": "anthropic", "gemini": "gemini",
    "deepseek": "deepseek", "openrouter": "openrouter",
    "ollama": "ollama_chat", "custom": "openai",
}
# LiteLLM serves Ollama embeddings through the "ollama" adapter, not the chat-only "ollama_chat".
_EMBEDDING_PREFIXES = {**_CHAT_PREFIXES, "ollama": "ollama"}


def _sdk_call_options(profile, api_key):
    """Options shared by chat and embedding calls: explicit key, no hidden retries, no dropped parameters."""
    options = {
        # Pass the selected profile's key explicitly; never borrow another provider's environment variable.
        "api_key": api_key if profile.requires_key else (api_key or "ollama-local"),
        "timeout": 60,
        "num_retries": 0,
        "max_retries": 0,
        "drop_params": False,
    }
    if profile.api_base:
        options["api_base"] = profile.api_base
    return options


class SDKCompletion:
    """Only calls the model and standardizes the response; it never runs tools or adds a hidden agent loop."""
    def __init__(self, profile, locale=SOURCE_LOCALE):
        self.profile = profile
        self.locale = locale

    def __call__(self, body, api_key):
        profile = self.profile
        if not profile.config_ready or not body.get("model"):
            raise ValueError(texts_for(self.locale).provider_not_configured)
        if profile.requires_key and not api_key:
            raise ValueError(texts_for(self.locale).provider_key_missing)
        # model is the provider's own id as the user typed it; the prefix only picks the SDK adapter.
        kwargs = {**body, "model": _CHAT_PREFIXES[profile.id] + "/" + body["model"],
                  **_sdk_call_options(profile, api_key)}
        response = sdk_completion(**kwargs)
        return response if isinstance(response, dict) else response.model_dump(exclude_none=True)

    def stream(self, body, api_key):
        """Open one streamed request (the body already says stream=True); yields each SDK chunk's model_dump().

        The chunks are LiteLLM's standardized chunk objects, not the provider's SSE lines, so the
        run keeps the sdk_standardized label. Only the iterating thread closes the stream.
        """
        profile = self.profile
        if not profile.config_ready or not body.get("model"):
            raise ValueError(texts_for(self.locale).provider_not_configured)
        if profile.requires_key and not api_key:
            raise ValueError(texts_for(self.locale).provider_key_missing)
        kwargs = {**body, "model": _CHAT_PREFIXES[profile.id] + "/" + body["model"],
                  **_sdk_call_options(profile, api_key)}
        return _SDKStream(sdk_completion(**kwargs))


class _SDKStream:
    """Iterate a LiteLLM stream as plain dicts; close() releases the SDK's connection when it can."""
    done_marker = None  # LiteLLM hides the provider's closing marker

    def __init__(self, stream):
        self._stream = stream

    def __iter__(self):
        try:
            for chunk in self._stream:
                yield chunk if isinstance(chunk, dict) else chunk.model_dump(exclude_none=True)
        finally:
            self.close()

    def close(self):
        for target in (self._stream, getattr(self._stream, "completion_stream", None)):
            close = getattr(target, "close", None)
            if callable(close):
                try:
                    close()
                except Exception:  # closing is best effort; the run's outcome is already decided
                    pass
                return


class SDKEmbedding:
    """Only sends one embeddings request and standardizes the response; it never splits or retries."""
    def __init__(self, profile, locale=SOURCE_LOCALE):
        self.profile = profile
        self.locale = locale

    def __call__(self, body, api_key):
        profile = self.profile
        if not profile.embedding_model or body.get("model") != profile.embedding_model:
            raise ValueError(texts_for(self.locale).embedding_not_configured)
        if profile.requires_key and not api_key:
            raise ValueError(texts_for(self.locale).provider_key_missing)
        kwargs = {**body, "model": _EMBEDDING_PREFIXES[profile.id] + "/" + body["model"],
                  **_sdk_call_options(profile, api_key)}
        if "dimensions" in body:
            # LiteLLM only forwards dimensions for model names it knows (text-embedding-3*) and
            # refuses others; the recorded body asks for it, so send it rather than drop it.
            kwargs["allowed_openai_params"] = ["dimensions"]
        response = sdk_embedding(**kwargs)
        return response if isinstance(response, dict) else response.model_dump(exclude_none=True)
