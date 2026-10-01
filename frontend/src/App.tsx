import { lazy, Suspense, useRef, useState } from "react";
import { motion } from "motion/react";
import { MotionIntent, useReducedMotion } from "./motion";
import ShinyText from "./components/react-bits/ShinyText";
import {
  ArrowUpRight,
  BookOpen,
  ChevronRight,
  FlaskConical,
  Layers3,
  Menu,
  Settings2,
  Waypoints,
  X,
} from "lucide-react";
import { useStudio } from "./hooks/useStudio";
import { formatLessonNumber } from "./lib/lessonIds";
import { ModelSettings } from "./components/workspace/ModelSettings";
import { ThemeSwitch } from "./components/ThemeSwitch";
import { MotionSwitch } from "./components/MotionSwitch";
import { CourseNavigation } from "./components/CourseNavigation";
import { LessonExtension } from "./lesson-extensions/LessonExtension";
import { Button } from "./components/ui/button";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "./components/ui/tabs";
import {
  Sheet,
  SheetContent,
  SheetTitle,
  SheetDescription,
} from "./components/ui/sheet";

const Onboarding = lazy(() =>
  import("./components/Onboarding").then((module) => ({
    default: module.Onboarding,
  })),
);
const Curriculum = lazy(() =>
  import("./components/Curriculum").then((module) => ({
    default: module.Curriculum,
  })),
);
const LearningWorkspace = lazy(() =>
  import("./components/workspace/LearningWorkspace").then((module) => ({
    default: module.LearningWorkspace,
  })),
);
const Laboratory = lazy(() =>
  import("./components/workspace/Laboratory").then((module) => ({
    default: module.Laboratory,
  })),
);
const loadingPanel = (
  <div className="learn-empty" role="status">
    正在准备学习内容…
  </div>
);

