import type { CSSProperties } from "react";
import { useTranslation } from "react-i18next";
import { motion } from "motion/react";
import {
  Code2,
  FlaskConical,
  Lightbulb,
  ListChecks,
  Radio,
  type LucideIcon,
} from "lucide-react";
import { useReducedMotion } from "../../motion";
import GlareHover from "../react-bits/GlareHover";

const steps: { key: "concept" | "code" | "evidence" | "experiment" | "check"; icon: LucideIcon; color: string }[] = [
  { key: "concept", icon: Lightbulb, color: "#b98aff" },
  { key: "code", icon: Code2, color: "#6d5dfc" },
  { key: "evidence", icon: Radio, color: "#49dec6" },
  { key: "experiment", icon: FlaskConical, color: "#ff9473" },
  { key: "check", icon: ListChecks, color: "#6fd39a" },
];

/** The course rhythm: concept → minimal code → run evidence → experiment → self-check. */
export function HomeMethod() {
  const { t } = useTranslation("home");
  const reduced = useReducedMotion();
  return (
    <section
      className="home-section home-method"
      aria-labelledby="home-method-title"
    >
      <header className="home-section-head">
        <p className="home-eyebrow">{t("method.kicker")}</p>
        <h2 id="home-method-title">{t("method.title")}</h2>
        <p>{t("method.lead")}</p>
      </header>
      <div className="home-method-track">
        <motion.span
          className="home-method-line"
          aria-hidden="true"
          initial={reduced ? false : { scaleX: 0 }}
          whileInView={reduced ? undefined : { scaleX: 1 }}
          viewport={{ once: true, amount: 0.6 }}
          transition={{ duration: 1.4, ease: [0.16, 1, 0.3, 1] }}
        />
        <ol className="home-method-steps">
          {steps.map(({ key, icon: Icon, color }, index) => (
            <motion.li
              key={key}
              style={{ "--step": color } as CSSProperties}
              initial={reduced ? false : { opacity: 0, y: 30, filter: "blur(8px)" }}
              whileInView={
                reduced ? undefined : { opacity: 1, y: 0, filter: "blur(0px)" }
              }
              viewport={{ once: true, amount: 0.4 }}
              transition={{ duration: 0.7, delay: 0.15 + index * 0.12, ease: [0.16, 1, 0.3, 1] }}
            >
              <GlareHover className="home-method-card" glareOpacity={0.22}>
                <span className="home-method-index" aria-hidden="true">
                  {String(index + 1).padStart(2, "0")}
                </span>
                <span className="home-method-icon" aria-hidden="true">
                  <Icon size={20} />
                </span>
                <h3>{t(`method.${key}`)}</h3>
                <p>{t(`method.${key}Help`)}</p>
              </GlareHover>
            </motion.li>
          ))}
        </ol>
      </div>
    </section>
  );
}
