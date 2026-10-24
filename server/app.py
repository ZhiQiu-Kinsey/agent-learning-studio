"""本地 Web API；运行是服务端资源，事件脱敏后写入运行存储并通过 SSE 推送。

密钥只存在于后端内存；运行存储（.runtime/runs.sqlite3）只保存脱敏后的事件。
"""
import asyncio
import copy
import functools
import json
import re
import threading
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Literal

from fastapi import FastAPI, Header, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field, ValidationError
from starlette.middleware.trustedhost import TrustedHostMiddleware

from course.runner import RunCancelled
from course.api_client import BAILIAN_EMBEDDING_BATCH_LIMIT, send_bailian, send_bailian_embeddings, stream_bailian
from course.execution import EmbeddingNotConfigured, RunContext, execute_lesson, validate_inputs
from course.providers import SDKCompletion, SDKEmbedding
from server.catalog import (ROOT, LESSONS, CATALOG_INDEX, LessonValidationError, catalog_lesson, curriculum_outline,
                            exercise_requires_embedding, lesson_code_view, lesson_detail, lesson_presets,
                            lesson_runtime, lesson_spec, public_lesson, run_locale)
from server.content import load_onboarding
from server.content_overlay import LOCALE
from server.curriculum import roadmap
from server.envelope import SCHEMA_VERSION, EnvelopeBuilder, sdk_identity
from server.glossary import public_glossary
from server.lesson_refs import resolve_refs
from server.offline import approval_for, completion_for, embedding_for, stream_for
from server.providers import ProviderRegistry, embedding_setting, provider_label
from server.recordings import RecordingInvalid, RecordingStale, list_recordings, read_recording, source_hash
from server.run_store import RunStore, utc_now

app = FastAPI(title="AgentStart Learning Lab", docs_url=None, redoc_url=None)
app.add_middleware(TrustedHostMiddleware, allowed_hosts=["127.0.0.1", "localhost", "[::1]"])
# 同一时间只执行一次运行；测试可以持有该锁模拟忙碌状态。
run_lock = threading.Lock()
session_key = ""
provider_registry = ProviderRegistry()
RUNTIME_DIR = ROOT / ".runtime"
# 首次需要时才打开，导入模块不会创建数据库文件；测试替换为临时目录中的 RunStore。
run_store: RunStore | None = None
_store_lock = threading.Lock()
RUN_ID_PATTERN = re.compile(r"[0-9a-f]{32}")
# 确定性测试适配器不是 SDK；如实写出它的名字，版本留空。
TEST_ADAPTER = {"name": "deterministic-test-adapter", "version": None}
# 离线 Embedding 夹具在请求体里的模型名；分批上限与百炼一致，确定性运行的请求次数与默认真实路径相同。
OFFLINE_EMBEDDING_MODEL = "offline-embedding"
# 没有模型服务商的运行写进 run_start 的名称；按运行语言写，英文运行的事件里不出现中文。
LOCAL_PROVIDER_LABELS = {
    "zh-CN": {"testing": "确定性测试", "local": "本地 Python"},
    "en": {"testing": "Deterministic test", "local": "Local Python"},
}


def get_run_store() -> RunStore:
    global run_store
    with _store_lock:
        if run_store is None:
            run_store = RunStore(RUNTIME_DIR / "runs.sqlite3")
        return run_store


class ApiError(Exception):
    """带稳定错误码的接口错误。前端按 code 翻译（可用 params 插值）；没有对应译文时显示 detail。"""

    def __init__(self, status_code: int, code: str, message: str, params: dict | None = None):
        super().__init__(message)
        self.status_code, self.code, self.message, self.params = status_code, code, message, params


def current_key():
    return provider_registry.resolve(bailian_key=session_key).api_key


def configuration():
    profile = provider_registry.resolve(bailian_key=session_key)
    return profile.model or "未配置", profile.config_ready


def scrub(value, secrets):
    """递归脱敏，包括模型或异常意外回显的当前认证密钥。"""
    if isinstance(value, str):
        for secret in secrets:
            if secret:
                value = value.replace(secret, "[REDACTED]")
        return value
    if isinstance(value, list):
        return [scrub(v, secrets) for v in value]
    if isinstance(value, dict):
        return {scrub(k, secrets): scrub(v, secrets) for k, v in value.items()}
    return value


def require_locale(lang: str | None) -> str | None:
    """?lang= 选择内容译文层；不存在的译文回落到源语言，格式不合法才报错。"""
    if lang is None or LOCALE.fullmatch(lang):
        return lang
    raise ApiError(400, "invalid_locale", "语言代码格式无效。")


