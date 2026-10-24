"""模型配置只保存在后端内存；公开接口只返回配置状态。"""
import os
import threading
from urllib.parse import unquote, urlsplit, urlunsplit

from course.api_client import (BAILIAN_EMBEDDING_BATCH_LIMIT, bailian_embedding_model,
                               bailian_embeddings_url)
from course.providers import ModelProfile


# env 名称分别绑定厂商；托管的同名模型不改变 endpoint 的服务商归属。
PROVIDERS = {
    "bailian": ("百炼（原生 HTTP）", "DASHSCOPE_API_KEY", "", ""),
    "openai": ("OpenAI", "OPENAI_API_KEY", "OPENAI_MODEL", "OPENAI_BASE_URL"),
    "anthropic": ("Anthropic", "ANTHROPIC_API_KEY", "ANTHROPIC_MODEL", "ANTHROPIC_BASE_URL"),
    "gemini": ("Google Gemini", "GEMINI_API_KEY", "GEMINI_MODEL", "GEMINI_API_BASE"),
    "deepseek": ("DeepSeek", "DEEPSEEK_API_KEY", "DEEPSEEK_MODEL", "DEEPSEEK_BASE_URL"),
    "openrouter": ("OpenRouter", "OPENROUTER_API_KEY", "OPENROUTER_MODEL", "OPENROUTER_BASE_URL"),
    "ollama": ("Ollama（本地）", "OLLAMA_API_KEY", "OLLAMA_MODEL", "OLLAMA_BASE_URL"),
    "custom": ("OpenAI compatible", "CUSTOM_API_KEY", "CUSTOM_MODEL", "CUSTOM_API_BASE"),
}
# Embedding 模型：百炼读 local_config（默认 text-embedding-v4），OpenAI 默认 text-embedding-3-small，
# 其他服务商只认环境变量 <PROVIDER>_EMBEDDING_MODEL 或网页设置；没有就是未配置，平台不替学生挑模型。
EMBEDDING_MODEL_ENV = {provider_id: (provider_id.upper() + "_EMBEDDING_MODEL") for provider_id in PROVIDERS
                       if provider_id != "bailian"}
DEFAULT_EMBEDDING_MODELS = {"openai": "text-embedding-3-small"}
# 每次 Embedding 请求最多几条输入。百炼兼容接口是 10（官方文档）；OpenAI 是 2048；
# 其他服务商的上限各不相同，平台统一取保守的 10。课程代码按这个值自己分批。
EMBEDDING_BATCH_LIMITS = {"bailian": BAILIAN_EMBEDDING_BATCH_LIMIT, "openai": 2048}
DEFAULT_EMBEDDING_BATCH_LIMIT = 10


def embedding_setting(provider_id):
    """缺 Embedding 配置时提示学生去改的设置名：百炼是 local_config，其他服务商是环境变量。"""
    return "local_config.EMBEDDING_MODEL / EMBEDDING_API_URL" if provider_id == "bailian" \
        else EMBEDDING_MODEL_ENV[provider_id]


# 写进英文运行事件（run_start.provider_label）的名称；没列出的服务商名称本来就是英文。
ENGLISH_LABELS = {"bailian": "Bailian (raw HTTP)", "ollama": "Ollama (local)"}


def provider_label(provider_id, locale):
    """运行事件里的服务商名称，按运行语言写。界面显示另由前端按 provider_id 翻译。"""
    label = PROVIDERS[provider_id][0]
    return ENGLISH_LABELS.get(provider_id, label) if locale == "en" else label


def normalize_api_base(value):
    """SDK接收base URL；接受完整chat/completions URL并明确去除该后缀。"""
    if not isinstance(value, str) or not value.strip() or len(value) > 2048:
        raise ValueError("请填写有效的 API Base URL。")
    value = value.strip()
    if any(ord(char) < 33 for char in value) or "\\" in value:
        raise ValueError("API Base URL 不能包含空白或本机路径。")
    try:
        parts = urlsplit(value)
        hostname = parts.hostname
        port = parts.port
    except ValueError:
        raise ValueError("请填写有效的 API Base URL。") from None
    del port  # 访问port会校验无效端口；不将URL加入错误信息。
    local = hostname in {"localhost", "127.0.0.1", "::1"}
    if not hostname or not (parts.scheme == "https" or parts.scheme == "http" and local):
        raise ValueError("API Base URL 需使用 HTTPS，或本机 localhost HTTP。")
    if parts.username is not None or parts.password is not None or parts.query or parts.fragment:
        raise ValueError("API Base URL 不能包含认证信息、查询参数或片段。")
    path = parts.path.rstrip("/")
    decoded_path = unquote(path)
    if any(segment in {".", ".."} for segment in decoded_path.split("/")):
        raise ValueError("API Base URL 路径无效。")
    if path.endswith("/chat/completions"):
        path = path[:-len("/chat/completions")]
    return urlunsplit((parts.scheme, parts.netloc, path, "", ""))


