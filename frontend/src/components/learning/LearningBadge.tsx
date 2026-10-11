import {
  Suspense,
  lazy,
  useEffect,
  useMemo,
  useState,
  useSyncExternalStore,
  type ReactNode,
} from "react";
import { useTranslation } from "react-i18next";
import {
  EffectBoundary,
  useMotionBudget,
  useReducedMotion,
} from "../../motion";
import { scenes, type LessonProgress } from "../../progress";
import Shuffle from "../react-bits/Shuffle";
import { fitText, type FitStep } from "./badgeText";

const Lanyard = lazy(() => import("../react-bits/Lanyard"));

/** Desktop with a fine pointer: the only place the 3D badge is offered. */
const desktopQuery = "(min-width: 1100px) and (pointer: fine)";
const subscribe = (callback: () => void) => {
  const media = window.matchMedia(desktopQuery);
  media.addEventListener("change", callback);
  return () => media.removeEventListener("change", callback);
};
const useDesktop = () =>
  useSyncExternalStore(
    subscribe,
    () => window.matchMedia(desktopQuery).matches,
    () => false,
  );

interface Face {
  brand: string;
  lesson: string;
  title: string;
  facts: { label: string; value: string }[];
  footer: string;
}

/** Logical size of the card face; the canvas is this times the pixel scale. */
const FACE_W = 720;
const FACE_H = 1000;

/**
 * Card face drawn on a canvas from real numbers (Lanyard's front image).
 * Drawn at least 2x (more on high-DPI screens) so the text stays crisp once
 * the card is mapped onto the 3D model.
 */
function drawFace(face: Face) {
  const scale = Math.min(2.5, Math.max(2, window.devicePixelRatio || 1));
  const canvas = document.createElement("canvas");
  canvas.width = Math.round(FACE_W * scale);
  canvas.height = Math.round(FACE_H * scale);
  const ctx = canvas.getContext("2d");
  if (!ctx) return null;
  ctx.scale(scale, scale);
  const family = getComputedStyle(document.body).fontFamily || "sans-serif";
  const bg = ctx.createLinearGradient(0, 0, FACE_W, FACE_H);
  bg.addColorStop(0, "#1f1748");
  bg.addColorStop(0.55, "#0f0c1e");
  bg.addColorStop(1, "#08281f");
  ctx.fillStyle = bg;
  ctx.fillRect(0, 0, FACE_W, FACE_H);
  const glow = ctx.createRadialGradient(560, 140, 10, 560, 140, 440);
  glow.addColorStop(0, "rgba(185,138,255,0.5)");
  glow.addColorStop(1, "rgba(185,138,255,0)");
  ctx.fillStyle = glow;
  ctx.fillRect(0, 0, FACE_W, FACE_H);
  // Fine grid, like the hero bands.
  ctx.strokeStyle = "rgba(255,255,255,0.05)";
  ctx.lineWidth = 1;
  for (let x = 0; x <= FACE_W; x += 48) {
    ctx.beginPath();
    ctx.moveTo(x, 0);
    ctx.lineTo(x, FACE_H);
    ctx.stroke();
  }
  for (let y = 0; y <= FACE_H; y += 48) {
    ctx.beginPath();
    ctx.moveTo(0, y);
    ctx.lineTo(FACE_W, y);
    ctx.stroke();
  }
  const left = 72;
  const width = FACE_W - left * 2;
  /** Fit text into `maxWidth`, shrinking and wrapping (by word, or by character for CJK). */
  const fit = (text: string, weight: number, maxWidth: number, steps: FitStep[]) =>
    fitText(text, maxWidth, steps, (value, size) => {
      ctx.font = `${weight} ${size}px ${family}`;
      return ctx.measureText(value).width;
    });
  ctx.textBaseline = "alphabetic";
  ctx.fillStyle = "#8ff0de";
  const brand = fit(face.brand.split("").join(" "), 800, width, [
    { size: 32, maxLines: 1 },
  ]);
  ctx.font = `800 ${brand.size}px ${family}`;
  ctx.fillText(brand.lines[0] ?? "", left, 150);
  ctx.fillStyle = "#d9cfff";
  const lesson = fit(face.lesson, 700, width, [
    { size: 46, maxLines: 1 },
    { size: 38, maxLines: 1 },
  ]);
  ctx.font = `700 ${lesson.size}px ${family}`;
  ctx.fillText(lesson.lines[0] ?? "", left, 252);
  // Title: shrink until it fits in the band above the divider (two lines at
  // full size, up to four when small); an ellipsis only if even that is too long.
  ctx.fillStyle = "#ffffff";
  const title = fit(face.title, 800, width, [
    { size: 80, maxLines: 2 },
    { size: 68, maxLines: 2 },
    { size: 58, maxLines: 3 },
    { size: 50, maxLines: 3 },
    { size: 44, maxLines: 4 },
  ]);
  ctx.font = `800 ${title.size}px ${family}`;
  title.lines.forEach((text, index) => {
    ctx.fillText(text, left, 290 + title.size * (0.8 + index * 1.15));
  });
  ctx.fillStyle = "rgba(255,255,255,0.14)";
  ctx.fillRect(left, 520, width, 2);
  const accent = ["#b98aff", "#49dec6", "#ff9473"];
  const labelLeft = left + 250;
  const labelWidth = FACE_W - left - labelLeft;
  face.facts.forEach((fact, index) => {
    const y = 630 + index * 112;
    ctx.fillStyle = accent[index];
    ctx.fillRect(left, y - 66, 8, 84);
    const value = fit(fact.value, 800, labelLeft - left - 34 - 16, [
      { size: 84, maxLines: 1 },
      { size: 64, maxLines: 1 },
      { size: 48, maxLines: 1 },
    ]);
    ctx.font = `800 ${value.size}px ${family}`;
    ctx.fillText(value.lines[0] ?? "", left + 34, y + 10);
    ctx.fillStyle = "rgba(244,241,255,0.92)";
    // Labels: one line if it fits at a readable size, otherwise two lines
    // centred on the row.
    const label = fit(fact.label, 700, labelWidth, [
      { size: 42, maxLines: 1 },
      { size: 36, maxLines: 1 },
      { size: 34, maxLines: 2 },
      { size: 30, maxLines: 2 },
    ]);
    ctx.font = `700 ${label.size}px ${family}`;
    const lineHeight = label.size * 1.15;
    const first = y - 2 - ((label.lines.length - 1) * lineHeight) / 2;
    label.lines.forEach((text, line) => {
      ctx.fillText(text, labelLeft, first + line * lineHeight);
    });
  });
  ctx.fillStyle = "rgba(236,232,255,0.7)";
  const footer = fit(face.footer, 600, width, [
    { size: 30, maxLines: 1 },
    { size: 26, maxLines: 1 },
  ]);
  ctx.font = `600 ${footer.size}px ${family}`;
  ctx.fillText(footer.lines[0] ?? "", left, 952);
  return canvas.toDataURL("image/png");
}

