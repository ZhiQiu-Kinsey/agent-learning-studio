"""本地 Web API；逐事件推送运行轨迹，不保存密钥或会话内容。"""
import asyncio
import json
import queue
import threading
import time
from datetime import datetime, timezone
from typing import Any, Literal

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field, ValidationError
from starlette.middleware.trustedhost import TrustedHostMiddleware

from course.runner import RunCancelled
from course.api_client import send_bailian
from course.execution import RunContext, execute_lesson, validate_inputs
from course.providers import SDKCompletion
from server.catalog import ROOT, LESSONS, lesson_detail, lesson_runtime, lesson_spec, public_lesson
from server.curriculum import public_curriculum, roadmap
from server.offline import completion_for
from server.providers import ProviderRegistry

app = FastAPI(title="AgentStart Learning Lab", docs_url=None, redoc_url=None)
app.add_middleware(TrustedHostMiddleware, allowed_hosts=["127.0.0.1", "localhost", "[::1]"])
run_lock = threading.Lock()
session_key = ""
provider_registry = ProviderRegistry()


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


@app.exception_handler(RequestValidationError)
async def invalid_request(request: Request, error: RequestValidationError):
    # Pydantic默认422含原始input，可能把误粘贴的Key或URL返回给浏览器。
    return JSONResponse({"detail": "请求参数无效，请检查课程、模式、问题和练习。"}, status_code=422)


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
    response.headers["Content-Security-Policy"] = "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; base-uri 'self'"
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
        raise HTTPException(400, "请提交有效 JSON。") from None
    try:
        provider_id, updates = provider_registry.update(body)
    except ValueError as error:
        raise HTTPException(400, str(error)) from None
    if provider_id == "bailian" and "api_key" in updates:
        session_key = updates["api_key"]
    return public_status(provider_registry.resolve(bailian_key=session_key))


@app.get("/api/lessons")
def lessons():
    return {"lessons": [public_lesson(s) for s in LESSONS], "roadmap": roadmap()}


@app.get("/api/curriculum")
def curriculum():
    return public_curriculum()