def require_lesson(lesson_id: str):
    """接受课程 slug（或目录里登记的旧 slug 别名），统一解析为可执行课程；不回显请求中的原始 id。"""
    spec = lesson_spec(lesson_id)
    if spec is not None:
        return spec
    planned = catalog_lesson(lesson_id)
    if planned is not None:
        raise ApiError(404, "lesson_not_available",
                       f"第 {planned['number']} 课「{planned['title']}」仍在规划中，暂不能打开或运行。",
                       {"number": planned["number"], "title": planned["title"]})
    raise ApiError(404, "lesson_not_found", "课程不存在。")


@app.exception_handler(RequestValidationError)
async def invalid_request(request: Request, error: RequestValidationError):
    # Pydantic默认422含原始input，可能把误粘贴的Key或URL返回给浏览器。
    return JSONResponse({"detail": "请求参数无效，请检查课程、模式、问题和练习。", "code": "invalid_request"},
                        status_code=422)


@app.exception_handler(ApiError)
async def api_error(request: Request, error: ApiError):
    body = {"detail": error.message, "code": error.code}
    if error.params:
        body["params"] = error.params
    return JSONResponse(body, status_code=error.status_code)


def public_status(profile):
    data = {"model": profile.model or "未配置", "api_key_configured": bool(profile.api_key),
            "requires_api_key": profile.requires_key,
            "config_ready": profile.config_ready, "provider_id": profile.id,
            "provider_label": profile.label, "trace_representation": profile.representation}
    return scrub(data, provider_registry.secrets(session_key))


@app.middleware("http")
async def local_request_guard(request: Request, call_next):
    if request.method in ("POST", "PUT", "PATCH", "DELETE"):
        origin = request.headers.get("origin")
        expected = f"{request.url.scheme}://{request.headers.get('host', '')}"
        if (origin is not None and origin != expected) or request.headers.get("sec-fetch-site") == "cross-site":
            return JSONResponse({"detail": "只接受本地页面发起的操作。"}, status_code=403)
        # 读取真实请求字节，避免缺失或虚假的 Content-Length 绕过限制。
        size = 0
        chunks = []
        async for chunk in request.stream():
            size += len(chunk)
            if size > 32768:
                return JSONResponse({"detail": "请求内容过长。"}, status_code=413)
            chunks.append(chunk)
        request._body = b"".join(chunks)
    response = await call_next(request)
    response.headers["Cache-Control"] = "no-store"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "no-referrer"
    # 'wasm-unsafe-eval' only allows compiling WebAssembly (the 3D badge's physics
    # engine), not JavaScript eval; blob: images/fetches are textures decoded from local models.
    response.headers["Content-Security-Policy"] = "default-src 'self'; script-src 'self' 'wasm-unsafe-eval'; style-src 'self' 'unsafe-inline'; img-src 'self' data: blob:; connect-src 'self' blob:; frame-ancestors 'none'; base-uri 'self'"
    return response


@app.get("/api/status")
def status():
    return public_status(provider_registry.resolve(bailian_key=session_key))


@app.get("/api/providers")
def providers():
    return scrub(provider_registry.public(session_key), provider_registry.secrets(session_key))


@app.post("/api/settings")
async def settings(request: Request):
    global session_key
    try:
        body = await request.json()
    except (ValueError, UnicodeDecodeError):
        raise ApiError(400, "invalid_json", "请提交有效 JSON。") from None
    try:
        provider_id, updates = provider_registry.update(body)
    except ValueError as error:
        raise ApiError(400, "settings_invalid", str(error)) from None
    if provider_id == "bailian" and "api_key" in updates:
        session_key = updates["api_key"]
    return public_status(provider_registry.resolve(bailian_key=session_key))


@app.get("/api/lessons")
def lessons(lang: str | None = None):
    locale = require_locale(lang)
    return {"lessons": [public_lesson(s, locale) for s in LESSONS], "roadmap": roadmap(locale)}


@app.get("/api/curriculum")
def curriculum(lang: str | None = None):
    return curriculum_outline(locale=require_locale(lang))


@app.get("/api/onboarding")
def onboarding(lang: str | None = None):
    """提供独立的前置阅读内容；不加载课程运行器或调用模型。"""
    locale = require_locale(lang)
    try:
        # 译文里的课程引用按目标语言写课号，没翻译的文本按源语言写。
        data = load_onboarding(ROOT / "curriculum" / "onboarding.json", locale,
                               lambda text: resolve_refs(text, CATALOG_INDEX.numbers, locale))
        return resolve_refs(data, CATALOG_INDEX.numbers)
    except LessonValidationError:
        raise ApiError(503, "onboarding_unavailable", "前置学习内容暂时不可用，请稍后重试。") from None


@app.get("/api/glossary")
def glossary(lang: str | None = None):
    """术语表单一来源；只读 JSON，不加载课程运行器。?lang= 合并该语言的显示名、释义与别名。"""
    locale = require_locale(lang)
    try:
        return public_glossary(ROOT, CATALOG_INDEX, locale)
    except (OSError, LessonValidationError):
        raise ApiError(503, "glossary_unavailable", "术语表暂时不可用，请稍后重试。") from None


