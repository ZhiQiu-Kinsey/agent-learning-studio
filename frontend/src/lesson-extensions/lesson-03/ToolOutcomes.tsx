import { CheckCircle2, CircleHelp, ShieldAlert } from "lucide-react";
import type { InspectorExtensionProps } from "../types";
import "./tool-outcomes.css";

/** This view reads visible events only: rewind also rewinds the outcome counts. */
export default function ToolOutcomes({
  studio,
  children,
}: InspectorExtensionProps) {
  const outcomes = studio.visible
    .map((event, index) => ({ event, index }))
    .filter(({ event }) => event.type === "tool_result")
    .map(({ event, index }) => {
      const result = event.data.result;
      const ok =
        result && typeof result === "object" && "ok" in result
          ? result.ok
          : undefined;
      return { index, name: String(event.data.name || "Python 工具"), ok };
    });
  const passed = outcomes.filter((item) => item.ok === true).length;
  const failed = outcomes.filter((item) => item.ok === false).length;
  const unknown = outcomes.length - passed - failed;
  return (
    <>
      {children}
      <section className="tool-outcomes" aria-label="工具安全边界观察">
        <div className="tool-outcomes-heading">
          <strong>工具结果与安全边界</strong>
          <small>来自当前回放位置的真实工具结果</small>
        </div>
        <div className="tool-outcome-counts" aria-live="polite">
          <span>
            <CheckCircle2 size={14} />
            通过 {passed}
          </span>
          <span>
            <ShieldAlert size={14} />
            失败 {failed}
          </span>
          {unknown > 0 && (
            <span>
              <CircleHelp size={14} />
              未声明状态 {unknown}
            </span>
          )}
        </div>
        {outcomes.length ? (
          <div className="tool-outcome-links">
            {outcomes.map(({ index, name, ok }) => (
              <button
                key={index}
                type="button"
                data-outcome={
                  ok === true ? "passed" : ok === false ? "failed" : "unknown"
                }
                aria-label={`定位工具结果 ${index + 1}：${name}`}
                aria-pressed={studio.active === studio.visible[index]}
                onClick={() => studio.selectEvent(index)}
              >
                <span>{name}</span>
                <span>
                  {ok === true ? "通过" : ok === false ? "失败" : "未声明状态"}{" "}
                  · 事件 {index + 1}
                </span>
              </button>
            ))}
          </div>
        ) : (
          <p>
            当前还没有工具结果。运行或向前回放，观察哪些请求被接受、哪些被工具拒绝。
          </p>
        )}
      </section>
    </>
  );
}
