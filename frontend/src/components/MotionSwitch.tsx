import { CirclePause, Feather, Sparkles } from "lucide-react";
import { useTranslation } from "react-i18next";
import GlideSelect from "./react-bits/GlideSelect";
import { useMotion } from "../motion";
import { motionSettings, parseMotionSetting } from "../motion/level";

export function MotionSwitch() {
  const { t } = useTranslation();
  const { setting, setSetting, level } = useMotion();
  const Icon =
    level === "static" ? CirclePause : level === "reduced" ? Feather : Sparkles;
  return (
    <div className="theme-control" title={t("motion.control")}>
      <Icon size={16} aria-hidden="true" />
      <GlideSelect
        ariaLabel={t("motion.label")}
        value={setting}
        options={motionSettings.map((value) => ({
          value,
          label: t(`motion.${value}`),
        }))}
        size="sm"
        align="right"
        menuWidth={136}
        accentColor="var(--text)"
        surfaceColor="var(--surface)"
        highlightColor="var(--surface-muted)"
        textColor="var(--text)"
        onChange={(value) => setSetting(parseMotionSetting(value))}
      />
    </div>
  );
}
