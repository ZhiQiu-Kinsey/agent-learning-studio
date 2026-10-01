"""复用 LiteLLM 厂商适配；课程保留自己的 Agent 循环和工具执行。"""
from dataclasses import dataclass
import os
import threading

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
    """导入前使用随包模型表、禁读.env；关闭遥测和外部日志集成。"""
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
    """按需加载 SDK，离线课和默认原生 HTTP 路径不需要导入 SDK。"""
    return load_sdk().completion(**kwargs)


class SDKCompletion:
    """只做模型调用和标准化；不接管工具或增加隐式 Agent 循环。"""
    def __init__(self, profile):
        self.profile = profile

    def __call__(self, body, api_key):
        profile = self.profile
        if not profile.config_ready or not body.get("model"):
            raise ValueError("请先配置所选服务商的模型与服务地址。")
        if profile.requires_key and not api_key:
            raise ValueError("请先配置所选服务商的 API Key。")
        prefixes = {
            "openai": "openai", "anthropic": "anthropic", "gemini": "gemini",
            "deepseek": "deepseek", "openrouter": "openrouter",
            "ollama": "ollama_chat", "custom": "openai",
        }
        # model 是用户填写的厂商原始 ID；prefix 只用于 SDK 内部选择适配器。
        kwargs = {
            **body,
            "model": prefixes[profile.id] + "/" + body["model"],
            # 显式传入所选 profile 的密钥，不能借用其他服务的全局环境变量。
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
