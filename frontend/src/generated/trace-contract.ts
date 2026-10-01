// 此文件由 scripts/export_trace_contract.py 从 server/envelope.py 生成，请勿手改。
// 修改后端常量表后运行：python scripts/export_trace_contract.py
export const TRACE_CONTRACT = {
  "schema_version": 2,
  "provenances": [
    "real_run",
    "recorded_run",
    "offline_recompute",
    "illustration"
  ],
  "representations": [
    "wire",
    "parsed",
    "sdk_standardized",
    "http_body"
  ],
  "span_kinds": [
    "run",
    "agent",
    "step",
    "llm",
    "tool"
  ],
  "default_actor": "agent",
  "span_events": {
    "run_start": {
      "phase": "start",
      "span_kind": "run",
      "closed_by": "done"
    },
    "done": {
      "phase": "end",
      "span_kind": "run",
      "opened_by": "run_start"
    },
    "request": {
      "phase": "start",
      "span_kind": "llm",
      "closed_by": "response",
      "model_payload": true
    },
    "response": {
      "phase": "end",
      "span_kind": "llm",
      "opened_by": "request",
      "model_payload": true
    },
    "tool_call": {
      "phase": "start",
      "span_kind": "tool",
      "closed_by": "tool_result",
      "pair_field": "id"
    },
    "tool_result": {
      "phase": "end",
      "span_kind": "tool",
      "opened_by": "tool_call",
      "pair_field": "tool_call_id"
    },
    "answer": {
      "phase": "instant"
    },
    "error": {
      "phase": "instant"
    }
  },
  "instant_prefixes": [
    "lesson."
  ],
  "step_span": {
    "span_kind": "step",
    "derived_from": "round",
    "parent": "run"
  }
} as const;
