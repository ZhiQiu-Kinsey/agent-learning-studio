"""手动实测默认 HTTP 与 LiteLLM 接入同一既有百炼服务；会产生模型用量。"""
import json
import os
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def request(path, payload=None):
    req = urllib.request.Request("http://127.0.0.1:8765" + path,
                                 data=None if payload is None else json.dumps(payload).encode("utf-8"),
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=180) as response:
        return response.read().decode("utf-8")


def main():
    from local_config import API_URL, MODEL
    key = os.environ.get("DASHSCOPE_API_KEY", "")
    if not key:
        raise SystemExit("DASHSCOPE_API_KEY is required; no model request sent.")
    active = json.loads(request("/api/providers"))["active_provider"]
    results = []
    try:
        for provider_id in ("bailian", "custom"):
            settings = {"provider_id": provider_id}
            if provider_id == "custom":
                settings.update(model=MODEL, api_base=API_URL, api_key=key)
            request("/api/settings", settings)
            created = json.loads(request("/api/runs", {"lesson_id": "1", "mode": "live", "exercise_id": "sum",
                                                       "question": "帮我计算 19 加 23，并说明结果。"}))
            stream = request(f"/api/runs/{created['run_id']}/events")
            events = [json.loads(line[6:]) for line in stream.splitlines() if line.startswith("data: ")]
            terminal = next((event for event in events if event["type"] == "done"), None)
            tool = next((event for event in events if event["type"] == "tool_result"), None)
            representations = sorted({event["data"].get("representation", "missing")
                                      for event in events if event["type"] in ("request", "response")})
            envelope = sorted({event.get("representation") or "missing"
                               for event in events if event["type"] in ("request", "response")})
            result = {"provider_id": provider_id, "model": MODEL,
                      "status": terminal["data"]["status"] if terminal else "missing",
                      "representations": representations,
                      "requests": sum(event["type"] == "request" for event in events),
                      "tool_result": tool["data"]["result"] if tool else None,
                      "answer": next((event["data"]["content"] for event in events if event["type"] == "answer"), None),
                      "duration_ms": terminal["data"]["duration_ms"] if terminal else None,
                      "usage": [event["data"]["body"].get("usage") for event in events if event["type"] == "response"],
                      "errors": [event["data"]["message"] for event in events if event["type"] == "error"]}
            expected = "http_body" if provider_id == "bailian" else "sdk_standardized"
            result["passed"] = (result["status"] == "completed" and result["tool_result"] == {"ok": True, "result": 42}
                                and result["representations"] == [expected] and envelope == [expected])
            results.append(result)
            # 只保存和打印白名单字段；原始请求头、配置值不进入记录。
            print(json.dumps(result, ensure_ascii=False, indent=2))
    finally:
        request("/api/settings", {"provider_id": active})
    (ROOT / ".runtime").mkdir(exist_ok=True)
    (ROOT / ".runtime/provider-live-verification.json").write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    if not all(item["passed"] for item in results):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
