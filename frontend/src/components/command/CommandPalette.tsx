import { useEffect, useRef, useState, type ReactNode } from "react";
import { Command } from "cmdk";
import { useTranslation } from "react-i18next";
import {
  BookOpen,
  Check,
  Compass,
  Download,
  Map as MapIcon,
  Monitor,
  Search,
  Settings2,
} from "lucide-react";
import { jsonFetch } from "../../api";
import type { Onboarding } from "../../content/types.gen";
import type { StudioState } from "../../hooks/useStudio";
import type { CurriculumData, Lesson } from "../../types";
import { formatLessonNumber } from "../../lib/lessonIds";
import { requestScene } from "../../scenes/LessonScenes";
import { sceneIds } from "../../scenes/types";
import {
  setThemePreference,
  themePreferenceNow,
  themePreferences,
} from "../ThemeSwitch";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogTitle,
} from "../ui/dialog";
import { paletteFilter } from "./filter";
import { useReturnFocus } from "./returnFocus";

export interface CommandPaletteProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  studio: StudioState;
  /** The current lesson page is on screen (not onboarding or the map). */
  lessonOpen: boolean;
  onLesson: (id: string) => void;
  onIntro: (chapter: number) => void;
  onMap: () => void;
  onSettings: () => void;
}

type PaletteLesson = Pick<
  Lesson,
  "id" | "number" | "aliases" | "title" | "available"
>;