@app.get("/api/lessons/{lesson_id}")
def detail(lesson_id: str, lang: str | None = None):
    return lesson_detail(require_lesson(lesson_id), require_locale(lang))


@app.get("/api/lessons/{lesson_id}/code")
def lesson_code(lesson_id: str, lang: str | None = None):
    """读码场景：源码符号、本课新增（与对比课的 AST 比较）和批注；只读本课 sources 白名单。"""
    spec = require_lesson(lesson_id)
    locale = require_locale(lang)
    try:
        return lesson_code_view(spec, locale)
    except (OSError, SyntaxError, ValueError):  # LessonValidationError 是 ValueError 的子类
        raise ApiError(503, "code_unavailable", "本课源码暂时无法解析，请检查课程源码与读码内容。") from None


# 随课录制是只读的课程资源，与 /api/runs（学习者自己的运行）完全分开，不写入运行存储。
@app.get("/api/lessons/{lesson_id}/recordings")
def lesson_recordings(lesson_id: str):
    """列出本课录制的元数据；校验失败的录制只返回名称与错误码。"""
    spec = require_lesson(lesson_id)
    return {"lesson_id": spec["id"],
            "recordings": list_recordings(spec, provider_registry.api_keys(session_key))}


@app.get("/api/lessons/{lesson_id}/recordings/{name}")
def lesson_recording(lesson_id: str, name: str):
    """返回通过完整校验的录制；校验失败时不返回事件。"""
    spec = require_lesson(lesson_id)
    try:
        metadata, events = read_recording(spec, name, provider_registry.api_keys(session_key))
    except FileNotFoundError:
        raise ApiError(404, "recording_not_found", "录制不存在。") from None
    except RecordingStale:
        raise ApiError(409, "recording_stale", "课程源码已变化，这份录制已过期，请重新录制。") from None
    except RecordingInvalid:
        raise ApiError(422, "recording_invalid", "录制未通过校验，已拒绝加载。") from None
    return {"lesson_id": spec["id"], "name": name, "metadata": metadata, "events": events}


class RunInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    lesson_id: str = Field(max_length=64)
    mode: Literal["offline", "live"] = "live"
    question: str = Field(max_length=8000)
    exercise_id: str = Field(max_length=32)
    inputs: dict[str, Any] | None = None
    # 界面语言；运行语言按本课支持的语言解析（server/catalog.py run_locale），没写时是源语言。
    locale: str | None = Field(None, max_length=35, pattern=LOCALE.pattern)


@dataclass
class RunPlan:
    """请求处理阶段完成全部校验与依赖解析；后台线程只执行，不再读取可变的全局配置。"""
    body: RunInput
    spec: dict
    module: Any
    inputs: dict
    locale: str
    key: str = field(repr=False)
    model: str
    provider_id: str
    provider_label: str
    representation: str
    envelope_representation: str | None
    sdk: dict | None
    completion: Callable | None = field(repr=False)
    completion_error: Exception | None
    secrets: list = field(repr=False)
    # Embedding 连接：没有配置时为 None，课程调用 context.embed 会得到带 code 的错误。
    embedding: Callable | None = field(default=None, repr=False)
    embedding_model: str | None = None
    embedding_batch_limit: int = BAILIAN_EMBEDDING_BATCH_LIMIT
    # 本练习是否声明要用 Embedding（写进 run_start）；缺配置时提示去改哪个设置。
    uses_embedding: bool = False
    embedding_setting: str | None = None
    # 流式连接（context.complete_stream）：离线用课程的 stream_factory，真实模式按服务商构造。
    stream_completion: Callable | None = field(default=None, repr=False)
    # 离线测试的确定性审批决定（testing.approval_factory）；真实运行永远是 None，只能由人决定。
    approval_policy: Callable | None = field(default=None, repr=False)
    unsupported_params: frozenset = frozenset()
    # 从检查点恢复时：{run_id, checkpoint_id, name, seq, state, state_digest, thread_id}。
    resume: dict | None = None
    # 课程源码哈希（与录制同一规则），写进检查点，恢复时据此拒绝源码已变化的检查点。
    source_hash: str | None = None


def lesson_source_hash(spec: dict) -> str | None:
    """课程源码哈希（规则同录制）；读不到源码时为 None，这时检查点不能恢复，而不是假装一致。"""
    try:
        return source_hash(spec)
    except (OSError, KeyError, TypeError):
        return None


