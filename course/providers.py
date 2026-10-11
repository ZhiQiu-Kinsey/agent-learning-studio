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
        prefixes = {
            "openai": "openai", "anthropic": "anthropic", "gemini": "gemini",
            "deepseek": "deepseek", "openrouter": "openrouter",
            "ollama": "ollama_chat", "custom": "openai",
        }
        # model is the provider's own id as the user typed it; the prefix only picks the SDK adapter.
        kwargs = {
            **body,
            "model": prefixes[profile.id] + "/" + body["model"],
            # Pass the selected profile's key explicitly; never borrow another provider's environment variable.
            "api_key": api_key if profile.requires_key else (api_key or "ollama-local"),
            "timeout": 60,
            "num_retries": 0,
            "max_retries": 0,
            "drop_params": False,
        }
        if profile.api_base:
            kwargs["api_base"] = profile.api_base
        response = sdk_completion(**kwargs)
        return response if isinstance(response, dict) else response.model_dump(exclude_none=True)