class ProviderRegistry:
    def __init__(self):
        self.active = "bailian"
        self.overrides = {}
        self.lock = threading.RLock()

    def resolve(self, provider_id=None, bailian_key=""):
        with self.lock:
            provider_id = provider_id or self.active
            label, key_env, model_env, base_env = PROVIDERS[provider_id]
            override = dict(self.overrides.get(provider_id, {}))
            key = (bailian_key if provider_id == "bailian" else override.get("api_key", ""))
            key = key or os.environ.get(key_env, "").strip()
            requires_key = provider_id != "ollama"
            if provider_id == "bailian":
                try:
                    from local_config import API_URL, MODEL
                    model = override.get("model", MODEL)
                    base = API_URL
                    valid_base = isinstance(base, str) and base.startswith("https://")
                except (ImportError, AttributeError, SyntaxError):
                    model, base, valid_base = "", None, False
            else:
                model = override.get("model", os.environ.get(model_env, "").strip())
                base = override.get("api_base", os.environ.get(base_env, "").strip() or None)
                if provider_id == "ollama" and base is None:
                    base = "http://localhost:11434"
                valid_base = True
                if base:
                    try:
                        base = normalize_api_base(base)
                    except ValueError:
                        valid_base = False
                elif provider_id == "custom":
                    valid_base = False
            valid_model = isinstance(model, str) and bool(model.strip())
            return ModelProfile(provider_id, label, model.strip() if valid_model else "",
                                key, base, valid_base and valid_model, requires_key,
                                provider_id != "bailian",
                                embedding_model=self._embedding_model(provider_id, override),
                                embedding_batch_limit=EMBEDDING_BATCH_LIMITS.get(
                                    provider_id, DEFAULT_EMBEDDING_BATCH_LIMIT))

    @staticmethod
    def _embedding_model(provider_id, override):
        """当前服务商的 Embedding 模型；空字符串表示未配置（百炼还要求能确定 embeddings 地址）。"""
        if provider_id == "bailian":
            try:
                model = override.get("embedding_model") or bailian_embedding_model()
                url = bailian_embeddings_url()
            except (ImportError, AttributeError, SyntaxError):
                return ""
            return model if url and model else ""
        model = override.get("embedding_model") or os.environ.get(EMBEDDING_MODEL_ENV[provider_id], "").strip() \
            or DEFAULT_EMBEDDING_MODELS.get(provider_id, "")
        return model.strip()

    def update(self, body):
        """先完整校验，再原子更新；错误不包含用户输入、密钥或URL。"""
        if not isinstance(body, dict) or not body or set(body) - {"provider_id", "model", "api_base", "api_key",
                                                        "embedding_model"}:
            raise ValueError("请输入有效的模型设置。")
        provider_id = body.get("provider_id", self.active)
        if not isinstance(provider_id, str) or provider_id not in PROVIDERS:
            raise ValueError("请选择有效的服务商。")
        updates = {}
        for name, limit in (("api_key", 1024), ("model", 256), ("api_base", 2048), ("embedding_model", 256)):
            if name not in body:
                continue
            value = body[name]
            if not isinstance(value, str) or len(value) > limit or any(ord(c) < 32 for c in value):
                raise ValueError("请输入有效的模型设置。")
            value = value.strip()
            if name == "api_base":
                if not value:
                    continue
                if provider_id == "bailian":
                    raise ValueError("百炼原生 HTTP 使用现有本地配置；自定义地址请选择兼容服务。")
                value = normalize_api_base(value)
            updates[name] = value
        with self.lock:
            # 百炼 session_key 由旧server接口持有，保留已有测试与调用约定。
            stored = {k: v for k, v in updates.items() if not (provider_id == "bailian" and k == "api_key")}
            self.overrides.setdefault(provider_id, {}).update(stored)
            self.active = provider_id
        return provider_id, updates

    def public(self, bailian_key=""):
        with self.lock:
            profiles = [self.resolve(provider_id, bailian_key) for provider_id in PROVIDERS]
            return {"active_provider": self.active, "providers": [public_profile(p) for p in profiles]}

    def secrets(self, bailian_key=""):
        with self.lock:
            profiles = [self.resolve(provider_id, bailian_key) for provider_id in PROVIDERS]
            values = [bailian_key]
            for profile in profiles:
                values.extend((profile.api_key, profile.api_base))
                if isinstance(profile.api_base, str):
                    # HTTP异常可能只报告hostname，仍不把私有服务地址回显到UI。
                    try:
                        values.append(urlsplit(profile.api_base).hostname)
                    except ValueError:
                        pass
            values.extend(os.environ.get(entry[1], "") for entry in PROVIDERS.values())
            return [value for value in values if isinstance(value, str) and value]

    def api_keys(self, bailian_key=""):
        """当前已配置的全部 API Key（不含服务地址）；用于录制的密钥检查。"""
        with self.lock:
            values = [bailian_key, *(self.resolve(provider_id, bailian_key).api_key for provider_id in PROVIDERS)]
            values.extend(os.environ.get(entry[1], "") for entry in PROVIDERS.values())
            return [value for value in values if isinstance(value, str) and value]


def public_profile(profile):
    return {"id": profile.id, "label": profile.label, "model": profile.model,
            "api_key_configured": bool(profile.api_key), "config_ready": profile.config_ready,
            "requires_api_key": profile.requires_key,
            "base_url_configured": bool(profile.api_base),
            "supports_custom_base_url": profile.supports_custom_base_url,
            "embedding_model": profile.embedding_model}
