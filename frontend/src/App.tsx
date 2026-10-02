import { lazy, Suspense, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { useReducedMotion } from "./motion";
import ShinyText from "./components/react-bits/ShinyText";
import {
  ArrowUpRight,
  BookOpen,
  House,
  Search,
  ChevronRight,
  Layers3,
  Menu,
  Settings2,
  Waypoints,
  X,
} from "lucide-react";
import { useStudio } from "./hooks/useStudio";
import { ModelSettings } from "./components/workspace/ModelSettings";
import { ThemeSwitch } from "./components/ThemeSwitch";
import { MotionSwitch } from "./components/MotionSwitch";
import { CourseNavigation } from "./components/CourseNavigation";
import {
  CommandButton,
  CommandMenu,
  openCommandPalette,
} from "./components/command/CommandMenu";
import { Button } from "./components/ui/button";
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
const Home = lazy(() =>
  import("./components/home/Home").then((module) => ({
    default: module.Home,
  })),
);
const LessonScenes = lazy(() =>
  import("./scenes/LessonScenes").then((module) => ({
    default: module.LessonScenes,
  })),
);
const loadingPanel = (
  <div className="learn-empty" role="status">
    正在准备学习内容…
  </div>
);

export default function App() {
  const reducedMotion = useReducedMotion();
  const { t } = useTranslation(["home", "command"]);
  const studio = useStudio();
  const [catalog, setCatalog] = useState(false);
  // First visit lands on the home page; returning learners go straight to their lesson.
  const [home, setHome] = useState(() => {
    try {
      return localStorage.getItem("agent-lab-entry") !== "lesson";
    } catch {
      return true;
    }
  });
  const [intro, setIntro] = useState(false);
  const [introChapter, setIntroChapter] = useState(0);
  const [hasOpenedLesson, setHasOpenedLesson] = useState(!home);
  const [menu, setMenu] = useState(false);
  const [settings, setSettings] = useState(false);
  const settingsRef = useRef<HTMLButtonElement>(null);
  const menuRef = useRef<HTMLButtonElement>(null);
  function choose(id: string) {
    if (studio.running) return;
    studio.selectLesson(id);
    setHasOpenedLesson(true);
    setIntro(false);
    setHome(false);
    try {
      localStorage.setItem("agent-lab-entry", "lesson");
    } catch {
      /* Session navigation still works. */
    }
    setCatalog(false);
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
        className={`rail-catalog ${home ? "is-active" : ""}`}
        data-testid="app-home-button"
        aria-pressed={home}
        disabled={studio.running}
        onClick={() => {
          setHome(true);
          setCatalog(false);
          setIntro(false);
          setMenu(false);
        }}
      >
        <House size={17} />
        {t("nav")}
      </Button>
      {/* Narrow screens hide the toolbar search button; keep the palette reachable. */}
      <Button
        variant="ghost"
        className="rail-catalog rail-command"
        data-testid="app-rail-command"
        onClick={() => {
          setMenu(false);
          openCommandPalette();
        }}
      >
        <Search size={17} />
        {t("command:open")}
      </Button>
      <Button
        variant="ghost"
        className={`rail-catalog ${catalog ? "is-active" : ""}`}
        data-testid="app-curriculum-button"
        aria-pressed={catalog}
        disabled={studio.running}
        onClick={() => {
          setCatalog(true);
          setIntro(false);
          setHome(false);
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
                setHome(false);
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
        current={!intro && !catalog && !home ? studio.lessonId : undefined}
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
            setHome(false);
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
              {home
                ? t("nav")
                : intro
                  ? "开始之前"
                  : catalog
                    ? "课程地图"
                    : "基础实践"}
            </strong>
          </div>
          <div className="app-preferences">
            <CommandButton />
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
          {home && (
            <Suspense fallback={loadingPanel}>
              <Home
                lessons={studio.lessons}
                onOpenLesson={choose}
                onStartOnboarding={() => {
                  setHome(false);
                  setIntro(true);
                  setIntroChapter(0);
                  window.scrollTo({ top: 0 });
                }}
                onOpenMap={() => {
                  setHome(false);
                  setCatalog(true);
                }}
              />
            </Suspense>
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
          <div hidden={catalog || intro || home}>
            {hasOpenedLesson && (
              <Suspense fallback={loadingPanel}>
                <LessonScenes
                  studio={studio}
                  visible={!catalog && !intro && !home}
                  onConfigure={() => setSettings(true)}
                />
              </Suspense>
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
      <CommandMenu
        studio={studio}
        lessonOpen={!intro && !catalog}
        onLesson={choose}
        onIntro={(chapter) => {
          setIntro(true);
          setIntroChapter(chapter);
          setCatalog(false);
          setMenu(false);
          window.scrollTo({ top: 0 });
        }}
        onMap={() => {
          setCatalog(true);
          setIntro(false);
          setMenu(false);
        }}
        onSettings={() => setSettings(true)}
      />
    </div>
  );
}
