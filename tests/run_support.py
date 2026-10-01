"""测试公用：把运行存储换到临时目录，并通过 runs 接口完整执行一次运行。

自动化测试从不写入真实的 .runtime/；每个用例结束时关闭并删除临时数据库。
"""
import importlib
import json
import tempfile
from pathlib import Path
from types import SimpleNamespace

from server.run_store import RunStore

web = importlib.import_module("server.app")


def use_temporary_run_store(testcase) -> RunStore:
    directory = tempfile.TemporaryDirectory()
    testcase.addCleanup(directory.cleanup)
    previous = web.run_store
    store = RunStore(Path(directory.name) / "runs.sqlite3")

    def restore():
        web.run_store = previous
        store.close()

    testcase.addCleanup(restore)
    web.run_store = store
    return store


def sse_events(text: str) -> list[dict]:
    return [json.loads(line[6:]) for line in text.splitlines() if line.startswith("data: ")]


def run_and_read(client, body, from_seq=None):
    """POST /api/runs 后读取事件流直到 done；失败时 events 为空，text 为错误响应。"""
    created = client.post("/api/runs", json=body)
    if created.status_code != 202:
        return SimpleNamespace(status_code=created.status_code, text=created.text, events=[], run_id=None)
    run_id = created.json()["run_id"]
    url = f"/api/runs/{run_id}/events" + (f"?from_seq={from_seq}" if from_seq else "")
    stream = client.get(url)
    return SimpleNamespace(status_code=created.status_code, text=stream.text, events=sse_events(stream.text),
                           run_id=run_id)