def prepare_run(body: RunInput) -> RunPlan:
    spec = require_lesson(body.lesson_id)  # 别名请求也以 slug 记录，事件与回放只出现一种课程 ID。
    # 运行语言：界面语言在本课 runtime.locales 里就用它，否则回落（同语言的地区变体，再到源语言）。
    locale = run_locale(spec, body.locale)
    exercises, input_defaults = lesson_presets(spec, locale)
    exercise = next((e for e in exercises if e["id"] == body.exercise_id), None)
    if exercise is None:
        raise ApiError(400, "exercise_not_found", "练习不存在。")
    if not body.question.strip() and spec["runtime"]["kind"] == "native":
        raise ApiError(400, "question_required", "请输入问题。")
    if body.mode == "offline" and body.question.strip() != exercise["question"]:
        raise ApiError(400, "offline_requires_preset", "离线模式只运行预设练习；自由输入请切换真实模型模式。")
    if body.mode == "live" and exercise.get("offline_only"):
        raise ApiError(400, "fault_injection_offline_only", "该练习是离线故障注入，请切换离线模式。")
    defaults = {**input_defaults, **exercise.get("inputs", {})}
    # Explicit input (including {}) is authoritative; never add hidden presets
    # after a student has edited the JSON. Omitted inputs use declared defaults.
    values = defaults if body.inputs is None else body.inputs
    try:
        module = lesson_runtime(spec)
        inputs = validate_inputs(module, values)
        if body.mode == "offline" and inputs != validate_inputs(module, defaults):
            raise ApiError(400, "test_inputs_fixed", "测试模式只接受该练习预设的结构化输入。")
    except (ValidationError, ValueError):
        raise ApiError(422, "inputs_invalid", "课程输入无效，请检查本课要求的字段、类型和范围。") from None
    except (ImportError, AttributeError, TypeError):
        raise ApiError(503, "runtime_unavailable", "课程运行组件暂时不可用，请检查课程配置。") from None
    # 练习可以单独声明不调用模型（catalog 只允许 custom 运行器这样做），其余沿用课程的声明。
    requires_model = exercise.get("requires_model", spec["runtime"].get("requires_model", True))
    testing = spec.get("testing", {})
    if body.mode == "offline" and requires_model and not (testing.get("completion_factory")
                                                          or testing.get("embedding_factory")
                                                          or testing.get("stream_factory")):
        raise ApiError(400, "no_offline_fixture", "本课未提供确定性模型测试场景。")
    uses_embedding = exercise_requires_embedding(spec, exercise)
    profile = provider_registry.resolve(bailian_key=session_key) if body.mode == "live" and requires_model else None
    key = profile.api_key if profile else ""
    model = profile.model if profile else "offline-script" if requires_model else "local-python"
    representation = profile.representation if profile else "sdk_standardized" if requires_model else "local"
    if profile and (not profile.config_ready or profile.requires_key and not key):
        raise ApiError(400, "live_not_configured", "真实模式需要已配置的模型、服务地址和所选服务商 API Key；本地 Ollama 无需 Key。")
    # 本练习要用 Embedding 而服务商没有 Embedding 模型：开始前就拒绝，不悄悄换模型或跳过检索。
    if profile and uses_embedding and not profile.embedding_model:
        raise ApiError(400, "embedding_model_missing",
                       f"所选服务商还没有可用的 Embedding 模型配置。请在模型设置里填写 Embedding 模型，"
                       f"或设置 {embedding_setting(profile.id)}。",
                       {"setting": embedding_setting(profile.id)})
    # 信封如实标注表示层级：百炼原生 HTTP 是 http_body；LiteLLM 是 sdk_standardized 并附 SDK 版本；
    # 离线测试适配器返回标准化形状的字典，标注为测试适配器而不是 SDK；本地课程没有模型数据。
    if profile:
        sdk = sdk_identity("litellm") if representation == "sdk_standardized" else None
    else:
        sdk = dict(TEST_ADAPTER) if requires_model else None
    completion, completion_error = None, None
    try:
        if body.mode == "offline" and requires_model:
            # 只做 Embedding 的课没有 completion_factory，离线时 completion 为 None。
            completion = (completion_for(spec, body.exercise_id, inputs, locale)
                          if testing.get("completion_factory") else None)
        elif profile:
            completion = (functools.partial(send_bailian, locale=locale) if profile.id == "bailian"
                          else SDKCompletion(profile, locale))
    except Exception as error:  # 与原行为一致：作为运行中的 error 事件报告。
        completion_error = error
    # Embedding 连接：离线用课程夹具；真实模式按当前服务商构造（没有模型时为 None）。
    embedding, embedding_model = None, None
    embedding_batch_limit = profile.embedding_batch_limit if profile else BAILIAN_EMBEDDING_BATCH_LIMIT
    if body.mode == "offline" and requires_model and testing.get("embedding_factory"):
        embedding_model = OFFLINE_EMBEDDING_MODEL
        try:
            embedding = embedding_for(spec, body.exercise_id, inputs, locale)
        except Exception as error:
            completion_error = completion_error or error
    elif profile and profile.embedding_model:
        embedding_model = profile.embedding_model
        embedding = (functools.partial(send_bailian_embeddings, locale=locale) if profile.id == "bailian"
                     else SDKEmbedding(profile, locale))
    # 流式连接与离线审批决定：夹具只在离线测试模式使用；真实模式的审批只能由人在网页提交。
    stream_completion, approval_policy = None, None
    try:
        if body.mode == "offline" and requires_model and testing.get("stream_factory"):
            stream_completion = stream_for(spec, body.exercise_id, inputs, locale)
        elif profile:
            stream_completion = (functools.partial(stream_bailian, locale=locale) if profile.id == "bailian"
                                 else SDKCompletion(profile, locale).stream)
        if body.mode == "offline" and testing.get("approval_factory"):
            approval_policy = approval_for(spec, body.exercise_id, inputs, locale)
    except Exception as error:
        completion_error = completion_error or error
    lesson_hash = lesson_source_hash(spec)
    provider_id = profile.id if profile else "testing" if requires_model else "local"
    return RunPlan(
        body=body, spec=spec, module=module, inputs=inputs, locale=locale, key=key, model=model,
        provider_id=provider_id,
        provider_label=provider_label(provider_id, locale) if profile else LOCAL_PROVIDER_LABELS[locale][provider_id],
        representation=representation,
        envelope_representation=representation if representation in ("http_body", "sdk_standardized") else None,
        sdk=sdk, completion=completion, completion_error=completion_error,
        unsupported_params=profile.unsupported_params if profile else frozenset(),
        secrets=provider_registry.secrets(session_key),
        embedding=embedding, embedding_model=embedding_model, embedding_batch_limit=embedding_batch_limit,
        uses_embedding=uses_embedding, embedding_setting=embedding_setting(profile.id) if profile else None,
        stream_completion=stream_completion, approval_policy=approval_policy, source_hash=lesson_hash,
    )