function StaticBadge({ face }: { face: Face }) {
  return (
    <div className="learning-badge-static" data-testid="learning-badge-static">
      <span className="learning-badge-brand" aria-hidden="true">
        {face.brand}
      </span>
      <span className="learning-badge-lesson">{face.lesson}</span>
      <strong className="learning-badge-title">{face.title}</strong>
      <dl>
        {face.facts.map((fact) => (
          <div key={fact.label}>
            <dt>{fact.label}</dt>
            <dd>{fact.value}</dd>
          </div>
        ))}
      </dl>
      <small>{face.footer}</small>
    </div>
  );
}

/** WebGL lanyard when the budget allows; the static card otherwise. */
function BadgeStage({ face }: { face: Face }) {
  const { t } = useTranslation("lesson", { keyPrefix: "review.badge" });
  const { ref, granted, active } = useMotionBudget<HTMLDivElement>("webgl", {
    margin: "120px",
  });
  const [image, setImage] = useState<string | null>(null);
  const signature = JSON.stringify(face);
  useEffect(() => {
    if (granted) setImage(drawFace(face));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [granted, signature]);
  const live = granted && image;
  return (
    <div
      ref={ref}
      className="learning-badge-stage"
      data-live={live ? true : undefined}
    >
      {live ? (
        <>
          <dl className="sr-only" aria-label={t("facts")}>
            {face.facts.map((fact) => (
              <div key={fact.label}>
                <dt>{fact.label}</dt>
                <dd>{fact.value}</dd>
              </div>
            ))}
          </dl>
          <EffectBoundary fallback={<StaticBadge face={face} />}>
            <Suspense fallback={<StaticBadge face={face} />}>
              <div aria-hidden="true" className="learning-badge-canvas">
                <Lanyard
                  frontImage={image}
                  active={active}
                  anchorY={4.5}
                  fov={13}
                  dpr={[1.5, 2.5]}
                />
              </div>
            </Suspense>
          </EffectBoundary>
        </>
      ) : (
        <StaticBadge face={face} />
      )}
    </div>
  );
}

/**
 * 回顾页的本机学习徽章：卡面只写这台设备的真实数字（打开过的场景、
 * 完成的运行、自测作答次数）。桌面 + 完整动效 + 浏览器支持 WebGL 时是可拖动的
 * 3D 挂牌（懒加载），否则是同内容的静态卡片。children 放在说明下方。
 */
export function LearningBadge({
  number,
  title,
  record,
  quizAttempts,
  children,
}: {
  number: string;
  title: string;
  record: LessonProgress | undefined;
  quizAttempts: number;
  children?: ReactNode;
}) {
  const { t } = useTranslation("lesson", { keyPrefix: "review.badge" });
  const desktop = useDesktop();
  const reduced = useReducedMotion();
  const opened = scenes.filter((scene) => record?.scenes[scene]).length;
  const runs = record?.runs.count ?? 0;
  const date = (record?.lastOpenedAt ?? "").slice(0, 10);
  const face = useMemo<Face>(
    () => ({
      brand: t("brand"),
      lesson: t("lesson", { number }),
      title,
      facts: [
        { label: t("scenes"), value: `${opened}/${scenes.length}` },
        { label: t("runs"), value: String(runs) },
        { label: t("quiz"), value: String(quizAttempts) },
      ],
      footer: t("footer", { date: date || "—" }),
    }),
    [t, number, title, opened, runs, quizAttempts, date],
  );
  return (
    <section className="learning-badge" data-testid="learning-badge">
      <div className="learning-badge-main">
        <div className="learning-badge-copy">
          <span className="reading-eyebrow">
            <Shuffle text={t("kicker")} />
          </span>
          <h3>{t("title")}</h3>
          <p>{desktop && !reduced ? t("hint") : t("staticHint")}</p>
        </div>
        {children}
      </div>
      {desktop ? <BadgeStage face={face} /> : <StaticBadge face={face} />}
    </section>
  );
}
