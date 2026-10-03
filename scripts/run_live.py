"""用真实模型运行一门课的一个或全部练习，打印事件摘要；会产生模型用量。

用法：python scripts/run_live.py <课程 slug> [练习 id ...] [--url http://127.0.0.1:8765] [--offline] [--json]
需要先启动后端（run_web.py 或 uvicorn），后端从自己的环境读取密钥；本脚本不读取、不打印密钥。
摘要只含事件类型、请求数、用量、回答、报告检查与错误，便于核对正文说法与真实运行是否一致。
"""
import argparse
import json
import os
import sys
import urllib.error
import urllib.request


def call(base, path, payload=None, timeout=300):
    request = urllib.request.Request(base + path,
                                     data=None if payload is None else json.dumps(payload).encode("utf-8"),
                                     headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return response.read().decode("utf-8")


def summarize(events):
    by_type = {}
    for event in events:
        by_type[event["type"]] = by_type.get(event["type"], 0) + 1
    responses = [event["data"].get("body", {}) for event in events if event["type"] == "response"]
    reports = [event["data"] for event in events if event["type"] == "lesson.report"]
    done = next((event["data"] for event in events if event["type"] == "done"), {})
    return {
        "status": done.get("status"),
        "events": by_type,
        "finish_reasons": [(body.get("choices") or [{}])[0].get("finish_reason") for body in responses],
        "usage": [body.get("usage") for body in responses],
        "answer": next((event["data"].get("content") for event in events if event["type"] == "answer"), None),
        "reports": [{"title": report.get("title"),
                     "checks": [(check.get("label"), check.get("passed")) for check in report.get("checks", [])],
                     "metrics": [(metric.get("label"), metric.get("value")) for metric in report.get("metrics", [])]}
                    for report in reports],
        "errors": [event["data"].get("message") for event in events if event["type"] == "error"],
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("lesson")
    parser.add_argument("exercises", nargs="*")
    parser.add_argument("--url", default=os.environ.get("AGENT_LAB_URL", "http://127.0.0.1:8765"))
    parser.add_argument("--offline", action="store_true", help="用离线测试模式运行（不调用模型）")
    parser.add_argument("--json", action="store_true", help="同时打印完整事件 JSON")
    args = parser.parse_args(argv)
    base = args.url.rstrip("/")
    detail = json.loads(call(base, f"/api/lessons/{args.lesson}"))
    exercises = [item for item in detail["exercises"] if not args.exercises or item["id"] in args.exercises]
    if not exercises:
        raise SystemExit("没有匹配的练习。")
    failed = False
    for exercise in exercises:
        if exercise.get("offline_only") and not args.offline:
            # 故障注入练习只在离线模式运行，服务端会拒绝真实运行；跳过并写明，不中断其余练习。
            print(json.dumps({"lesson": detail["id"], "exercise": exercise["id"], "status": "skipped",
                              "reason": "offline_only：故障注入练习只在离线模式运行"}, ensure_ascii=False, indent=2))
            continue
        payload = {"lesson_id": detail["id"], "mode": "offline" if args.offline else "live",
                   "question": exercise["question"], "exercise_id": exercise["id"]}
        if exercise.get("inputs"):
            payload["inputs"] = exercise["inputs"]
        try:
            created = json.loads(call(base, "/api/runs", payload))
        except urllib.error.HTTPError as error:
            # 服务端拒绝创建运行（如配置不全）：记为失败，继续下一个练习。
            failed = True
            print(json.dumps({"lesson": detail["id"], "exercise": exercise["id"], "status": "rejected",
                              "http_status": error.code, "body": error.read().decode("utf-8", "replace")[:300]},
                             ensure_ascii=False, indent=2))
            continue
        stream = call(base, f"/api/runs/{created['run_id']}/events")
        events = [json.loads(line[6:]) for line in stream.splitlines() if line.startswith("data: ")]
        summary = {"lesson": detail["id"], "exercise": exercise["id"], "run_id": created["run_id"], **summarize(events)}
        failed = failed or summary["status"] != "completed"
        print(json.dumps(summary, ensure_ascii=False, indent=2))
        if args.json:
            print(json.dumps(events, ensure_ascii=False, indent=2))
    return 1 if failed else 0


if __name__ == "__main__":
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
    raise SystemExit(main())