@dataclass
class PendingApproval:
    """一条等待人决定的审批：只接受这一次运行、这一个 approval_id、这一份参数摘要，且只接受一次。"""
    request: dict
    decided: threading.Event = field(default_factory=threading.Event)
    decision: dict | None = None
    closed: bool = False


class ActiveRun:
    """正在执行的运行：串行分配 seq、先脱敏再写库，published 之前的事件才对读者可见。"""

    def __init__(self, run_id: str, store: RunStore, builder: EnvelopeBuilder, secrets: list):
        self.run_id, self.store, self.builder = run_id, store, builder
        self._secrets = secrets
        self._lock = threading.Lock()
        self.cancelled = threading.Event()
        # 谁要求停止：user_stop（停止按钮）、page_closed（页面关闭）、api（其他调用方）。
        self.cancel_reason: str | None = None
        self.published = 0
        # 运行结束前断开的事件连接数；断开连接不会停止运行。
        self.client_disconnects = 0
        self.pending_approvals: dict[str, PendingApproval] = {}
        self._approval_lock = threading.Lock()

    def request_cancel(self, reason: str):
        with self._lock:
            if self.cancel_reason is None:
                self.cancel_reason = reason
        self.cancelled.set()

    def wait_for_approval(self, request: dict, timeout_s: float) -> dict:
        """RunContext.approval_gate：运行停在这里（状态 paused），直到有人决定、超时或运行被停止。"""
        pending = PendingApproval(request=request)
        approval_id = request["approval_id"]
        with self._approval_lock:
            self.pending_approvals[approval_id] = pending
        self.store.set_live_status(self.run_id, "paused")
        deadline = time.monotonic() + timeout_s
        try:
            while True:
                if pending.decided.wait(0.1):
                    break
                with self._approval_lock:
                    if pending.decision is not None:
                        break
                    if self.cancelled.is_set():
                        pending.decision = {"decision": "cancelled"}
                    elif time.monotonic() >= deadline:
                        pending.decision = {"decision": "timeout"}
                    if pending.decision is not None:
                        break
        finally:
            with self._approval_lock:
                pending.closed = True
                self.pending_approvals.pop(approval_id, None)
            self.store.set_live_status(self.run_id, "running")
        return pending.decision

    def submit_approval(self, approval_id: str, decision: dict, payload_digest: str):
        """接口线程提交决定；与等待线程用同一把锁，迟到（已超时、已取消、已决定）的提交一律拒绝。"""
        with self._approval_lock:
            pending = self.pending_approvals.get(approval_id)
            if pending is None or pending.closed or pending.decision is not None:
                raise ApiError(409, "no_pending_approval", "该运行没有等待处理的这条审批，可能已经决定、超时或停止。")
            if payload_digest != pending.request["payload_digest"]:
                raise ApiError(409, "approval_digest_mismatch", "提交的参数摘要与待审批的请求不一致，请刷新后核对再决定。")
            if decision.get("edited_payload") is not None and not pending.request.get("editable"):
                raise ApiError(422, "approval_edit_not_allowed", "这条审批不允许修改参数，只能批准或拒绝。")
            pending.decision = decision
            pending.decided.set()

    def _build(self, kind, data, round_number):
        timestamp = datetime.now(timezone.utc).isoformat()
        event = self.builder.build(kind, scrub(data, self._secrets), round_number, timestamp)
        # 序列化即时形成不可变快照，后续追加消息不会改变先前请求。
        return event, json.dumps(event, ensure_ascii=False)

    def emit(self, kind, data, round_number=None):
        with self._lock:
            event, text = self._build(kind, data, round_number)
            self.store.append(self.run_id, event["seq"], kind, text)
            self.published = event["seq"]

    def finish(self, status, duration_ms):
        """done 与运行状态同一事务提交；读者在运行退出活动表后才会读到 done。"""
        data = {"status": status, "duration_ms": duration_ms}
        if status == "cancelled":
            data["cancel_reason"] = self.cancel_reason or "api"
        if self.client_disconnects:
            data["client_disconnects"] = self.client_disconnects
        with self._lock:
            event, text = self._build("done", data, None)
            self.store.finish(self.run_id, event["seq"], "done", text, status, utc_now())