export default function App() {
  const reducedMotion = useReducedMotion();
  const studio = useStudio();
  const [mode, setMode] = useState("learn");
  const [catalog, setCatalog] = useState(false);
  const [intro, setIntro] = useState(() => {
    try {
      return localStorage.getItem("agent-lab-entry") !== "lesson";
    } catch {
      return true;
    }
  });
  const [introChapter, setIntroChapter] = useState(0);
  const [hasOpenedLesson, setHasOpenedLesson] = useState(!intro);
  const [hasOpenedLab, setHasOpenedLab] = useState(false);
  const [menu, setMenu] = useState(false);
  const [settings, setSettings] = useState(false);
  const settingsRef = useRef<HTMLButtonElement>(null);
  const menuRef = useRef<HTMLButtonElement>(null);
  const title =
    studio.detail?.title.replace(/^第\s*\d+\s*课[：:]?\s*/, "") ||
    "准备学习环境";
  const number = formatLessonNumber(
    studio.lessons.find((lesson) => lesson.id === studio.lessonId)?.number,
  );
  function choose(id: string) {
    if (studio.running) return;
    studio.selectLesson(id);
    setHasOpenedLesson(true);
    setIntro(false);
    try {
      localStorage.setItem("agent-lab-entry", "lesson");
    } catch {
      /* Session navigation still works. */
    }
    setCatalog(false);
    setMode("learn");
    setMenu(false);
  }
  const navigation = (
    <>
      <div className="rail-brand">
        <span>
          <Waypoints size={23} />
        </span>
        <div>
          <ShinyText
            text="Agent Lab"
            color="var(--text)"
            shineColor="var(--accent)"
            speed={3}
            delay={3}
            disabled={!!reducedMotion}
          />
          <small>开发者学习空间</small>
        </div>
      </div>
      <Button
        variant="ghost"
        className={`rail-catalog ${catalog ? "is-active" : ""}`}
        data-testid="app-curriculum-button"
        aria-pressed={catalog}
        disabled={studio.running}
        onClick={() => {
          setCatalog(true);
          setIntro(false);
          setMenu(false);
        }}
      >
        <Layers3 size={17} />
        完整课程表
        <ArrowUpRight size={15} />
      </Button>
      <div className="nav-prelude">
        <span className="course-tree-heading">
          开始之前 <small>START HERE</small>
        </span>
        {["学习前言", "认识 Agent", "学习路线与准备", "使用实验工作台"].map(
          (label, index) => (
            <Button
              key={label}
              variant="ghost"
              className={`nav-prelude-link ${intro && introChapter === index ? "is-active" : ""}`}
              aria-current={
                intro && introChapter === index ? "page" : undefined
              }
              disabled={studio.running}
              onClick={() => {
                setIntro(true);
                setIntroChapter(index);
                setCatalog(false);
                setMenu(false);
                window.scrollTo({ top: 0 });
              }}
            >
              <span>0{index + 1}</span>
              {label}
              <ChevronRight size={12} />
            </Button>
          ),
        )}
      </div>
      <CourseNavigation
        lessons={studio.lessons}
        current={!intro && !catalog ? studio.lessonId : undefined}
        disabled={studio.running}
        onSelect={choose}
      />
      <div className="rail-next">
        <BookOpen size={18} />
        <strong>从原理，到工程</strong>
        <p>沿着课程地图，逐步学习记忆、检索、框架与多 Agent 协作。</p>
        <Button
          variant="ghost"
          disabled={studio.running}
          onClick={() => {
            setCatalog(true);
            setIntro(false);
            setMenu(false);
          }}
        >
          探索学习路线 <ChevronRight size={14} />
        </Button>
      </div>
      <div className="rail-footer">
        <i />
        本地学习空间<span>Python + React</span>
      </div>
    </>
  );
  return (
    <div className="studio-shell experience-shell">
      <aside className="course-rail">{navigation}</aside>
      <Sheet open={menu} onOpenChange={setMenu}>
        <SheetContent
          side="left"
          className="course-sheet"
          onCloseAutoFocus={(e) => {
            e.preventDefault();
            menuRef.current?.focus();
          }}
        >
          <SheetTitle className="sr-only">课程菜单</SheetTitle>
          <SheetDescription className="sr-only">
            选择一节课程继续学习。
          </SheetDescription>
          {navigation}
        </SheetContent>
      </Sheet>
      <div className="studio-body">
        <header className="app-toolbar">
          <div className="app-location">
            <Button
              ref={menuRef}
              variant="ghost"
              size="icon"
              className="open-course-menu"
              data-testid="app-open-course-menu"
              aria-label="打开课程菜单"
              onClick={() => setMenu(true)}
            >
              <Menu size={18} />
            </Button>
            <span>Agent 开发</span>
            <ChevronRight size={13} />
            <strong>
              {intro ? "开始之前" : catalog ? "课程地图" : "基础实践"}
            </strong>
          </div>
          <div className="app-preferences">
            <MotionSwitch />
            <ThemeSwitch />
            <Button
              ref={settingsRef}
              variant="outline"
              className="connection-button"
              data-testid="app-connection-button"
              title="配置模型连接"
              onClick={() => setSettings(true)}
            >
              <i className={studio.status?.config_ready ? "is-ready" : ""} />
              <span>{studio.status?.provider_label || "连接模型"}</span>
              <Settings2 size={15} />
            </Button>
          </div>
        </header>
        <main className="studio-main">
          {studio.error && (
            <div role="alert" className="workspace-error">
              <span>{studio.error}</span>
              <Button
                variant="ghost"
                size="icon"
                aria-label="关闭错误提示"
                onClick={() => studio.setError("")}
              >
                <X size={16} />
              </Button>
            </div>
          )}
          {intro && (
            <Suspense fallback={loadingPanel}>
              <Onboarding
                chapter={introChapter}
                onChapterChange={setIntroChapter}
                onStart={() => {
                  const first = studio.lessons.find(
                    (lesson) => lesson.available,
                  );
                  if (first) choose(first.id);
                }}
                onMap={() => {
                  setIntro(false);
                  setCatalog(true);
                }}
              />
            </Suspense>
          )}
          {catalog && (
            <Suspense fallback={loadingPanel}>
              <Curriculum onSelectLesson={choose} />
            </Suspense>
          )}
          <div hidden={catalog || intro}>
            {hasOpenedLesson && (
              <Tabs
                value={mode}
                onValueChange={(value) => {
                  setMode(value);
                  if (value === "lab") setHasOpenedLab(true);
                }}
                className="workspace-modes"
              >
                <div
                  className="lesson-masthead"
                  data-testid="lesson-masthead"
                >
                  <div className="masthead-aurora" aria-hidden="true">
                    {!catalog && !intro && (
                      <MotionIntent
                        name="ambient.aurora"
                        colorStops={["#6d5dfc", "#49dec6", "#b98aff"]}
                        amplitude={0.65}
                        blend={0.65}
                        speed={0.55}
                      />
                    )}
                  </div>
                  <div className="masthead-texture" aria-hidden="true">
                    {!catalog && !intro && (
                      <MotionIntent
                        name="ambient.dot-grid"
                        dotSize={2}
                        gap={17}
                        baseColor="#a2a4bb"
                        activeColor="#7d73cb"
                        proximity={70}
                        shockStrength={1}
                      />
                    )}
                  </div>
                  <div className="lesson-heading">
                    <span
                      className="lesson-badge"
                      data-testid="lesson-badge"
                    >
                      {number}
                    </span>
                    <div>
                      <p className="masthead-kicker">
                        AGENT LEARNING <span>/</span> 实践课 {number}
                      </p>
                      <MotionIntent
                        name="heading.split"
                        key={`${studio.lessonId}-${title}`}
                          text={title}
                          tag="h1"
                          textAlign="left"
                          splitType="chars"
                          delay={45}
                          duration={0.55}
                          from={{ opacity: 0, y: 14, rotateX: -25 }}
                          to={{ opacity: 1, y: 0, rotateX: 0 }}
                          rootMargin="0px"
                        />
                    </div>
                  </div>
                  <TabsList className="mode-navigation" aria-label="工作区">
                    <TabsTrigger
                      value="learn"
                      data-testid="workspace-tab-learn"
                    >
                      {mode === "learn" && (
                        <motion.span
                          aria-hidden="true"
                          className="mode-active-pill"
                          layoutId="workspace-mode"
                          transition={{
                            type: "spring",
                            bounce: 0.15,
                            duration: reducedMotion ? 0 : 0.4,
                          }}
                        />
                      )}
                      <BookOpen size={16} />
                      学习课程
                    </TabsTrigger>
                    <TabsTrigger
                      value="lab"
                      data-testid="workspace-tab-lab"
                    >
                      {mode === "lab" && (
                        <motion.span
                          aria-hidden="true"
                          className="mode-active-pill"
                          layoutId="workspace-mode"
                          transition={{
                            type: "spring",
                            bounce: 0.15,
                            duration: reducedMotion ? 0 : 0.4,
                          }}
                        />
                      )}
                      <FlaskConical size={16} />
                      实验工作台
                      {studio.running && <i className="live-indicator" />}
                    </TabsTrigger>
                  </TabsList>
                </div>
                <TabsContent
                  forceMount
                  hidden={mode !== "learn"}
                  value="learn"
                  className="mode-panel motion-safe:animate-in motion-safe:fade-in motion-safe:slide-in-from-bottom-2 motion-safe:duration-300"
                >
                  <Suspense fallback={loadingPanel}>
                    <LearningWorkspace
                      studio={studio}
                      active={mode === "learn" && !catalog && !intro}
                      onStartLab={() => {
                        setMode("lab");
                        setHasOpenedLab(true);
                      }}
                    />
                  </Suspense>
                </TabsContent>
                <TabsContent
                  forceMount
                  hidden={mode !== "lab"}
                  value="lab"
                  className="mode-panel motion-safe:animate-in motion-safe:fade-in motion-safe:slide-in-from-bottom-2 motion-safe:duration-300"
                >
                  {hasOpenedLab && (
                    <Suspense fallback={loadingPanel}>
                      <LessonExtension
                        slot="lab"
                        extensionKey={studio.detail?.ui?.lab}
                        studio={studio}
                        active={mode === "lab" && !catalog && !intro}
                        onConfigure={() => setSettings(true)}
                      >
                        <Laboratory
                          studio={studio}
                          active={mode === "lab" && !catalog && !intro}
                          onConfigure={() => setSettings(true)}
                        />
                      </LessonExtension>
                    </Suspense>
                  )}
                </TabsContent>
              </Tabs>
            )}
          </div>
        </main>
      </div>
      <ModelSettings
        open={settings}
        onOpenChange={setSettings}
        onSaved={() => {
          void studio.refreshStatus();
        }}
        triggerRef={settingsRef}
      />
    </div>
  );
}
