import { useEffect, useMemo, useState } from "react";
import { animate, motion, useMotionValue, useTransform } from "motion/react";
import { useTranslation } from "react-i18next";
import { useMotion } from "../motion";
import { duration, ease } from "../motion/tokens";
import type { Trace } from "../types";
import { deriveStage, type StageNode, type StageSpan } from "./derive";
import "../styles/stage.css";

type Point = { x: number; y: number };

/** Positions in percent of the stage box; topology itself comes from the events. */
function layout(nodes: StageNode[]): Map<string, Point> {
  const tools = nodes.filter((node) => node.role === "tool");
  const places = new Map<string, Point>([
    ["user", { x: 9, y: 50 }],
    ["runtime", { x: 38, y: 50 }],
    ["model", { x: 74, y: 17 }],
    ["memory", { x: 38, y: 87 }],
  ]);
  tools.forEach((node, index) =>
    places.set(node.id, { x: 74, y: 44 + ((index + 0.5) * 46) / tools.length }),
  );
  return places;
}

/** Quadratic curve between two nodes; opposite directions bow to opposite sides. */
function curve(from: Point, to: Point) {
  const mx = (from.x + to.x) / 2;
  const my = (from.y + to.y) / 2;
  const dx = to.x - from.x;
  const dy = to.y - from.y;
  const length = Math.hypot(dx, dy) || 1;
  const bow = 5;
  const control = { x: mx - (dy / length) * bow, y: my + (dx / length) * bow };
  return {
    d: `M ${from.x} ${from.y} Q ${control.x} ${control.y} ${to.x} ${to.y}`,
    at: (t: number) => ({
      x: (1 - t) ** 2 * from.x + 2 * (1 - t) * t * control.x + t ** 2 * to.x,
      y: (1 - t) ** 2 * from.y + 2 * (1 - t) * t * control.y + t ** 2 * to.y,
    }),
  };
}

/** One dot travels the edge once per real event; reduced motion shows the lit edge only. */
function SignalDot({ at }: { at: (t: number) => Point }) {
  const progress = useMotionValue(0);
  const left = useTransform(progress, (t) => `${at(t).x}%`);
  const top = useTransform(progress, (t) => `${at(t).y}%`);
  useEffect(() => {
    const controls = animate(progress, 1, {
      duration: duration.slow * 1.4,
      ease,
    });
    return () => controls.stop();
  }, [progress]);
  return (
    <motion.span
      className="stage-signal"
      style={{ left, top }}
      aria-hidden="true"
    />
  );
}

function useSeconds(startAt: string | null) {
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    if (!startAt) return;
    const timer = window.setInterval(() => setNow(Date.now()), 100);
    return () => window.clearInterval(timer);
  }, [startAt]);
  return startAt ? Math.max(0, now - Date.parse(startAt)) / 1000 : 0;
}

export function AgentStage({
  events,
  cursor,
  live,
  recording,
  spotlight,
}: {
  events: readonly Trace[];
  cursor: number;
  /** True while this run is still streaming and the cursor is at its end. */
  live: boolean;
  recording?: { model: string; date: string };
  /** Node role a guided replay points at; other nodes recede. */
  spotlight?: string | null;
}) {
  const { t, i18n } = useTranslation(["stage", "common"]);
  const { reduced } = useMotion();
  const stage = useMemo(() => deriveStage(events, cursor), [events, cursor]);
  const final = useMemo(() => deriveStage(events, events.length), [events]);
  const places = layout(stage.nodes);
  const seconds = new Intl.NumberFormat(i18n.language, {
    minimumFractionDigits: 1,
    maximumFractionDigits: 1,
  });

  const openLlm = stage.spans.find(
    (span) => span.kind === "llm" && span.status === "open",
  );
  const liveSeconds = useSeconds(live && openLlm ? openLlm.startAt : null);
  const finalOf = (span: StageSpan | undefined) =>
    span &&
    final.spans.find(
      (item) => item.id === span.id && item.startIndex === span.startIndex,
    );

  const illustration = stage.provenance === "illustration";
  const badge = illustration
    ? t("common:provenance.illustration")
    : stage.provenance === "recorded_run" && recording
      ? t("provenance.recorded_run", recording)
      : t(
          `provenance.${stage.provenance === "real_run" ? "real_run" : "unknown"}`,
        );

  if (!events.length)
    return (
      <section
        className="agent-stage is-empty"
        aria-label={t("region")}
        data-testid="agent-stage"
      >
        <p>{t("empty")}</p>
      </section>
    );

  return (
    <section
      className="agent-stage"
      aria-label={t("region")}
      data-testid="agent-stage"
      data-provenance={stage.provenance}
      data-status={stage.status}
      data-spotlight={spotlight || undefined}
    >
      <header className="stage-header">
        <span className="stage-provenance" data-provenance={stage.provenance}>
          {badge}
        </span>
        <span className="stage-status" role="status">
          {t(`status.${stage.status}`)}
        </span>
      </header>
      <div className="stage-canvas">
        <svg
          className="stage-edges"
          viewBox="0 0 100 100"
          preserveAspectRatio="none"
          aria-hidden="true"
        >
          {stage.edges.map((edge) => {
            const from = places.get(edge.from);
            const to = places.get(edge.to);
            if (!from || !to) return null;
            return (
              <path
                key={edge.id}
                d={curve(from, to).d}
                className={`stage-edge ${stage.signal?.edge === edge.id ? "is-lit" : ""}`}
                data-target-role={edge.to.split(":")[0]}
                vectorEffect="non-scaling-stroke"
              />
            );
          })}
        </svg>
        {!reduced &&
          stage.signal &&
          (() => {
            const edge = stage.edges.find(
              (item) => item.id === stage.signal!.edge,
            );
            const from = edge && places.get(edge.from);
            const to = edge && places.get(edge.to);
            return from && to ? (
              <SignalDot
                key={stage.signal.eventIndex}
                at={curve(from, to).at}
              />
            ) : null;
          })()}
        {stage.nodes.map((node) => {
          const place = places.get(node.id)!;
          const waiting = node.id === "model" && node.state === "waiting";
          const waited = waiting && !live ? finalOf(openLlm)?.durationMs : null;
          return (
            <div
              key={node.id}
              className="stage-node"
              data-role={node.role}
              data-state={node.state}
              data-spotlit={
                spotlight && node.role === spotlight ? true : undefined
              }
              data-testid={`stage-node-${node.id}`}
              style={{ left: `${place.x}%`, top: `${place.y}%` }}
            >
              <strong>
                {node.role === "tool" ? node.name : t(`role.${node.role}`)}
              </strong>
              {node.role === "tool" && (
                <small className="stage-node-kind">{t("role.tool")}</small>
              )}
              {waiting ? (
                <span className="stage-waiting">
                  <i aria-hidden="true" />
                  <i aria-hidden="true" />
                  <i aria-hidden="true" />
                  <span>
                    {live
                      ? t("waiting", { seconds: seconds.format(liveSeconds) })
                      : waited != null
                        ? t("waited", {
                            seconds: seconds.format(waited / 1000),
                          })
                        : t("state.waiting")}
                  </span>
                </span>
              ) : (
                <small>{t(`state.${node.state}`)}</small>
              )}
            </div>
          );
        })}
        {illustration && (
          <span className="stage-watermark" aria-hidden="true">
            {t("common:provenance.illustration")}
          </span>
        )}
      </div>
    </section>
  );
}
