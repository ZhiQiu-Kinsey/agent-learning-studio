import {
  lazy,
  Suspense,
  useEffect,
  useRef,
  useState,
  type ReactNode,
  type Ref,
} from "react";
import { useTranslation } from "react-i18next";
import { AnimatePresence, motion, useAnimate } from "motion/react";
import { ChevronRight, Menu, Settings2, X } from "lucide-react";
import { motionTokens, useReducedMotion } from "./motion";
import { useStudio } from "./hooks/useStudio";
import { ModelSettings } from "./components/workspace/ModelSettings";
import { ThemeSwitch } from "./components/ThemeSwitch";
import {
  CommandButton,
  CommandMenu,
  openCommandPalette,
} from "./components/command/CommandMenu";
import { RailNavigation } from "./components/shell/RailNavigation";
import { ShellAmbient } from "./components/shell/ShellAmbient";
import ClickSparkLayer from "./components/react-bits/ClickSparkLayer";
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

type View = "home" | "intro" | "catalog" | "lesson";

// Page change: the old page lifts away while the new one rises out of a blur.
const pageEnter = { opacity: 0, y: 14, filter: "blur(8px)" };
const pageShown = {
  opacity: 1,
  y: 0,
  filter: "blur(0px)",
  transition: { duration: 0.42, ease: motionTokens.ease },
  transitionEnd: { filter: "none" },
};
const pageExit = {
  opacity: 0,
  y: -10,
  filter: "blur(6px)",
  transition: { duration: 0.2, ease: motionTokens.ease },
};

// AnimatePresence (popLayout) measures the leaving page through this ref.
function PageView({
  ref,
  name,
  reduced,
  children,
}: {
  ref?: Ref<HTMLDivElement>;
  name: View;
  reduced: boolean;
  children: ReactNode;
}) {
  return (
    <motion.div
      ref={ref}
      className="page-view"
      data-view={name}
      initial={reduced ? false : pageEnter}
      animate={reduced ? undefined : pageShown}
      exit={reduced ? undefined : pageExit}
    >
      {children}
    </motion.div>
  );
}

