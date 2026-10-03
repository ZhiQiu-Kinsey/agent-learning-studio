"""本地 Web API；运行是服务端资源，事件脱敏后写入运行存储并通过 SSE 推送。

密钥只存在于后端内存；运行存储（.runtime/runs.sqlite3）只保存脱敏后的事件。
"""
import asyncio
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
from course.api_client import send_bailian
from course.execution import RunContext, execute_lesson, validate_inputs
from course.providers import SDKCompletion
from server.catalog import (ROOT, LESSONS, CATALOG_INDEX, LessonValidationError, catalog_lesson, curriculum_outline,
                            lesson_code_view,
                            lesson_detail, lesson_runtime, lesson_spec, public_lesson)
from server.content import load_onboarding
from server.content_overlay import LOCALE
from server.curriculum import roadmap
from server.envelope import SCHEMA_VERSION, EnvelopeBuilder, sdk_identity
from server.glossary import public_glossary
from server.lesson_refs import resolve_refs
from server.offline import completion_for
from server.providers import ProviderRegistry
from server.recordings import RecordingInvalid, RecordingStale, list_recordings, read_recording
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
def lessons():
    return {"lessons": [public_lesson(s) for s in LESSONS], "roadmap": roadmap()}


@app.get("/api/curriculum")
def curriculum():
    return curriculum_outline()


@app.get("/api/onboarding")
def onboarding(lang: str | None = None):
    """提供独立的前置阅读内容；不加载课程运行器或调用模型。"""
    locale = require_locale(lang)
    try:
        data = load_onboarding(ROOT / "curriculum" / "onboarding.json", locale)
        return resolve_refs(data, CATALOG_INDEX.numbers, data["i18n"]["locale"])
    except LessonValidationError:
        raise ApiError(503, "onboarding_unavailable", "前置学习内容暂时不可用，请稍后重试。") from None


@app.get("/api/glossary")
def glossary():
    """术语表单一来源；只读 JSON，不加载课程运行器。"""
    try:
        return public_glossary(ROOT, CATALOG_INDEX)
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


@dataclass
class RunPlan:
    """请求处理阶段完成全部校验与依赖解析；后台线程只执行，不再读取可变的全局配置。"""
    body: RunInput
    spec: dict
    module: Any
    inputs: dict
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


def prepare_run(body: RunInput) -> RunPlan:
    spec = require_lesson(body.lesson_id)  # 别名请求也以 slug 记录，事件与回放只出现一种课程 ID。
    exercise = next((e for e in spec["exercises"] if e["id"] == body.exercise_id), None)
    if exercise is None:
        raise ApiError(400, "exercise_not_found", "练习不存在。")
    if not body.question.strip() and spec["runtime"]["kind"] == "native":
        raise ApiError(400, "question_required", "请输入问题。")
    if body.mode == "offline" and body.question.strip() != exercise["question"]:
        raise ApiError(400, "offline_requires_preset", "离线模式只运行预设练习；自由输入请切换真实模型模式。")
    if body.mode == "live" and exercise.get("offline_only"):
        raise ApiError(400, "fault_injection_offline_only", "该练习是离线故障注入，请切换离线模式。")
    defaults = {**spec.get("input_defaults", {}), **exercise.get("inputs", {})}
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
    requires_model = spec["runtime"].get("requires_model", True)
    if body.mode == "offline" and requires_model and not spec.get("testing", {}).get("completion_factory"):
        raise ApiError(400, "no_offline_fixture", "本课未提供确定性模型测试场景。")
    profile = provider_registry.resolve(bailian_key=session_key) if body.mode == "live" and requires_model else None
    key = profile.api_key if profile else ""
    model = profile.model if profile else "offline-script" if requires_model else "local-python"
    representation = profile.representation if profile else "sdk_standardized" if requires_model else "local"
    if profile and (not profile.config_ready or profile.requires_key and not key):
        raise ApiError(400, "live_not_configured", "真实模式需要已配置的模型、服务地址和所选服务商 API Key；本地 Ollama 无需 Key。")
    # 信封如实标注表示层级：百炼原生 HTTP 是 http_body；LiteLLM 是 sdk_standardized 并附 SDK 版本；
    # 离线测试适配器返回标准化形状的字典，标注为测试适配器而不是 SDK；本地课程没有模型数据。
    if profile:
        sdk = sdk_identity("litellm") if representation == "sdk_standardized" else None
    else:
        sdk = dict(TEST_ADAPTER) if requires_model else None
    completion, completion_error = None, None
    try:
        completion = (completion_for(spec, body.exercise_id, inputs) if body.mode == "offline" and requires_model
                      else send_bailian if profile and profile.id == "bailian"
                      else SDKCompletion(profile) if profile else None)
    except Exception as error:  # 与原行为一致：作为运行中的 error 事件报告。
        completion_error = error
    return RunPlan(
        body=body, spec=spec, module=module, inputs=inputs, key=key, model=model,
        provider_id=profile.id if profile else "testing" if requires_model else "local",
        provider_label=profile.label if profile else "确定性测试" if requires_model else "本地 Python",
        representation=representation,
        envelope_representation=representation if representation in ("http_body", "sdk_standardized") else None,
        sdk=sdk, completion=completion, completion_error=completion_error,
        secrets=provider_registry.secrets(session_key),
    )


