import { useState } from "react";
import { useReducedMotion } from "../../motion";
import {
  ArrowRight,
  BookOpen,
  Code2,
  ListChecks,
  Workflow,
} from "lucide-react";
import type { StudioState } from "../../hooks/useStudio";
import { Code } from "../Code";
import { Quiz } from "../Quiz";
import { Button } from "../ui/button";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "../ui/tabs";
import GlideSelect from "../react-bits/GlideSelect";
import LineSidebar from "../react-bits/LineSidebar";
import StarBorder from "../react-bits/StarBorder";
import Magnet from "../react-bits/Magnet";
import { LessonHero } from "../learning/LessonHero";
import { LessonGuide } from "../learning/LessonGuide";
import { LessonExtension } from "../../lesson-extensions/LessonExtension";
import { lessonView } from "../../content/view";
import "../../styles/learning-experience.css";

export function LearningWorkspace({
  studio,
  onStartLab,
  active,
}: {
  studio: StudioState;
  onStartLab: () => void;
  active: boolean;
}) {
  const [tab, setTab] = useState("guide");
  const reducedMotion = useReducedMotion();
  const { detail, lessonError, source, setSource } = studio;
  if (lessonError)
    return (
      <div className="learn-empty" role="alert">
        {lessonError}
      </div>
    );
  if (!detail)
    return (
      <div className="learn-empty" role="status">
        正在准备课程内容…
      </div>
    );
  const activeSource = detail.sources[source] ?? detail.sources[0];
  return (
    <div
      className={`learn-workspace learning-experience ${tab === "guide" ? "is-guide" : ""}`}
    >
      <Tabs value={tab} onValueChange={setTab} className="learn-tabs">
        <TabsList
          variant="line"
          className="learn-tab-list"
          aria-label="课程学习内容"
          data-testid="learn-tabs"
        >
          <TabsTrigger
            className="learn-tab"
            value="guide"
            data-testid="learn-tab-guide"
          >
            <BookOpen size={16} />
            课程导读
          </TabsTrigger>
          <TabsTrigger
            className="learn-tab"
            value="source"
            data-testid="learn-tab-source"
          >
            <Code2 size={16} />
            Python 源码
          </TabsTrigger>
          <TabsTrigger
            className="learn-tab"
            value="reference"
            data-testid="learn-tab-reference"
          >
            <Workflow size={16} />
            提示词与工具
          </TabsTrigger>
          <TabsTrigger
            className="learn-tab"
            value="quiz"
            data-testid="learn-tab-quiz"
          >
            <ListChecks size={16} />
            课后自测
          </TabsTrigger>
        </TabsList>
        {tab === "guide" && (
          <LessonHero
            key={detail.id}
            detail={detail}
            onSource={() => setTab("source")}
          />
        )}
        <div className="learn-layout">
          <div
            className="learn-main"
            data-testid="learn-main"
          >
            <TabsContent value="guide" className="learn-tab-content">
              <LessonExtension
                slot="guide"
                extensionKey={detail.ui?.guide}
                studio={studio}
                active={active && tab === "guide"}
                onStartLab={onStartLab}
              >
                <LessonGuide detail={detail} />
              </LessonExtension>
            </TabsContent>
            <TabsContent value="source" className="learn-tab-content">
              <div className="learn-source-toolbar">
                <div>
                  <h2>从代码理解运行机制</h2>
                  <p>
                    这里展示本课完整源码。沿着输入、工具调用与结果返回，逐步阅读。
                  </p>
                </div>
                <GlideSelect
                  className="learn-source-select"
                  ariaLabel="选择 Python 源文件"
                  value={String(detail.sources.indexOf(activeSource))}
                  options={detail.sources.map((file, index) => ({
                    value: String(index),
                    label: file.path,
                    tag: file.language,
                  }))}
                  onChange={(value) => setSource(Number(value))}
                  disabled={!detail.sources.length}
                  menuWidth={320}
                  surfaceColor="var(--surface)"
                  highlightColor="var(--surface-muted)"
                  textColor="var(--text)"
                  accentColor="var(--accent)"
                />
              </div>
              {activeSource ? (
                <div
                  className="learn-code-frame"
                  data-testid="learn-source-code"
                >
                  <Code
                    content={activeSource.content}
                    language={
                      activeSource.language === "py"
                        ? "python"
                        : activeSource.language
                    }
                  />
                </div>
              ) : (
                <p className="learn-empty">这节课暂未提供源码。</p>
              )}
            </TabsContent>
            <TabsContent value="reference" className="learn-tab-content">
              <section className="learn-reference-section">
                <span className="reading-eyebrow">SYSTEM PROMPT</span>
                <h2>模型收到的任务边界</h2>
                <p>阅读系统提示词，理解模型的角色、约束与工具使用要求。</p>
                {detail.system_prompt ? (
                  <div className="learn-code-frame">
                    <Code content={detail.system_prompt} language="text" />
                  </div>
                ) : (
                  <p>本课没有单独的系统提示词。</p>
                )}
              </section>
              <section className="learn-reference-section">
                <span className="reading-eyebrow">TOOL DEFINITIONS</span>
                <h2>可调用工具的接口</h2>
                <p>
                  对照工具名称、参数结构与 Python
                  实现，观察模型如何提出调用请求。
                </p>
                <div className="learn-code-frame">
                  <Code
                    content={
                      JSON.stringify(detail.tools, null, 2) ?? "未提供工具定义"
                    }
                    language="json"
                  />
                </div>
              </section>
            </TabsContent>
            <TabsContent value="quiz" className="learn-tab-content" forceMount>
              <Quiz key={detail.id} questions={lessonView(detail.learning).quiz} />
            </TabsContent>
          </div>
          <aside className="learn-sidebar" aria-label="学习路线">
            <StarBorder className="learn-objectives-glow">
              <section className="learn-objectives">
                <span className="reading-eyebrow">本课目标</span>
                <h2>学完之后，你能…</h2>
                <ul>
                  {detail.objectives.map((objective, index) => (
                    <li key={index}>{objective}</li>
                  ))}
                </ul>
              </section>
            </StarBorder>
            <section
              className="learn-steps"
              data-testid="learn-steps"
            >
              <h3>建议学习顺序</h3>
              <LineSidebar
                ariaLabel="学习步骤导航"
                className="learning-path-lines"
                items={["读懂原理", "对照源码", "运行与观察", "自测与复盘"]}
                activeItem={
                  tab === "source"
                    ? 1
                    : tab === "quiz"
                      ? 3
                      : tab === "guide"
                        ? 0
                        : null
                }
                onItemClick={(index) => {
                  if (index === 2) onStartLab();
                  else
                    setTab(
                      index === 1 ? "source" : index === 3 ? "quiz" : "guide",
                    );
                }}
                accentColor="var(--accent)"
                textColor="var(--text-muted)"
                markerColor="var(--line)"
                markerLength={18}
                markerGap={8}
                itemGap={14}
                fontSize={0.86}
                maxShift={reducedMotion ? 0 : 8}
                smoothing={reducedMotion ? 1 : 110}
                proximityRadius={65}
              />
              <p className="learning-path-caption">
                点击步骤切换内容，按自己的节奏学习。
              </p>
            </section>
            <div className="learn-lab-cta">
              <Magnet>
                <StarBorder className="learn-cta-glow" speed="5s">
                  <Button
                    variant="link"
                    className="learn-start-lab"
                    onClick={onStartLab}
                  >
                    进入实验工作台
                    <ArrowRight size={16} />
                  </Button>
                </StarBorder>
              </Magnet>
              <p>用一次真实运行，验证刚学到的原理。</p>
            </div>
          </aside>
        </div>
      </Tabs>
    </div>
  );
}
