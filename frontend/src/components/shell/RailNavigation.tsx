import type { PointerEvent } from "react";
import { useTranslation } from "react-i18next";
import {
  ArrowUpRight,
  BookOpen,
  ChevronRight,
  House,
  Layers3,
  Search,
  Waypoints,
} from "lucide-react";
import { useReducedMotion } from "../../motion";
import type { Lesson } from "../../types";
import { CourseNavigation } from "../CourseNavigation";
import ShinyText from "../react-bits/ShinyText";
import { Button } from "../ui/button";
import { RailGroup, RailItem } from "./Rail";

const preludeKeys = ["preface", "agent", "route", "workbench"] as const;

export interface RailNavigationProps {
  /** LayoutGroup id: the desktop rail and the mobile sheet animate separately. */
  id: string;
  view: "home" | "intro" | "catalog" | "lesson";
  introChapter: number;
  running: boolean;
  lessons: Lesson[];
  lessonId?: string;
  onHome: () => void;
  onCommand: () => void;
  onCatalog: () => void;
  onIntro: (chapter: number) => void;
  onSelect: (id: string) => void;
}

/** Sidebar content shared by the fixed rail and the narrow-screen sheet. */
export function RailNavigation({
  id,
  view,
  introChapter,
  running,
  lessons,
  lessonId,
  onHome,
  onCommand,
  onCatalog,
  onIntro,
  onSelect,
}: RailNavigationProps) {
  const { t } = useTranslation(["common", "home", "command"]);
  const reduced = useReducedMotion();
  return (
    <RailGroup id={id}>
      <div className="rail-brand">
        <span className="rail-brand-mark" aria-hidden="true">
          <i className="rail-brand-halo" />
          <i className="rail-brand-core">
            <Waypoints size={21} />
          </i>
        </span>
        <div>
          <ShinyText
            text="Agent Lab"
            color="var(--text)"
            shineColor="var(--rail-shine)"
            speed={3}
            delay={3}
            disabled={!!reduced}
          />
          <small>{t("shell.brandTagline")}</small>
        </div>
      </div>
      <div className="rail-primary">
        <RailItem
          itemKey="home"
          active={view === "home"}
          className="rail-catalog"
          data-testid="app-home-button"
          aria-pressed={view === "home"}
          disabled={running}
          onClick={onHome}
        >
          <House size={17} aria-hidden="true" />
          <span className="rail-label">{t("home:nav")}</span>
        </RailItem>
        {/* Narrow screens hide the toolbar search button; keep the palette reachable. */}
        <RailItem
          itemKey="command"
          className="rail-catalog rail-command"
          data-testid="app-rail-command"
          onClick={onCommand}
        >
          <Search size={17} aria-hidden="true" />
          <span className="rail-label">{t("command:open")}</span>
        </RailItem>
        <RailItem
          itemKey="catalog"
          active={view === "catalog"}
          className="rail-catalog"
          data-testid="app-curriculum-button"
          aria-pressed={view === "catalog"}
          disabled={running}
          onClick={onCatalog}
        >
          <Layers3 size={17} aria-hidden="true" />
          <span className="rail-label">{t("shell.curriculum")}</span>
          <ArrowUpRight size={15} aria-hidden="true" className="rail-trail" />
        </RailItem>
      </div>
      <div className="nav-prelude">
        <span className="course-tree-heading">
          {t("shell.prelude.title")} <small>{t("shell.prelude.eyebrow")}</small>
        </span>
        {preludeKeys.map((key, index) => {
          const active = view === "intro" && introChapter === index;
          return (
            <RailItem
              key={key}
              itemKey={`intro-${index}`}
              active={active}
              className="nav-prelude-link"
              aria-current={active ? "page" : undefined}
              disabled={running}
              onClick={() => onIntro(index)}
            >
              <span>0{index + 1}</span>
              {t(`shell.prelude.${key}`)}
              <ChevronRight size={12} aria-hidden="true" />
            </RailItem>
          );
        })}
      </div>
      <CourseNavigation
        lessons={lessons}
        current={view === "lesson" ? lessonId : undefined}
        disabled={running}
        onSelect={onSelect}
      />
      <div
        className="rail-next"
        onPointerMove={(event: PointerEvent<HTMLDivElement>) => {
          if (reduced) return;
          const box = event.currentTarget.getBoundingClientRect();
          event.currentTarget.style.setProperty(
            "--spot-x",
            `${event.clientX - box.left}px`,
          );
          event.currentTarget.style.setProperty(
            "--spot-y",
            `${event.clientY - box.top}px`,
          );
        }}
      >
        <span className="rail-next-border" aria-hidden="true" />
        <span className="rail-next-spot" aria-hidden="true" />
        <BookOpen size={18} aria-hidden="true" />
        <strong>{t("shell.next.title")}</strong>
        <p>{t("shell.next.body")}</p>
        <Button variant="ghost" disabled={running} onClick={onCatalog}>
          {t("shell.next.action")} <ChevronRight size={14} aria-hidden="true" />
        </Button>
      </div>
      <div className="rail-footer">
        <i aria-hidden="true" />
        {t("shell.footer.title")}
        <span>{t("shell.footer.stack")}</span>
      </div>
    </RailGroup>
  );
}