class ActiveRun:
    """正在执行的运行：串行分配 seq、先脱敏再写库，published 之前的事件才对读者可见。"""

    def __init__(self, run_id: str, store: RunStore, builder: EnvelopeBuilder, secrets: list):
        self.run_id, self.store, self.builder = run_id, store, builder
        self._secrets = secrets
        self._lock = threading.Lock()
        self.cancelled = threading.Event()
        self.published = 0
        # 审批骨架：目前没有课程请求审批，因此始终为空。
        self.pending_approvals: dict[str, dict] = {}

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
        with self._lock:
            event, text = self._build("done", {"status": status, "duration_ms": duration_ms}, None)
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
    store.create_run(run_id=run_id, lesson_id=spec["id"], exercise_id=body.exercise_id, mode=body.mode,
                     model=scrub(plan.model, plan.secrets), provider_id=plan.provider_id,
                     representation=plan.envelope_representation, provenance="real_run",
                     schema_version=SCHEMA_VERSION, created_at=utc_now())
    active = ActiveRun(run_id, store, builder, plan.secrets)
    with _active_lock:
        active_runs[run_id] = active
    started = time.perf_counter()

    def work():
        final_status = "completed"
        try:
            active.emit("run_start", {"lesson_id": spec["id"], "mode": body.mode, "model": plan.model,
                                      "question": body.question, "inputs": plan.inputs,
                                      "runtime_kind": spec["runtime"]["kind"],
                                      "provider_id": plan.provider_id, "provider_label": plan.provider_label,
                                      "trace_representation": plan.representation})
            if plan.completion_error is not None:
                raise plan.completion_error
            context = RunContext(
                lesson_id=spec["id"], exercise_id=body.exercise_id, question=body.question,
                mode=body.mode, model=plan.model, representation=plan.representation, inputs=plan.inputs,
                api_key=plan.key, completion=plan.completion, emit_event=active.emit,
                cancelled=active.cancelled.is_set, max_model_calls=spec["runtime"].get("max_rounds", 3),
            )
            execute_lesson(spec, plan.module, context)
        except RunCancelled:
            final_status = "cancelled"
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
        next_seq = from_seq
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
                    return
            if rows:
                heartbeat = time.monotonic()
                continue
            if active is None:
                return  # 已结束且读完；异常中断的运行没有 done，也在此结束。
            if time.monotonic() - heartbeat > 10:
                yield ": waiting\n\n"
                heartbeat = time.monotonic()
            await asyncio.sleep(0.05)

    return StreamingResponse(stream(), media_type="text/event-stream", headers={"X-Accel-Buffering": "no"})


@app.post("/api/runs/{run_id}/cancel", status_code=202)
def cancel_run(run_id: str):
    """停止指定运行的后续步骤；已经发出的模型请求仍受网络超时约束。"""
    stored_run(run_id)
    active = active_run(run_id)
    if active is None:
        raise ApiError(409, "run_not_active", "该运行已经结束，无需停止。")
    active.cancelled.set()
    return {"run_id": run_id, "status": "cancelling"}


class ApprovalInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    approval_id: str = Field(min_length=1, max_length=64)
    decision: Literal["approve", "reject"]
    note: str | None = Field(None, max_length=2000)


@app.post("/api/runs/{run_id}/approvals")
def submit_approval(run_id: str, body: ApprovalInput):
    """审批接口骨架：当前没有课程发出 approval.requested，因此总是没有待审批项。"""
    stored_run(run_id)
    active = active_run(run_id)
    if active is None or body.approval_id not in active.pending_approvals:
        raise ApiError(409, "no_pending_approval", "该运行没有等待处理的审批。")
    raise ApiError(501, "approval_not_supported", "当前版本尚未支持处理审批。")


# 前端先构建；只公开 dist，不暴露项目、配置或 Python 文件目录。
dist = ROOT / "frontend" / "dist"
if dist.is_dir():
    app.mount("/", StaticFiles(directory=dist, html=True), name="frontend")
else:
    @app.get("/")
    def frontend_pending():
        return JSONResponse({"detail": "请先在 frontend 目录执行 npm install 和 npm run build。"}, status_code=503)
