"""测试用 A2A 被委派方：在 127.0.0.1 的空闲端口上提供 Agent Card 与 JSON-RPC 接口，第一行输出 "PORT <n>"。

只由 tests/test_protocols.py 通过 `python -m tests.fixtures.a2a_demo_worker` 启动。
"""
import socket

import uvicorn
from a2a.helpers import get_message_text, new_task_from_user_message, new_text_message, new_text_part
from a2a.server.agent_execution import AgentExecutor, RequestContext
from a2a.server.events import EventQueue
from a2a.server.request_handlers import DefaultRequestHandler
from a2a.server.routes import create_agent_card_routes, create_jsonrpc_routes
from a2a.server.tasks import InMemoryTaskStore, TaskUpdater
from a2a.types import AgentCapabilities, AgentCard, AgentInterface, AgentSkill, TaskState
from starlette.applications import Starlette


class FirstWords(AgentExecutor):
    """确定性的“摘要”：保留前三个词；以 fail 开头的任务进入 FAILED 状态。"""

    async def execute(self, context: RequestContext, event_queue: EventQueue) -> None:
        task = context.current_task or new_task_from_user_message(context.message)
        if not context.current_task:
            await event_queue.enqueue_event(task)
        updater = TaskUpdater(event_queue=event_queue, task_id=task.id, context_id=task.context_id)
        await updater.update_status(state=TaskState.TASK_STATE_WORKING)
        text = get_message_text(context.message) or ""
        if text.startswith("fail"):
            await updater.update_status(state=TaskState.TASK_STATE_FAILED, message=new_text_message("refused"))
            return
        await updater.add_artifact(parts=[new_text_part(text=" ".join(text.split()[:3]))], name="summary")
        await updater.update_status(state=TaskState.TASK_STATE_COMPLETED)

    async def cancel(self, context: RequestContext, event_queue: EventQueue) -> None:
        updater = TaskUpdater(event_queue=event_queue, task_id=context.task_id, context_id=context.context_id)
        await updater.update_status(state=TaskState.TASK_STATE_CANCELED)


def main():
    # 先 listen 再报端口：uvicorn 启动前到达的连接在积压队列里等待，而不是被拒绝（CI 较慢时会遇到）。
    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    sock.listen(64)
    url =f"http://127.0.0.1:{sock.getsockname()[1]}"
    card = AgentCard(
        name="first-words-worker", description="Keeps the first three words.", version="0.1.0",
        default_input_modes=["text/plain"], default_output_modes=["text/plain"],
        capabilities=AgentCapabilities(streaming=True),
        supported_interfaces=[AgentInterface(protocol_binding="JSONRPC", url=url, protocol_version="1.0")],
        skills=[AgentSkill(id="first-words", name="First words", description="Keep the first three words.",
                           tags=["text"])],
    )
    handler = DefaultRequestHandler(agent_executor=FirstWords(), task_store=InMemoryTaskStore(), agent_card=card)
    app = Starlette(routes=[*create_agent_card_routes(card), *create_jsonrpc_routes(handler, "/")])
    print(f"PORT {sock.getsockname()[1]}", flush=True)
    uvicorn.Server(uvicorn.Config(app, log_level="warning")).run(sockets=[sock])


if __name__ == "__main__":
    main()