active_runs: dict[str, ActiveRun] = {}
_active_lock = threading.Lock()


def active_run(run_id: str) -> ActiveRun | None:
    with _active_lock:
        return active_runs.get(run_id)


def start_run(plan: RunPlan) -> str:
    """调用方已持有 run_lock；线程结束时释放。"""
    body, spec = plan.body, plan.spec
    run_id = uuid.uuid4().hex
    store = get_run_store()
    builder = EnvelopeBuilder(run_id, provenance="real_run", representation=plan.envelope_representation,
                              sdk=plan.sdk)
    resume = plan.resume
    # 同一条恢复链共用一个 thread_id：第一次运行用自己的 run_id，恢复出来的运行沿用来源运行的。
    thread_id = resume["thread_id"] if resume else run_id
    store.create_run(run_id=run_id, lesson_id=spec["id"], exercise_id=body.exercise_id, mode=body.mode,
                     model=scrub(plan.model, plan.secrets), provider_id=plan.provider_id,
                     representation=plan.envelope_representation, provenance="real_run",
                     schema_version=SCHEMA_VERSION, created_at=utc_now(), locale=plan.locale,
                     thread_id=thread_id, resumed_from_run=resume["run_id"] if resume else None,
                     resumed_from_checkpoint=resume["checkpoint_id"] if resume else None)
    active = ActiveRun(run_id, store, builder, plan.secrets)
    with _active_lock:
        active_runs[run_id] = active
    started = time.perf_counter()

    def work():
        final_status = "completed"
        try:
            # locale 是这次运行的语言，回放按它标注；界面请求的语言不同（本课没有该语言）时一并记下。
            start = {"lesson_id": spec["id"], "mode": body.mode, "model": plan.model,
                     "question": body.question, "inputs": plan.inputs,
                     "runtime_kind": spec["runtime"]["kind"],
                     "provider_id": plan.provider_id, "provider_label": plan.provider_label,
                     "trace_representation": plan.representation, "locale": plan.locale}
            if body.locale and body.locale != plan.locale:
                start["requested_locale"] = body.locale
            if plan.uses_embedding:
                start["embedding_model"] = plan.embedding_model
            if resume:
                # 恢复不重放来源运行的任何请求：这里只记下从哪个检查点、带着什么状态开始。
                start["resumed_from"] = {key: resume[key] for key in
                                         ("run_id", "checkpoint_id", "name", "seq", "state", "state_digest")}
                start["thread_id"] = thread_id
            active.emit("run_start", start)
            if plan.completion_error is not None:
                raise plan.completion_error
            context = RunContext(
                lesson_id=spec["id"], exercise_id=body.exercise_id, question=body.question,
                mode=body.mode, model=plan.model, representation=plan.representation, inputs=plan.inputs,
                api_key=plan.key, completion=plan.completion, emit_event=active.emit,
                cancelled=active.cancelled.is_set, max_model_calls=spec["runtime"].get("max_rounds", 3),
                unsupported_params=plan.unsupported_params,
                locale=plan.locale, embedding=plan.embedding, embedding_model=plan.embedding_model,
                embedding_batch_limit=plan.embedding_batch_limit,
                stream_completion=plan.stream_completion, cancel_reason=lambda: active.cancel_reason,
                approval_gate=active.wait_for_approval, approval_policy=plan.approval_policy,
                resume_state=copy.deepcopy(resume["state"]) if resume else None,
                resumed_from={key: resume[key] for key in ("run_id", "checkpoint_id", "name")} if resume else None,
                thread_id=thread_id, source_hash=plan.source_hash,
                checkpoint_offset=resume["checkpoint_offset"] if resume else 0,
            )
            execute_lesson(spec, plan.module, context)
        except RunCancelled:
            final_status = "cancelled"
        except EmbeddingNotConfigured as error:
            # 带稳定错误码，前端翻译并引导去模型设置；setting 说明该改哪个配置。
            final_status = "error"
            active.emit("error", {"message": str(error), "error_type": type(error).__name__,
                                  "code": "embedding_model_missing",
                                  "params": {"setting": plan.embedding_setting or ""}})
        except Exception as error:
            final_status = "error"
            active.emit("error", {"message": str(error), "error_type": type(error).__name__})
        finally:
            try:
                active.finish(final_status, round((time.perf_counter() - started) * 1000))
            finally:
                # 先释放执行互斥再公开 done：客户端收到 done 时即可开始下一次运行。
                run_lock.release()
                with _active_lock:
                    active_runs.pop(run_id, None)

    try:
        threading.Thread(target=work, name="agent-course-run", daemon=True).start()
    except BaseException:
        with _active_lock:
            active_runs.pop(run_id, None)
        raise
    return run_id


