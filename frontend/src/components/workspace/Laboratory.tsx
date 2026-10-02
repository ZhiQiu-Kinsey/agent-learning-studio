import { useEffect, useMemo, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { useReducedMotion } from "../../motion";
import BorderGlow from "../react-bits/BorderGlow";
import CountUp from "../react-bits/CountUp";
import ClickSpark from "../react-bits/ClickSpark";
import StarBorder from "../react-bits/StarBorder";
import TextType from "../react-bits/TextType";
import StatusMark from "../react-bits/StatusMark";
import { AgentStage } from "../../stage/AgentStage";
import { ContextFilm } from "../../stage/ContextFilm";
import { Timeline } from "../../stage/Timeline";
import { ToolCards } from "../../stage/ToolCards";
import { deriveStage } from "../../stage/derive";
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
  LoaderCircle,
  MessageSquare,
  Pause,
  Play,
  RotateCcw,
  SkipForward,
  Square,
  Terminal,
  Waypoints,
} from "lucide-react";
import type { StudioState } from "../../hooks/useStudio";
import type { Trace } from "../../types";
import { Button } from "../ui/button";
import { Textarea } from "../ui/textarea";
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
  const file = s.detail?.sources[s.source];
  const requests = s.visible.filter((e: Trace) => e.type === "request").length;
  const tools = s.visible.filter((e: Trace) => e.type === "tool_call").length;
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
      <div className="lab-workspace" data-testid="lab-workspace">
        <div className="lab-command-column">
          <section className="lab-composer">
            <div className="pane-heading">
              <span>
                <FlaskConical size={17} />
                运行一个问题
              </span>
              <small>LIVE</small>
            </div>
            <p className="pane-description">
              {s.requiresModel
                ? s.detail?.capabilities?.custom_runtime
                  ? "修改参数，观察本课模型请求、校验和执行证据。"
                  : "修改输入，观察模型如何选择和执行工具。"
                : "修改输入，观察本课程序的执行过程。"}
            </p>
            <div className="form-field" data-testid="lab-exercise-field">
              <label>练习场景</label>
              <GlideSelect
                {...pickerColors}
                size="lg"
                className="full-picker"
                ariaLabel="练习场景"
                value={s.exerciseId}
                onChange={s.selectExercise}
                disabled={s.running || !s.detail}
                options={
                  s.detail?.exercises
                    .filter((e) => !e.offline_only)
                    .map((e) => ({ value: e.id, label: e.title })) || []
                }
              />
            </div>
            <div className="form-field">
              <label htmlFor="lab-question">
                {s.detail?.ui?.question_label || "你的问题"}
              </label>
              <Textarea
                id="lab-question"
                data-testid="lab-question-input"
                value={s.question}
                disabled={s.running}
                onChange={(e) => s.setQuestion(e.target.value)}
                placeholder="输入你想让 Agent 完成的任务…"
                aria-describedby={
                  s.detail?.ui?.question_help ? "lab-question-help" : undefined
                }
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
                配置模型连接
              </Button>
            )}
            <ClickSpark
              sparkColor="#a49cff"
              sparkCount={reducedMotion ? 0 : 7}
              sparkRadius={30}
              sparkSize={7}
              duration={450}
            >
              <div className="composer-actions">
                {s.running ? (
                  <Button onClick={s.cancel} variant="destructive">
                    <Square size={14} />
                    停止运行
                  </Button>
                ) : (
                  <StarBorder
                    className="lab-run-star"
                    color="#c4b5ff"
                    speed="4s"
                  >
                    <Button
                      data-testid="lab-run-button"
                      onClick={() => {
                        setTab("trace");
                        void s.run();
                      }}
                      disabled={
                        !s.detail ||
                        !ready ||
                        (!s.question.trim() &&
                          !s.detail.capabilities?.supports_inputs)
                      }
                    >
                      <Play size={15} />
                      运行练习
                    </Button>
                  </StarBorder>
                )}
                <small>
                  {s.requiresModel ? "使用真实模型" : "运行本课程序"}
                </small>
              </div>
            </ClickSpark>
            <p className="composer-note">
              {s.requiresModel
                ? "模型请求按服务商规则计费。工具在本机 Python 执行。"
                : "本课无需模型连接，使用本地课程程序运行。"}
            </p>
          </section>
          <section className="lab-answer" aria-live="polite">
            <div className="pane-heading">
              <span>
                <MessageSquare size={17} />
                最终回答
              </span>
              {s.answer && <Check size={15} />}
            </div>
            {s.answer ? (
              <Answer
                content={String(s.answer.data.content || "（模型未返回文本）")}
              />
            ) : (
              <div className="answer-placeholder">
                {s.running ? (
                  <>
                    <LoaderCircle size={17} className="spin" />
                    {s.requiresModel
                      ? "等待模型完成当前任务…"
                      : "等待本课程序完成当前任务…"}
                  </>
                ) : (
                  <>
                    回答会出现在这里。
                    <span>回放时，这里与选中的进度保持同步。</span>
                  </>
                )}
              </div>
            )}
          </section>
          <div className="lab-connection">
            <i />
            <span>
              {s.requiresModel
                ? s.status?.provider_label || "未连接"
                : "本地课程程序"}
              <small>
                {s.requiresModel
                  ? s.status?.model || "请先设置模型"
                  : "无需配置模型连接"}
              </small>
            </span>
            <Button variant="ghost" size="sm" onClick={onConfigure}>
              设置
            </Button>
          </div>
        </div>
        <section className="lab-inspector">
          <div className="inspector-heading">
            <div>
              <h2>
                <Waypoints size={18} />
                运行观察台
              </h2>
              <p>看到每一步，也看到每一步的数据。</p>
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
                ? "运行中"
                : completed
                  ? "已完成"
                  : s.events.length
                    ? "已结束"
                    : "等待运行"}
            </span>
          </div>
          <Tabs value={tab} onValueChange={setTab} className="inspector-tabs">
            <TabsList aria-label="实验观察内容" className="inspector-tab-list">
              <TabsTrigger value="trace">执行记录</TabsTrigger>
              <TabsTrigger value="source" data-testid="lab-tab-source">
                Python 源码
              </TabsTrigger>
              <TabsTrigger value="prompt">提示词与工具</TabsTrigger>
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
                  live={s.running && s.cursor === s.events.length}
                  spotlight={spotlight}
                />
              </LessonExtension>
              <div className="inspector-summary" data-testid="lab-run-metrics">
                <span>
                  <RunMetric value={requests} /> 模型请求
                </span>
                <span>
                  <RunMetric value={tools} /> 工具调用
                </span>
                <span>
                  <RunMetric value={s.cursor} /> 运行事件
                </span>
              </div>
              {s.running && (
                <ThoughtLine
                  label={
                    last
                      ? `${label(last)} · ${summary(last).slice(0, 50)}`
                      : "正在建立连接"
                  }
                  working
                  showTimer={false}
                  glyph="dot"
                  collapsible={false}
                  className="trace-activity"
                  fontSize={13}
                />
              )}
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
                    aria-label={s.playing ? "暂停回放" : "播放回放"}
                    onClick={s.replay}
                  >
                    {s.playing ? <Pause size={15} /> : <Play size={15} />}
                  </Button>
                  <Button
                    variant="ghost"
                    size="icon"
                    disabled={s.running || s.cursor >= s.events.length}
                    data-testid="lab-replay-step"
                    aria-label="下一步"
                    onClick={s.step}
                  >
                    <SkipForward size={15} />
                  </Button>
                  <Button
                    variant="ghost"
                    size="icon"
                    disabled={s.running}
                    data-testid="lab-replay-rewind"
                    aria-label="回到起点"
                    onClick={() => s.seek(0)}
                  >
                    <RotateCcw size={15} />
                  </Button>
                  <WakeSlider
                    ariaLabel="回放进度"
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
                    aria-label="下载本次运行记录"
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
                    执行顺序 <small>EVENTS</small>
                  </div>
                  <div
                    className="timeline"
                    ref={list}
                    data-testid="lab-timeline"
                  >
                    {s.visible.map((event: Trace, index: number) => (
                      <Button
                        key={index}
                        variant="ghost"
                        className={`event event-${event.type} ${s.active === event ? "is-selected" : ""}`}
                        data-testid={`lab-event-${event.type.replace(/[._]/g, "-")}`}
                        aria-pressed={s.active === event}
                        onClick={() => s.selectEvent(index)}
                      >
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
                    ))}
                    {!s.visible.length && (
                      <div className="trace-list-empty">
                        <Waypoints size={24} />
                        <p>
                          {s.events.length ? "已回到起点" : "还没有运行事件"}
                        </p>
                        <small>
                          {s.events.length
                            ? "播放回放或向前一步。"
                            : "运行后，步骤会依次出现在这里。"}
                        </small>
                      </div>
                    )}
                  </div>
                </div>
                <div className="event-detail" data-testid="lab-event-detail">
                  <div className="subpane-label">
                    <span>{s.active ? label(s.active) : "请求与响应"}</span>
                    {s.active && (
                      <Button
                        variant="ghost"
                        size="icon"
                        aria-label="复制事件 JSON"
                        onClick={async () => {
                          try {
                            await navigator.clipboard.writeText(
                              JSON.stringify(activeBody, null, 2),
                            );
                            setCopied(true);
                          } catch {
                            s.setError("复制失败，请手动选中数据复制。");
                          }
                        }}
                      >
                        {copied ? <Check size={15} /> : <Copy size={15} />}
                      </Button>
                    )}
                  </div>
                  {s.active ? (
                    <>
                      <p className="event-explanation">
                        {s.active.data.representation === "sdk_standardized"
                          ? "SDK 标准化数据，不等同于原始 HTTP 报文。"
                          : ["request", "response"].includes(s.active.type)
                            ? "完整 HTTP 请求或响应数据，可检查 messages、tools 和 tool_call_id。"
                            : "当前事件的完整执行数据。"}
                      </p>
                      <Code
                        content={JSON.stringify(activeBody, null, 2) || "null"}
                      />
                    </>
                  ) : (
                    <div className="inspector-empty">
                      <div>
                        <Code2 size={28} />
                      </div>
                      <h3 aria-label="让执行过程变得可读">
                        {active ? (
                          <TextType
                            text="让执行过程变得可读"
                            typingSpeed={90}
                            startOnVisible
                            loop={false}
                            showCursor={!reducedMotion}
                            aria-hidden="true"
                          />
                        ) : (
                          "让执行过程变得可读"
                        )}
                      </h3>
                      <p>
                        在左侧运行问题，再选择一个事件。
                        <br />
                        这里会显示完整请求、响应或工具结果。
                      </p>
                      <div className="empty-flow">
                        <span>问题</span>
                        <ArrowRight size={13} />
                        <span>模型</span>
                        <ArrowRight size={13} />
                        <span>工具</span>
                      </div>
                    </div>
                  )}
                </div>
              </div>
              <p className="replay-footnote">
                回放只读取本次记录，不会再次请求模型。
              </p>
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
                  ariaLabel="实验源码文件"
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
                <small>只读</small>
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
              <h3>工具定义</h3>
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