@app.get("/api/onboarding")
def onboarding():
    """提供独立的前置阅读内容；不加载课程运行器或调用模型。"""
    try:
        return json.loads((ROOT / "curriculum" / "onboarding.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        raise HTTPException(503, "前置学习内容暂时不可用，请稍后重试。") from None


@app.get("/api/lessons/{lesson_id}")
def detail(lesson_id: str):
    spec = lesson_spec(lesson_id)
    if spec is None:
        raise HTTPException(404, "课程不存在。")
    return lesson_detail(spec)


class RunInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    lesson_id: str = Field(max_length=32)
    mode: Literal["offline", "live"] = "live"
    question: str = Field(max_length=8000)
    exercise_id: str = Field(max_length=32)
    inputs: dict[str, Any] | None = None


@app.post("/api/run")
async def run(body: RunInput, request: Request):
    spec = lesson_spec(body.lesson_id)
    if spec is None:
        raise HTTPException(404, "课程不存在。")
    exercise = next((e for e in spec["exercises"] if e["id"] == body.exercise_id), None)
    if exercise is None:
        raise HTTPException(400, "练习不存在。")
    if not body.question.strip() and spec["runtime"]["kind"] == "native":
        raise HTTPException(400, "请输入问题。")
    if body.mode == "offline" and body.question.strip() != exercise["question"]:
        raise HTTPException(400, "离线模式只运行预设练习；自由输入请切换真实模型模式。")
    if body.mode == "live" and exercise.get("offline_only"):
        raise HTTPException(400, "该练习是离线故障注入，请切换离线模式。")
    defaults = {**spec.get("input_defaults", {}), **exercise.get("inputs", {})}
    # Explicit input (including {}) is authoritative; never add hidden presets
    # after a student has edited the JSON. Omitted inputs use declared defaults.
    values = defaults if body.inputs is None else body.inputs
    try:
        module = lesson_runtime(spec)
        inputs = validate_inputs(module, values)
        if body.mode == "offline" and inputs != validate_inputs(module, defaults):
            raise HTTPException(400, "测试模式只接受该练习预设的结构化输入。")
    except (ValidationError, ValueError):
        raise HTTPException(422, "课程输入无效，请检查本课要求的字段、类型和范围。") from None
    except (ImportError, AttributeError, TypeError):
        raise HTTPException(503, "课程运行组件暂时不可用，请检查课程配置。") from None
    requires_model = spec["runtime"].get("requires_model", True)
    if body.mode == "offline" and requires_model and not spec.get("testing", {}).get("completion_factory"):
        raise HTTPException(400, "本课未提供确定性模型测试场景。")
    profile = provider_registry.resolve(bailian_key=session_key) if body.mode == "live" and requires_model else None
    key = profile.api_key if profile else ""
    model = profile.model if profile else "offline-script" if requires_model else "local-python"
    representation = profile.representation if profile else "sdk_standardized" if requires_model else "local"
    if profile and (not profile.config_ready or profile.requires_key and not key):
        raise HTTPException(400, "真实模式需要已配置的模型、服务地址和所选服务商 API Key；本地 Ollama 无需 Key。")
    if not run_lock.acquire(blocking=False):
        raise HTTPException(409, "上一次运行尚未结束，请等待网络请求返回（网络超时 60 秒）。")
    events = queue.Queue()
    cancelled = threading.Event()
    started = time.perf_counter()
    secrets = provider_registry.secrets(session_key)

    def emit(kind, data, round_number=None):
        event = {"schema_version": 1, "type": kind, "round": round_number,
                 "timestamp": datetime.now(timezone.utc).isoformat(), "data": data}
        # 序列化即时形成不可变快照，后续追加消息不会改变先前请求。
        events.put(json.dumps(scrub(event, secrets), ensure_ascii=False))

    def work():
        final_status = "completed"
        try:
            emit("run_start", {"lesson_id": body.lesson_id, "mode": body.mode, "model": model,
                               "question": body.question, "inputs": inputs,
                               "runtime_kind": spec["runtime"]["kind"],
                               "provider_id": profile.id if profile else "testing" if requires_model else "local",
                               "provider_label": profile.label if profile else "确定性测试" if requires_model else "本地 Python",
                               "trace_representation": representation})
            completion = (completion_for(spec, body.exercise_id, inputs) if body.mode == "offline" and requires_model
                          else send_bailian if profile and profile.id == "bailian"
                          else SDKCompletion(profile) if profile else None)
            context = RunContext(
                lesson_id=body.lesson_id, exercise_id=body.exercise_id, question=body.question,
                mode=body.mode, model=model, representation=representation, inputs=inputs,
                api_key=key, completion=completion, emit_event=emit, cancelled=cancelled.is_set,
                max_model_calls=spec["runtime"].get("max_rounds", 3),
            )
            execute_lesson(spec, module, context)
        except RunCancelled:
            final_status = "cancelled"
        except Exception as error:
            final_status = "error"
            emit("error", {"message": str(error), "error_type": type(error).__name__})
        finally:
            emit("done", {"status": final_status, "duration_ms": round((time.perf_counter()-started)*1000)})
            run_lock.release()

    worker = threading.Thread(target=work, name="agent-course-run", daemon=True)
    worker.start()

    async def stream():
        heartbeat = time.monotonic()
        try:
            while True:
                if await request.is_disconnected():
                    break
                try:
                    event = events.get_nowait()
                except queue.Empty:
                    if time.monotonic() - heartbeat > 10:
                        yield ": waiting\n\n"
                        heartbeat = time.monotonic()
                    await asyncio.sleep(0.05)
                    continue
                yield "data: " + event + "\n\n"
                if json.loads(event)["type"] == "done":
                    break
        finally:
            cancelled.set()

    return StreamingResponse(stream(), media_type="text/event-stream", headers={"X-Accel-Buffering": "no"})


# 前端先构建；只公开 dist，不暴露项目、配置或 Python 文件目录。
dist = ROOT / "frontend" / "dist"
if dist.is_dir():
    app.mount("/", StaticFiles(directory=dist, html=True), name="frontend")
else:
    @app.get("/")
    def frontend_pending():
        return JSONResponse({"detail": "请先在 frontend 目录执行 npm install 和 npm run build。"}, status_code=503)