/** ⌘K palette over lessons, scenes, onboarding chapters and settings (cmdk). */
export function CommandPalette({
  open,
  onOpenChange,
  studio,
  lessonOpen,
  onLesson,
  onIntro,
  onMap,
  onSettings,
}: CommandPaletteProps) {
  const { t } = useTranslation("command");
  const { t: tLesson } = useTranslation("lesson");
  const { t: tCommon } = useTranslation();
  const [search, setSearch] = useState("");
  const [chapters, setChapters] = useState<string[]>([]);
  const [planned, setPlanned] = useState<PaletteLesson[]>([]);
  // Whether closing should return focus to where the palette opened from.
  const restoreFocus = useRef(true);
  const focus = useReturnFocus();

  useEffect(() => {
    const abort = new AbortController();
    jsonFetch<Onboarding>("/api/onboarding", { signal: abort.signal })
      .then((value) => {
        if (!abort.signal.aborted)
          setChapters(value.chapters.map((chapter) => chapter.title));
      })
      .catch(() => {
        /* Onboarding entries are simply absent if the content is unavailable. */
      });
    // Planned lessons live only in the curriculum; they are listed, never run.
    jsonFetch<CurriculumData>("/api/curriculum", { signal: abort.signal })
      .then((value) => {
        if (!abort.signal.aborted)
          setPlanned(
            value.lessons
              .filter((lesson) => lesson.status === "planned")
              .map((lesson) => ({ ...lesson, available: false })),
          );
      })
      .catch(() => {
        /* Runnable lessons from the studio are still listed. */
      });
    return () => abort.abort();
  }, []);

  useEffect(() => {
    if (open) setSearch("");
  }, [open]);

  const run =
    (action: () => void, { keepFocus = true } = {}) =>
    () => {
      restoreFocus.current = keepFocus;
      onOpenChange(false);
      action();
    };

  const running = studio.running;
  const detail = studio.detail;
  const theme = themePreferenceNow();
  const lessons: PaletteLesson[] = [
    ...studio.lessons,
    ...planned.filter(
      (lesson) => !studio.lessons.some((item) => item.id === lesson.id),
    ),
  ].sort((a, b) => a.number - b.number);

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent
        className="command-dialog"
        data-testid="command-palette"
        data-command-palette=""
        showCloseButton={false}
        // Esc closes only the palette, not the guide bar listening on window.
        onEscapeKeyDown={(event) => event.stopPropagation()}
        onOpenAutoFocus={focus.onOpenAutoFocus}
        onCloseAutoFocus={(event) => {
          focus.onCloseAutoFocus(event, restoreFocus.current);
          restoreFocus.current = true;
        }}
      >
        <DialogTitle className="sr-only">{t("title")}</DialogTitle>
        <DialogDescription className="sr-only">
          {t("description")}
        </DialogDescription>
        <Command label={t("title")} loop filter={paletteFilter}>
          <div className="command-input-row">
            <Search size={16} aria-hidden="true" />
            <Command.Input
              value={search}
              onValueChange={setSearch}
              placeholder={t("placeholder")}
              data-testid="command-input"
            />
          </div>
          <Command.List className="command-list" data-testid="command-list">
            <Command.Empty className="command-empty">
              {t("empty")}
            </Command.Empty>

            <Command.Group heading={t("groups.lessons")}>
              {lessons.map((lesson) => {
                const number = formatLessonNumber(lesson.number);
                const current = lessonOpen && lesson.id === studio.lessonId;
                return (
                  <Command.Item
                    key={lesson.id}
                    value={`lesson ${lesson.id}`}
                    keywords={[
                      lesson.title,
                      lesson.id,
                      ...lesson.aliases,
                      String(lesson.number),
                      number,
                    ]}
                    disabled={!lesson.available || running}
                    onSelect={run(() => onLesson(lesson.id))}
                    data-testid="command-lesson"
                    data-lesson-id={lesson.id}
                    data-status={lesson.available ? "available" : "planned"}
                  >
                    <span className="command-number">{number}</span>
                    <span className="command-label">{lesson.title}</span>
                    {!lesson.available ? (
                      <span className="command-badge">
                        {t("lesson.planned")}
                      </span>
                    ) : running ? (
                      <span className="command-badge">
                        {t("lesson.running")}
                      </span>
                    ) : current ? (
                      <Current label={t("current")} />
                    ) : null}
                  </Command.Item>
                );
              })}
            </Command.Group>

            {lessonOpen && detail && (
              <Command.Group
                heading={t("groups.scenes", { title: detail.title })}
              >
                {sceneIds.map((id) => {
                  const label = tLesson(`scenes.${id}`);
                  return (
                    <Item
                      key={id}
                      value={`scene ${id}`}
                      keywords={[label, tLesson(`sceneHint.${id}`)]}
                      onSelect={run(() => requestScene(id))}
                      testId={`command-scene-${id}`}
                      icon={<Compass size={15} />}
                      hint={tLesson(`sceneHint.${id}`)}
                    >
                      {t("scene", { scene: label })}
                    </Item>
                  );
                })}
              </Command.Group>
            )}

            <Command.Group heading={t("groups.navigate")}>
              {chapters.map((title, index) => (
                <Item
                  key={`intro-${index}`}
                  value={`intro ${index}`}
                  keywords={[title]}
                  disabled={running}
                  onSelect={run(() => onIntro(index))}
                  testId={`command-intro-${index}`}
                  icon={<BookOpen size={15} />}
                >
                  {t("intro", { title })}
                </Item>
              ))}
              <Item
                value="map"
                keywords={[t("map")]}
                disabled={running}
                onSelect={run(onMap)}
                testId="command-map"
                icon={<MapIcon size={15} />}
              >
                {t("map")}
              </Item>
            </Command.Group>

            <Command.Group heading={t("groups.preferences")}>
              {themePreferences.map((value) => {
                const label = t("theme", { value: tCommon(`theme.${value}`) });
                return (
                  <Item
                    key={`theme-${value}`}
                    value={`theme ${value}`}
                    keywords={[label, tCommon("theme.label")]}
                    onSelect={run(() => setThemePreference(value))}
                    testId={`command-theme-${value}`}
                    icon={<Monitor size={15} />}
                    current={theme === value ? t("current") : undefined}
                  >
                    {label}
                  </Item>
                );
              })}
              <Item
                value="settings"
                keywords={[t("settings"), studio.status?.provider_label ?? ""]}
                onSelect={run(onSettings, { keepFocus: false })}
                testId="command-settings"
                icon={<Settings2 size={15} />}
              >
                {t("settings")}
              </Item>
            </Command.Group>

            {studio.events.length > 0 && !running && (
              <Command.Group heading={t("groups.run")}>
                <Item
                  value="download"
                  keywords={[t("download")]}
                  onSelect={run(studio.download)}
                  testId="command-download"
                  icon={<Download size={15} />}
                >
                  {t("download")}
                </Item>
              </Command.Group>
            )}
          </Command.List>
        </Command>
      </DialogContent>
    </Dialog>
  );
}

function Item({
  value,
  keywords,
  disabled,
  onSelect,
  testId,
  icon,
  hint,
  current,
  children,
}: {
  value: string;
  keywords: string[];
  disabled?: boolean;
  onSelect: () => void;
  testId: string;
  icon: ReactNode;
  hint?: string;
  current?: string;
  children: ReactNode;
}) {
  return (
    <Command.Item
      value={value}
      keywords={keywords}
      disabled={disabled}
      onSelect={onSelect}
      data-testid={testId}
    >
      <span className="command-icon" aria-hidden="true">
        {icon}
      </span>
      <span className="command-label">{children}</span>
      {hint && <span className="command-hint">{hint}</span>}
      {current && <Current label={current} />}
    </Command.Item>
  );
}

function Current({ label }: { label: string }) {
  return (
    <span className="command-current">
      <Check size={14} aria-hidden="true" />
      <span className="sr-only">{label}</span>
    </span>
  );
}