def stored_run(run_id: str) -> dict:
    run = get_run_store().get_run(run_id) if RUN_ID_PATTERN.fullmatch(run_id) else None
    if run is None:
        raise ApiError(404, "run_not_found", "运行记录不存在或已被清除。")
    return run


@app.post("/api/runs", status_code=202)
def create_run(body: RunInput):
    plan = prepare_run(body)
    if not run_lock.acquire(blocking=False):
        raise ApiError(409, "run_busy", "上一次运行尚未结束，请等待网络请求返回（网络超时 60 秒）。")
    try:
        run_id = start_run(plan)
    except BaseException:
        run_lock.release()
        raise
    return {"run_id": run_id}


@app.get("/api/runs")
def list_runs(limit: int = Query(50, ge=1, le=500)):
    return {"runs": get_run_store().list_runs(limit)}


@app.delete("/api/runs")
def clear_runs():
    """一键清除全部运行记录；有运行在执行时拒绝，避免删除仍在写入的记录。"""
    if not run_lock.acquire(blocking=False):
        raise ApiError(409, "run_active", "有运行尚未结束，请在运行结束后再清除记录。")
    try:
        return {"deleted": get_run_store().clear()}
    finally:
        run_lock.release()


@app.get("/api/runs/{run_id}")
def run_metadata(run_id: str):
    return stored_run(run_id)


@app.get("/api/runs/{run_id}/events")
async def run_events(run_id: str, request: Request, from_seq: int | None = Query(None, ge=1, le=10**9),
                     last_event_id: str | None = Header(None)):
    """先回放存储中 seq ≥ from_seq 的事件，再接续实时事件，直到 done。断线后带 from_seq 续读。"""
    stored_run(run_id)
    if from_seq is None:
        # 兼容浏览器 EventSource 的自动重连头；无效值从头读取。
        from_seq = int(last_event_id) + 1 if last_event_id and last_event_id.isdigit() else 1
    store = get_run_store()

    async def stream():
        reached_end = False
        try:
            async for chunk in events_from(from_seq):
                if chunk is None:
                    reached_end = True
                    return
                yield chunk
        finally:
            # 读者在运行结束前离开（断网、关闭连接）：只计数写进 done，运行照常继续。
            active = active_run(run_id)
            if not reached_end and active is not None:
                active.client_disconnects += 1

    async def events_from(next_seq):
        heartbeat = time.monotonic()
        while True:
            if await request.is_disconnected():
                return
            active = active_run(run_id)
            # 运行中只读到已公开的水位；读库放到线程池，避免写入时的 fsync 阻塞事件循环。
            rows = await asyncio.to_thread(store.events, run_id, next_seq, active.published if active else None)
            for seq, kind, text in rows:
                yield f"id: {seq}\ndata: {text}\n\n"
                next_seq = seq + 1
                if kind == "done":
                    yield None
                    return
            if rows:
                heartbeat = time.monotonic()
                continue
            if active is None:
                yield None
                return  # 已结束且读完；异常中断的运行没有 done，也在此结束。
            if time.monotonic() - heartbeat > 10:
                yield ": waiting\n\n"
                heartbeat = time.monotonic()
            await asyncio.sleep(0.05)

    return StreamingResponse(stream(), media_type="text/event-stream", headers={"X-Accel-Buffering": "no"})


class CancelInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    # user_stop：学习者点了停止；page_closed：页面关闭（pagehide 的 keepalive 请求）。没有请求体时记为 api。
    reason: Literal["user_stop", "page_closed"] | None = None


