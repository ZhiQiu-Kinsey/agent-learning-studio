import { useEffect, useId, useMemo, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { motion } from "motion/react";
import { useReducedMotion } from "../../motion";

/** Selection pill glides between events; a snappy spring, no overshoot. */
const PILL_SPRING = {
  type: "spring",
  stiffness: 520,
  damping: 40,
  mass: 0.8,
} as const;
import BorderGlow from "../react-bits/BorderGlow";
import CountUp from "../react-bits/CountUp";
import TextType from "../react-bits/TextType";
import StatusMark from "../react-bits/StatusMark";
import CallChip, { type CallChipStatus } from "../react-bits/CallChip";
import LatticeLoader from "../react-bits/LatticeLoader";
import PromptBar from "../react-bits/PromptBar";
import { AgentStage } from "../../stage/AgentStage";
import { ContextFilm } from "../../stage/ContextFilm";
import { Timeline } from "../../stage/Timeline";
import { ToolCards, summarize } from "../../stage/ToolCards";
import { deriveStage, type StageSpan } from "../../stage/derive";
import { useElapsedMs } from "../../stage/useElapsed";
import { Lenses } from "../../stage/Lenses";
import RubberSegment from "../react-bits/RubberSegment";
import { LessonExtension } from "../../lesson-extensions/LessonExtension";
import {
  ArrowRight,
  Check,
  Code2,
  Copy,
  Download,
  FlaskConical,
  MessageSquare,
  Pause,
  Play,
  RotateCcw,
  SkipForward,
  Terminal,
  Waypoints,
} from "lucide-react";
import type { StudioState } from "../../hooks/useStudio";
import type { Trace } from "../../types";
import { Button } from "../ui/button";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "../ui/tabs";
import GlideSelect from "../react-bits/GlideSelect";
import WakeSlider from "../react-bits/WakeSlider";
import ThoughtLine from "../react-bits/ThoughtLine";
import { Code } from "../Code";
import { Answer } from "../Answer";

const names: Record<string, string> = {
  run_start: "开始运行",
  request: "发送请求",
  response: "模型响应",
  tool_call: "请求调用工具",
  tool_result: "Python 执行结果",
  answer: "最终回答",
  error: "运行错误",
  done: "运行结束",
};
function label(e: Trace) {
  if (e.type === "tool_call" && e.data.origin === "course_program")
    return "程序调用工具";
  return e.data.representation === "sdk_standardized" &&
    ["request", "response"].includes(e.type)
    ? e.type === "request"
      ? "标准化请求"
      : "标准化响应"
    : names[e.type] ||
        (typeof e.data.title === "string" ? e.data.title : e.type);
}
function summary(e: Trace) {
  if (e.type === "tool_call") {
    const fn = e.data.function as
      { name?: string; arguments?: string } | undefined;
    return fn
      ? `${fn.name}(${fn.arguments || ""})`
      : String(e.data.name || "工具调用");
  }
  if (e.type === "tool_result")
    return `${e.data.name || "工具"} · ${(e.data.result as { ok?: boolean })?.ok === false ? "返回错误" : "执行完成"}`;
  if (e.type === "request") return `第 ${e.round || 1} 轮 · messages + tools`;
  if (e.type === "response")
    return typeof e.data.duration_ms === "number"
      ? `${(e.data.duration_ms / 1000).toFixed(2)} 秒`
      : "响应已收到";
  if (e.type === "answer") return String(e.data.content || "");
  if (e.type === "error") return String(e.data.message || "查看错误详情");
  if (e.type === "done") return String(e.data.status || "已结束");
  if (e.type === "run_start") return "准备运行环境";
  return typeof e.data.summary === "string"
    ? e.data.summary
    : typeof e.data.title === "string"
      ? e.data.title
      : "自定义课程事件 · 点击查看完整数据";
}
const pickerColors = {
  surfaceColor: "var(--surface)",
  textColor: "var(--text)",
  accentColor: "var(--accent)",
  highlightColor: "var(--surface-muted)",
};

function RunMetric({ value }: { value: number }) {
  const reduced = useReducedMotion();
  const previous = useRef(value);
  useEffect(() => {
    previous.current = value;
  }, [value]);
  return (
    <b>
      <span className="sr-only">{value}</span>
      <span aria-hidden="true">
        {reduced ? (
          value
        ) : (
          <CountUp
            key={value}
            from={previous.current}
            to={value}
            duration={0.35}
          />
        )}
      </span>
    </b>
  );
}

/**
 * The run's activity line. While a model request is open (request sent, no
 * response yet) it says "waiting for the model response" with the real time
 * since that request's server timestamp; otherwise it names the latest event.
 */
function RunActivity({
  openLlm,
  last,
}: {
  openLlm: StageSpan | undefined;
  last: Trace | undefined;
}) {
  const { t, i18n } = useTranslation("lab", { keyPrefix: "bench.wait" });
  const elapsed = useElapsedMs(openLlm?.startAt);
  if (openLlm)
    return (
      <div className="trace-activity is-waiting" data-testid="lab-model-wait">
        <ThoughtLine
          label={`${t("model")} · ${t("round", { round: openLlm.round ?? 1 })}`}
          working
          glyph={
            <LatticeLoader
              pattern="orbit"
              cellSize={4}
              gap={1.5}
              color="var(--role-model)"
              className="trace-activity-lattice"
            />
          }
          elapsed={elapsed == null ? undefined : elapsed / 1000}
          showTimer={elapsed != null}
          collapsible={false}
          color="var(--text)"
          fontSize={13}
        />
        <span className="sr-only">
          {elapsed != null &&
            t("seconds", {
              value: new Intl.NumberFormat(i18n.language, {
                maximumFractionDigits: 0,
              }).format(elapsed / 1000),
            })}
        </span>
      </div>
    );
  return (
    <div className="trace-activity">
      <ThoughtLine
        label={
          last
            ? `${label(last)} · ${summary(last).slice(0, 50)}`
            : t("connecting")
        }
        working
        showTimer={false}
        glyph="dot"
        collapsible={false}
        color="var(--text-muted)"
        glyphColor="var(--accent)"
        fontSize={13}
      />
    </div>
  );
}

/** One chip per real tool call at the cursor; times come from server timestamps. */
function ToolCallChips({
  spans,
  events,
  live,
  activeIndex,
  onSelect,
}: {
  spans: StageSpan[];
  events: readonly Trace[];
  live: boolean;
  activeIndex: number;
  onSelect: (index: number) => void;
}) {
  const { t, i18n } = useTranslation("lab", { keyPrefix: "bench.calls" });
  const tools = spans.filter((span) => span.kind === "tool");
  if (!tools.length) return null;
  const number = new Intl.NumberFormat(i18n.language, {
    maximumFractionDigits: 1,
  });
  const formatMs = (ms: number) =>
    ms < 1000
      ? t("ms", { value: number.format(Math.round(ms)) })
      : t("s", { value: number.format(ms / 1000) });
  return (
    <ul
      className="tool-call-chips"
      aria-label={t("region")}
      data-testid="lab-call-chips"
    >
      {tools.map((span) => {
        const call = events[span.startIndex];
        const { name, args } = summarize(call, undefined, 28);
        const status: CallChipStatus =
          span.status === "stopped"
            ? "stopped"
            : span.status === "open"
              ? "running"
              : span.ok === false
                ? "error"
                : span.ok === true
                  ? "done"
                  : "unknown";
        // Only a call that is open right now ticks; a replayed open call shows no time.
        const startAt = status === "running" && live ? span.startAt : null;
        const time =
          span.durationMs != null ? formatMs(span.durationMs) : t("noTime");
        const target = span.endIndex ?? span.startIndex;
        return (
          <li key={`${span.id}-${span.startIndex}`}>
            <CallChip
              name={name}
              argument={args}
              status={status}
              startAt={startAt}
              durationMs={status === "running" ? null : span.durationMs}
              formatMs={formatMs}
              statusLabel={
                status === "running"
                  ? t("running", { name })
                  : status === "stopped"
                    ? t("stopped", { name })
                    : t(status === "unknown" ? "undeclared" : status, {
                        name,
                        time,
                      })
              }
              pressed={
                activeIndex >= span.startIndex &&
                activeIndex <= (span.endIndex ?? span.startIndex)
              }
              onClick={() => onSelect(target)}
              data-testid="lab-call-chip"
            />
          </li>
        );
      })}
    </ul>
  );
}

export function Laboratory({
  studio: s,
  onConfigure,
  active,
  spotlight,
}: {
  studio: StudioState;
  onConfigure: () => void;
  active: boolean;
  /** Stage node role highlighted by a guided replay. */
  spotlight?: string | null;
}) {
  const reducedMotion = useReducedMotion();
  const { t } = useTranslation("stage");
  const { t: tb } = useTranslation("lab", { keyPrefix: "bench" });
  const pillId = useId();
  const [tab, setTab] = useState("trace");
  // One projection of the real events feeds the stage, film, cards and timeline.
  const stage = useMemo(
    () => deriveStage(s.events, s.cursor),
    [s.events, s.cursor],
  );
  const finalSpans = useMemo(
    () => deriveStage(s.events, s.events.length).spans,
    [s.events],
  );
  const pacing =
    s.replayOptions.pacing === "uniform"
      ? "uniform"
      : s.replayOptions.speed === 2
        ? "real2"
        : "real1";
  const [copied, setCopied] = useState(false);
  const list = useRef<HTMLDivElement>(null);
  const last = s.events.at(-1);
  const completed = last?.type === "done" && last.data.status === "completed";
  const ready = s.canRun;
  const live = s.running && s.cursor === s.events.length;
  const openLlm = live
    ? stage.spans.find((span) => span.kind === "llm" && span.status === "open")
    : undefined;
  const needsConnection =
    s.requiresModel &&
    !(
      s.status?.config_ready &&
      (s.status.requires_api_key === false || s.status.api_key_configured)
    );
  const activeBody = s.active
    ? ["request", "response"].includes(s.active.type)
      ? s.active.data.body
      : s.active.data
    : null;
  const activeIndex = s.active ? s.visible.indexOf(s.active) : -1;
  const file = s.detail?.sources[s.source];
  const requests = s.visible.filter((e: Trace) => e.type === "request").length;
  const tools = s.visible.filter((e: Trace) => e.type === "tool_call").length;
  const exercises = useMemo(
    () => s.detail?.exercises.filter((e) => !e.offline_only) ?? [],
    [s.detail],
  );
  const canSend =
    !!s.detail &&
    ready &&
    (!!s.question.trim() || !!s.detail.capabilities?.supports_inputs);
  useEffect(() => {
    if (s.running && list.current)
      list.current.scrollTop = list.current.scrollHeight;
  }, [s.events.length, s.running]);
  useEffect(() => {
    if (s.running) setTab("trace");
  }, [s.running]);
  useEffect(() => {
    setCopied(false);
  }, [s.active]);
  return (
    <BorderGlow
      className="lab-border-glow"
      backgroundColor="var(--surface)"
      borderRadius={18}
      edgeSensitivity={20}
      glowColor="250 80% 72%"
      glowRadius={8}
      glowIntensity={reducedMotion ? 0 : 0.95}
      colors={["#9781ed", "#65b6d3", "#b39af0"]}
      fillOpacity={0.035}
      animated={active && !reducedMotion}
    >
      <div
        className="lab-workspace"
        data-testid="lab-workspace"
        data-running={s.running || undefined}
      >
        <div className="lab-command-column">
          <section className="lab-composer">
            <div className="pane-heading">
              <span>
                <FlaskConical size={17} />
                {tb("composer.title")}
              </span>
              <small>LIVE</small>
            </div>
            <p className="pane-description">
              {s.requiresModel
                ? s.detail?.capabilities?.custom_runtime
                  ? tb("composer.descCustom")
                  : tb("composer.descModel")
                : tb("composer.descLocal")}
            </p>
            <div className="form-field" data-testid="lab-exercise-field">
              <label>{tb("composer.exercise")}</label>
              <GlideSelect
                {...pickerColors}
                size="lg"
                className="full-picker"
                ariaLabel={tb("composer.exercise")}
                value={s.exerciseId}
                onChange={s.selectExercise}
                disabled={s.running || !s.detail}
                options={exercises.map((e) => ({
                  value: e.id,
                  label: e.title,
                }))}
              />
            </div>
            <div className="form-field">
              <label htmlFor="lab-question">
                {s.detail?.ui?.question_label || tb("composer.question")}
              </label>
              <PromptBar
                className="lab-prompt-bar"
                value={s.question}
                onChange={s.setQuestion}
                disabled={s.running}
                busy={s.running}
                canSend={canSend}
                onSend={() => {
                  setTab("trace");
                  void s.run();
                }}
                onStop={s.cancel}
                commands={exercises.map((e) => ({
                  key: e.id,
                  name: e.title,
                  description: e.question,
                  active: e.id === s.exerciseId,
                }))}
                onCommand={s.selectExercise}
                placeholder={tb("composer.placeholder")}
                labels={{
                  send: tb("composer.run"),
                  sendText: tb("composer.runShort"),
                  stop: tb("composer.stop"),
                  stopText: tb("composer.stopShort"),
                  commands: tb("composer.commands"),
                  openCommands: tb("composer.openCommands"),
                  noMatch: tb("composer.noMatch"),
                }}
                hint={tb("composer.hint")}
                sendTestId="lab-run-button"
                stopTestId="lab-stop-button"
                textareaProps={{
                  id: "lab-question",
                  "data-testid": "lab-question-input",
                  "aria-describedby": s.detail?.ui?.question_help
                    ? "lab-question-help"
                    : undefined,
                }}
              />
              {s.detail?.ui?.question_help && (
                <p id="lab-question-help" className="composer-note">
                  {s.detail.ui.question_help}
                </p>
              )}
            </div>
            {needsConnection && (
              <Button
                variant="outline"
                onClick={onConfigure}
                data-testid="lab-configure-button"
              >
                {tb("composer.configure")}
              </Button>
            )}
            <p className="composer-note">
              <span className="composer-mode">
                {s.requiresModel
                  ? tb("composer.modeModel")
                  : tb("composer.modeLocal")}
              </span>
              {s.requiresModel
                ? tb("composer.noteModel")
                : tb("composer.noteLocal")}
            </p>
          </section>
          <section className="lab-answer" aria-live="polite">
            <div className="pane-heading">
              <span>
                <MessageSquare size={17} />
                {tb("answer.title")}
              </span>
              {s.answer && <Check size={15} />}
            </div>
            {s.answer ? (
              <Answer
                content={String(s.answer.data.content || tb("answer.noText"))}
              />
            ) : (
              <div className="answer-placeholder">
                {s.running ? (
                  <LatticeLoader
                    pattern="snake"
                    color="var(--accent)"
                    fontSize={13}
                    label={
                      s.requiresModel
                        ? tb("answer.waitingModel")
                        : tb("answer.waitingLocal")
                    }
                  />
                ) : (
                  <>
                    {tb("answer.empty")}
                    <span>{tb("answer.emptyReplay")}</span>
                  </>
                )}
              </div>
            )}
          </section>
          <div className="lab-connection">
            <i />
            <span>
              {s.requiresModel
                ? s.status?.provider_label || tb("connection.none")
                : tb("connection.local")}
              <small>
                {s.requiresModel
                  ? s.status?.model || tb("connection.noModel")
                  : tb("connection.localNote")}
              </small>
            </span>
            <Button variant="ghost" size="sm" onClick={onConfigure}>
              {tb("connection.settings")}
            </Button>
          </div>
        </div>
        <section className="lab-inspector">
          <div className="inspector-heading">
            <div>
              <h2>
                <Waypoints size={18} />
                {tb("inspector.title")}
              </h2>
              <p>{tb("inspector.subtitle")}</p>
            </div>
            <span
              className={`trace-status ${s.running ? "is-running" : ""}`}
              data-testid="lab-trace-status"
            >
              <span aria-hidden="true">
                <StatusMark
                  size={16}
                  strike={false}
                  status={
                    s.running && active
                      ? "running"
                      : completed
                        ? "done"
                        : s.events.some((e) => e.type === "error")
                          ? "failed"
                          : last?.data.status === "cancelled"
                            ? "cancelled"
                            : "pending"
                  }
                  doneColor="var(--success)"
                  errorColor="var(--danger)"
                />
              </span>
              {s.running
                ? tb("status.running")
                : completed
                  ? tb("status.completed")
                  : s.events.length
                    ? tb("status.ended")
                    : tb("status.idle")}
            </span>
          </div>
          <Tabs value={tab} onValueChange={setTab} className="inspector-tabs">
            <TabsList
              aria-label={tb("inspector.tabs")}
              className="inspector-tab-list"
            >
              <TabsTrigger value="trace">{tb("inspector.trace")}</TabsTrigger>
              <TabsTrigger value="source" data-testid="lab-tab-source">
                {tb("inspector.source")}
              </TabsTrigger>
              <TabsTrigger value="prompt">{tb("inspector.prompt")}</TabsTrigger>
            </TabsList>
            <TabsContent value="trace" className="inspector-trace">
              <LessonExtension
                slot="inspector"
                extensionKey={s.detail?.ui?.inspector}
                studio={s}
                active={active}
              >
                <AgentStage
                  events={s.events}
                  cursor={s.cursor}
                  live={live}
                  spotlight={spotlight}
                />
              </LessonExtension>
              <div className="inspector-summary" data-testid="lab-run-metrics">
                <span>
                  <RunMetric value={requests} /> {tb("metrics.requests")}
                </span>
                <span>
                  <RunMetric value={tools} /> {tb("metrics.tools")}
                </span>
                <span>
                  <RunMetric value={s.cursor} /> {tb("metrics.events")}
                </span>
              </div>
              {s.running && <RunActivity openLlm={openLlm} last={last} />}
              <ToolCallChips
                spans={stage.spans}
                events={s.events}
                live={live}
                activeIndex={activeIndex}
                onSelect={s.selectEvent}
              />
              {s.events.length > 0 && (
                <div
                  className="replay-toolbar"
                  data-testid="lab-replay-toolbar"
                >
                  <Button
                    variant="ghost"
                    size="icon"
                    disabled={s.running}
                    data-testid="lab-replay-play"
                    aria-label={
                      s.playing ? tb("replay.pause") : tb("replay.play")
                    }
                    onClick={s.replay}
                  >
                    {s.playing ? <Pause size={15} /> : <Play size={15} />}
                  </Button>
                  <Button
                    variant="ghost"
                    size="icon"
                    disabled={s.running || s.cursor >= s.events.length}
                    data-testid="lab-replay-step"
                    aria-label={tb("replay.step")}
                    onClick={s.step}
                  >
                    <SkipForward size={15} />
                  </Button>
                  <Button
                    variant="ghost"
                    size="icon"
                    disabled={s.running}
                    data-testid="lab-replay-rewind"
                    aria-label={tb("replay.rewind")}
                    onClick={() => s.seek(0)}
                  >
                    <RotateCcw size={15} />
                  </Button>
                  <WakeSlider
                    ariaLabel={tb("replay.progress")}
                    className="replay-slider"
                    value={s.cursor}
                    min={0}
                    max={s.events.length}
                    step={1}
                    disabled={s.running}
                    onChange={s.seek}
                    height={24}
                    restHeight={4}
                    gap={3}
                    fillColor="var(--accent)"
                    trackColor="var(--line)"
                  />
                  <span>
                    {s.cursor}/{s.events.length}
                  </span>
                  <RubberSegment
                    aria-label={t("replay.pacing")}
                    size="sm"
                    items={(["uniform", "real1", "real2"] as const).map(
                      (value) => ({ value, label: t(`replay.${value}`) }),
                    )}
                    value={pacing}
                    disabled={s.running}
                    onChange={(value) =>
                      s.setReplayOptions(
                        value === "uniform"
                          ? { pacing: "uniform", speed: 1 }
                          : {
                              pacing: "realtime",
                              speed: value === "real2" ? 2 : 1,
                            },
                      )
                    }
                    trackColor="var(--surface-muted)"
                    thumbColor="var(--surface)"
                    textColor="var(--text-muted)"
                    activeTextColor="var(--text)"
                  />
                  <Button
                    variant="ghost"
                    size="icon"
                    data-testid="lab-download-trace"
                    aria-label={tb("replay.download")}
                    onClick={s.download}
                  >
                    <Download size={16} />
                  </Button>
                </div>
              )}
              {s.events.length > 1 && (
                <Timeline
                  events={s.events}
                  spans={finalSpans}
                  cursor={s.cursor}
                  onSeek={s.seek}
                />
              )}
              {s.replayGap?.compressed && (
                <p className="replay-footnote" role="status">
                  {t("replay.compressed")}
                </p>
              )}
              {s.events.length > 0 && (
                <div className="stage-detail-grid">
                  <ContextFilm film={stage.film} onSelect={s.selectEvent} />
                  <ToolCards
                    spans={stage.spans}
                    events={s.events}
                    live={s.running}
                    onSelect={s.selectEvent}
                  />
                </div>
              )}
              <Lenses visible={s.visible} film={stage.film} />
              <div className="trace-split">
                <div className="trace-list-pane" data-testid="lab-trace-list">
                  <div className="subpane-label">
                    {tb("list.title")} <small>EVENTS</small>
                  </div>
                  <div
                    className="timeline"
                    ref={list}
                    data-testid="lab-timeline"
                  >
                    {s.visible.map((event: Trace, index: number) => {
                      const selected = s.active === event;
                      return (
                        <Button
                          key={index}
                          variant="ghost"
                          className={`event event-${event.type} ${selected ? "is-selected" : ""}`}
                          data-testid={`lab-event-${event.type.replace(/[._]/g, "-")}`}
                          aria-pressed={selected}
                          onClick={() => s.selectEvent(index)}
                        >
                          {selected && (
                            <motion.span
                              layoutId={`${pillId}-event`}
                              className="event-pill"
                              aria-hidden="true"
                              transition={
                                reducedMotion ? { duration: 0 } : PILL_SPRING
                              }
                            />
                          )}
                          <span className="event-index">
                            {String(index + 1).padStart(2, "0")}
                          </span>
                          <span className="event-text">
                            <strong>{label(event)}</strong>
                            <small>{summary(event)}</small>
                          </span>
                          <span className="event-round">
                            {event.round ? `R${event.round}` : ""}
                          </span>
                        </Button>
                      );
                    })}
                    {!s.visible.length && (
                      <div className="trace-list-empty">
                        <Waypoints size={24} />
                        <p>
                          {s.events.length
                            ? tb("list.rewound")
                            : tb("list.empty")}
                        </p>
                        <small>
                          {s.events.length
                            ? tb("list.rewoundHint")
                            : tb("list.emptyHint")}
                        </small>
                      </div>
                    )}
                  </div>
                </div>
                <div className="event-detail" data-testid="lab-event-detail">
                  <div className="subpane-label">
                    <span>
                      {s.active ? label(s.active) : tb("detail.title")}
                    </span>
                    {s.active && (
                      <Button
                        variant="ghost"
                        size="icon"
                        aria-label={tb("detail.copy")}
                        onClick={async () => {
                          try {
                            await navigator.clipboard.writeText(
                              JSON.stringify(activeBody, null, 2),
                            );
                            setCopied(true);
                          } catch {
                            s.setError(tb("detail.copyFailed"));
                          }
                        }}
                      >
                        {copied ? <Check size={15} /> : <Copy size={15} />}
                      </Button>
                    )}
                  </div>
                  {s.active ? (
                    <div className="event-detail-body" key={activeIndex}>
                      <p className="event-explanation">
                        {s.active.data.representation === "sdk_standardized"
                          ? tb("detail.sdk")
                          : ["request", "response"].includes(s.active.type)
                            ? tb("detail.http")
                            : tb("detail.generic")}
                      </p>
                      <Code
                        content={JSON.stringify(activeBody, null, 2) || "null"}
                      />
                    </div>
                  ) : (
                    <div className="inspector-empty">
                      <div>
                        <Code2 size={28} />
                      </div>
                      <h3 aria-label={tb("detail.emptyTitle")}>
                        {active ? (
                          <TextType
                            text={tb("detail.emptyTitle")}
                            typingSpeed={90}
                            startOnVisible
                            loop={false}
                            showCursor={!reducedMotion}
                            aria-hidden="true"
                          />
                        ) : (
                          tb("detail.emptyTitle")
                        )}
                      </h3>
                      <p>
                        {tb("detail.emptyLine1")}
                        <br />
                        {tb("detail.emptyLine2")}
                      </p>
                      <div className="empty-flow">
                        <span>{tb("detail.flowQuestion")}</span>
                        <ArrowRight size={13} />
                        <span>{tb("detail.flowModel")}</span>
                        <ArrowRight size={13} />
                        <span>{tb("detail.flowTool")}</span>
                      </div>
                    </div>
                  )}
                </div>
              </div>
              <p className="replay-footnote">{tb("replay.footnote")}</p>
            </TabsContent>
            <TabsContent
              value="source"
              className="lab-source source-pane"
              data-testid="lab-source-panel"
            >
              <div className="source-toolbar">
                <Terminal size={16} />
                <GlideSelect
                  {...pickerColors}
                  ariaLabel={tb("source.file")}
                  className="full-picker"
                  value={String(s.source)}
                  onChange={(v) => s.setSource(Number(v))}
                  options={
                    s.detail?.sources.map((f, i) => ({
                      value: String(i),
                      label: f.path,
                    })) || []
                  }
                />
                <small>{tb("source.readonly")}</small>
              </div>
              {file && (
                <Code
                  content={file.content}
                  language={file.language === "py" ? "python" : file.language}
                />
              )}
            </TabsContent>
            <TabsContent value="prompt" className="lab-prompt">
              <h3>System prompt</h3>
              <pre>{s.detail?.system_prompt}</pre>
              <h3>{tb("prompt.tools")}</h3>
              <Code
                content={JSON.stringify(s.detail?.tools, null, 2) || "[]"}
              />
            </TabsContent>
          </Tabs>
        </section>
      </div>
    </BorderGlow>
  );
}