export default function App() {
  const reducedMotion = useReducedMotion();
  const { t } = useTranslation(["common", "home"]);
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
  const [scrolled, setScrolled] = useState(false);
  const settingsRef = useRef<HTMLButtonElement>(null);
  const menuRef = useRef<HTMLButtonElement>(null);
  const shellRef = useRef<HTMLDivElement>(null);
  const [lessonScope, animateLesson] = useAnimate<HTMLDivElement>();
  const view: View = home
    ? "home"
    : intro
      ? "intro"
      : catalog
        ? "catalog"
        : "lesson";
  const loadingPanel = (
    <div className="learn-empty" role="status">
      {t("shell.loading")}
    </div>
  );

  useEffect(() => {
    const update = () => setScrolled(window.scrollY > 6);
    update();
    window.addEventListener("scroll", update, { passive: true });
    return () => window.removeEventListener("scroll", update);
  }, []);

  // LessonScenes stays mounted (hidden) to keep its state; only its container
  // replays the page entrance when the lesson comes back on screen.
  useEffect(() => {
    const el = lessonScope.current;
    if (view !== "lesson" || reducedMotion || !el) return;
    const controls = animateLesson(
      el,
      {
        opacity: [0, 1],
        y: [14, 0],
        filter: ["blur(8px)", "blur(0px)"],
      },
      { duration: 0.42, ease: motionTokens.ease },
    );
    controls.then(() => {
      el.style.filter = "";
      el.style.transform = "";
    });
    return () => controls.stop();
  }, [view, reducedMotion, animateLesson, lessonScope]);

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
  const navigationProps = {
    view,
    introChapter,
    running: studio.running,
    lessons: studio.lessons,
    lessonId: studio.lessonId,
    onHome: () => {
      setHome(true);
      setCatalog(false);
      setIntro(false);
      setMenu(false);
    },
    onCommand: () => {
      setMenu(false);
      openCommandPalette();
    },
    onCatalog: () => {
      setCatalog(true);
      setIntro(false);
      setHome(false);
      setMenu(false);
    },
    onIntro: (index: number) => {
      setIntro(true);
      setHome(false);
      setIntroChapter(index);
      setCatalog(false);
      setMenu(false);
      window.scrollTo({ top: 0 });
    },
    onSelect: choose,
  };
  const location = t(
    view === "home"
      ? "home:nav"
      : view === "intro"
        ? "shell.breadcrumb.intro"
        : view === "catalog"
          ? "shell.breadcrumb.map"
          : "shell.breadcrumb.lesson",
  );
  const ready = !!studio.status?.config_ready;
  return (
    <div className="studio-shell experience-shell" ref={shellRef}>
      <ShellAmbient />
      <ClickSparkLayer scope={shellRef} />
      <motion.aside className="course-rail" layoutScroll>
        <RailNavigation id="rail" {...navigationProps} />
      </motion.aside>
      <Sheet open={menu} onOpenChange={setMenu}>
        <SheetContent
          side="left"
          className="course-sheet"
          onCloseAutoFocus={(e) => {
            e.preventDefault();
            menuRef.current?.focus();
          }}
        >
          <SheetTitle className="sr-only">{t("shell.menu.title")}</SheetTitle>
          <SheetDescription className="sr-only">
            {t("shell.menu.description")}
          </SheetDescription>
          <motion.div className="course-sheet-scroll" layoutScroll>
            <RailNavigation id="sheet" {...navigationProps} />
          </motion.div>
        </SheetContent>
      </Sheet>
      <div className="studio-body">
        <header className="app-toolbar" data-scrolled={scrolled || undefined}>
          <div className="app-location">
            <Button
              ref={menuRef}
              variant="ghost"
              size="icon"
              className="open-course-menu"
              data-testid="app-open-course-menu"
              aria-label={t("shell.menu.open")}
              onClick={() => setMenu(true)}
            >
              <Menu size={18} />
            </Button>
            <span>{t("shell.breadcrumb.root")}</span>
            <ChevronRight size={13} aria-hidden="true" />
            <span className="app-location-current">
              <AnimatePresence mode="popLayout" initial={false}>
                <motion.strong
                  key={location}
                  initial={
                    reducedMotion
                      ? false
                      : { opacity: 0, y: 10, filter: "blur(4px)" }
                  }
                  animate={{ opacity: 1, y: 0, filter: "blur(0px)" }}
                  exit={
                    reducedMotion
                      ? undefined
                      : { opacity: 0, y: -10, filter: "blur(4px)" }
                  }
                  transition={{ duration: 0.28, ease: motionTokens.ease }}
                >
                  {location}
                </motion.strong>
              </AnimatePresence>
            </span>
          </div>
          <div className="app-preferences">
            <CommandButton />
            <ThemeSwitch />
            <Button
              ref={settingsRef}
              variant="outline"
              className="connection-button"
              data-testid="app-connection-button"
              data-ready={ready || undefined}
              title={t("shell.connection.title")}
              onClick={() => setSettings(true)}
            >
              <i className={ready ? "is-ready" : ""} aria-hidden="true" />
              <span>
                {studio.status?.provider_label || t("shell.connection.connect")}
              </span>
              <Settings2 size={15} aria-hidden="true" />
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
                aria-label={t("shell.dismissError")}
                onClick={() => studio.setError("")}
              >
                <X size={16} />
              </Button>
            </div>
          )}
          <AnimatePresence mode="popLayout" initial={false}>
            {view === "home" && (
              <PageView key="home" name="home" reduced={reducedMotion}>
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
              </PageView>
            )}
            {view === "intro" && (
              <PageView key="intro" name="intro" reduced={reducedMotion}>
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
              </PageView>
            )}
            {view === "catalog" && (
              <PageView key="catalog" name="catalog" reduced={reducedMotion}>
                <Suspense fallback={loadingPanel}>
                  <Curriculum onSelectLesson={choose} />
                </Suspense>
              </PageView>
            )}
          </AnimatePresence>
          <div
            ref={lessonScope}
            className="page-view"
            data-view="lesson"
            hidden={view !== "lesson"}
          >
            {hasOpenedLesson && (
              <Suspense fallback={loadingPanel}>
                <LessonScenes
                  studio={studio}
                  visible={view === "lesson"}
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
        lessonOpen={view === "lesson"}
        onLesson={choose}
        onIntro={(chapter) => {
          setHome(false);
          setIntro(true);
          setIntroChapter(chapter);
          setCatalog(false);
          setMenu(false);
          window.scrollTo({ top: 0 });
        }}
        onMap={() => {
          setHome(false);
          setCatalog(true);
          setIntro(false);
          setMenu(false);
        }}
        onSettings={() => setSettings(true)}
      />
    </div>
  );
}