@app.post("/api/runs/{run_id}/cancel", status_code=202)
def cancel_run(run_id: str, body: CancelInput | None = None):
    """停止指定运行的后续步骤；已经发出的模型请求仍受网络超时约束，流式请求在下一个分块前停止接收。"""
    stored_run(run_id)
    active = active_run(run_id)
    if active is None:
        raise ApiError(409, "run_not_active", "该运行已经结束，无需停止。")
    active.request_cancel(body.reason if body and body.reason else "api")
    return {"run_id": run_id, "status": "cancelling", "reason": active.cancel_reason}


class ApprovalInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    approval_id: str = Field(min_length=1, max_length=64, pattern=r"^approval-[0-9]{1,6}$")
    decision: Literal["approve", "reject"]
    # 必须与 approval_requested 里的摘要一致：证明决定针对的就是页面上看到的那组参数。
    payload_digest: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    note: str | None = Field(None, max_length=2000)
    # 只有 editable 的请求可以带修改后的参数，而且只能和 approve 一起提交。
    edited_payload: dict[str, Any] | None = None


@app.post("/api/runs/{run_id}/approvals")
def submit_approval(run_id: str, body: ApprovalInput):
    """提交人的决定：只接受当前运行、当前待决的那条审批，参数摘要必须一致；决定由运行线程写成事件。"""
    stored_run(run_id)
    active = active_run(run_id)
    if active is None:
        raise ApiError(409, "approval_run_finished", "该运行已经结束，不能再提交审批；回放里的审批记录只读。")
    if body.edited_payload is not None and body.decision != "approve":
        raise ApiError(422, "approval_edit_not_allowed", "这条审批不允许修改参数，只能批准或拒绝。")
    decision = {"decision": body.decision, "note": body.note}
    if body.edited_payload is not None:
        decision["edited_payload"] = body.edited_payload
    active.submit_approval(body.approval_id, decision, body.payload_digest)
    return {"run_id": run_id, "approval_id": body.approval_id, "decision": body.decision, "status": "accepted"}


class ResumeInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    checkpoint_id: str = Field(pattern=r"^cp-[0-9]{1,4}$")


@app.post("/api/runs/{run_id}/resume", status_code=202)
def resume_run(run_id: str, body: ResumeInput):
    """从某次运行的某个检查点启动一次新运行：同一课程、练习、问题、输入、模式与运行语言。

    不重放来源运行的任何模型请求或工具调用；新运行从 context.resume_state 继续，之后的请求都是真实新请求。
    """
    source = stored_run(run_id)
    if active_run(run_id) is not None:
        raise ApiError(409, "run_still_active", "这次运行还没有结束，结束（或停止）后才能从它的检查点恢复。")
    store = get_run_store()
    event = store.checkpoint(run_id, body.checkpoint_id)
    start = store.first_event(run_id, "run_start")
    if event is None or start is None:
        raise ApiError(404, "checkpoint_not_found", "这次运行没有这个检查点。")
    spec = require_lesson(source["lesson_id"])
    checkpoint = event["data"]
    current_hash = lesson_source_hash(spec)
    if not checkpoint.get("source_hash") or checkpoint["source_hash"] != current_hash:
        raise ApiError(409, "checkpoint_stale", "课程源码在保存这个检查点之后变了，不能从它恢复；请重新运行。")
    data = start["data"]
    resume_input = RunInput(lesson_id=spec["id"], mode=source["mode"], question=data.get("question", ""),
                            exercise_id=source["exercise_id"], inputs=data.get("inputs") or {},
                            locale=source["locale"])
    plan = prepare_run(resume_input)
    plan.resume = {"run_id": run_id, "checkpoint_id": checkpoint["checkpoint_id"], "name": checkpoint["name"],
                   "seq": event["seq"], "state": checkpoint["state"], "state_digest": checkpoint["state_digest"],
                   "thread_id": source.get("thread_id") or run_id,
                   "checkpoint_offset": store.last_checkpoint_number(run_id)}
    if not run_lock.acquire(blocking=False):
        raise ApiError(409, "run_busy", "上一次运行尚未结束，请等待网络请求返回（网络超时 60 秒）。")
    try:
        new_id = start_run(plan)
    except BaseException:
        run_lock.release()
        raise
    return {"run_id": new_id, "resumed_from": {"run_id": run_id, "checkpoint_id": checkpoint["checkpoint_id"]}}


# 前端先构建；只公开 dist，不暴露项目、配置或 Python 文件目录。
dist = ROOT / "frontend" / "dist"
if dist.is_dir():
    app.mount("/", StaticFiles(directory=dist, html=True), name="frontend")
else:
    @app.get("/")
    def frontend_pending():
        return JSONResponse({"detail": "请先在 frontend 目录执行 npm install 和 npm run build。"}, status_code=503)
