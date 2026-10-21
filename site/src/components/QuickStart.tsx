import { useTranslation } from "react-i18next";
import { ArrowUpRight, KeyRound, Laptop, ShieldAlert } from "lucide-react";
import FadeContent from "@studio/components/react-bits/FadeContent";
import { LINKS } from "../links";
import { Section } from "./Section";
import { useSiteLocale } from "./useSiteLocale";

// Commands from the repository README (Quick start); code reads the same in every language.
const COMMANDS = [
  ["$", "git clone https://github.com/ZhiQiu-Kinsey/agent-learning-studio.git"],
  ["$", "cd agent-learning-studio"],
  ["$", "uv sync --dev"],
  ["$", "npm --prefix frontend ci"],
  ["$", "npm --prefix frontend run build"],
  ["$", ".venv/bin/python run_web.py"],
] as const;

export function QuickStart() {
  const { t } = useTranslation("site", { keyPrefix: "start" });
  const locale = useSiteLocale();
  const notes = [
    { id: "keys", Icon: KeyRound },
    { id: "bind", Icon: Laptop },
    { id: "sandbox", Icon: ShieldAlert },
  ] as const;
  return (
    <Section id="start" eyebrow={t("eyebrow")} title={t("title")} lead={t("lead")}>
      <div className="site-start">
        <FadeContent className="site-terminal">
          <div className="site-window-bar" aria-hidden="true">
            <i />
            <i />
            <i />
            <span>bash</span>
          </div>
          <pre tabIndex={0}>
            <code>
              {COMMANDS.map(([prompt, command]) => (
                <span key={command} className="site-terminal-line">
                  <span className="site-terminal-prompt" aria-hidden="true">
                    {prompt}
                  </span>
                  {command}
                  {"\n"}
                </span>
              ))}
            </code>
          </pre>
          <p className="site-terminal-note">{t("windows")}</p>
        </FadeContent>
        <ul className="site-notes">
          {notes.map(({ id, Icon }, index) => (
            <FadeContent as="li" key={id} delay={index * 0.08}>
              <Icon size={20} aria-hidden="true" />
              <span>{t(id)}</span>
            </FadeContent>
          ))}
          <li className="site-notes-link">
            <a href={LINKS.readme[locale]}>
              {t("readme")}
              <ArrowUpRight size={16} aria-hidden="true" />
            </a>
          </li>
        </ul>
      </div>
    </Section>
  );
}
