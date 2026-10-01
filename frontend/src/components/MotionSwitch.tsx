import { CirclePause, Feather, Sparkles } from "lucide-react";
import GlideSelect from "./react-bits/GlideSelect";
import { useMotion } from "../motion";
import { parseMotionSetting } from "../motion/level";

export function MotionSwitch() {
  const { setting, setSetting, level } = useMotion();
  const Icon =
    level === "static" ? CirclePause : level === "reduced" ? Feather : Sparkles;
  return (
    <div className="theme-control" title="调整页面动效">
      <Icon size={16} aria-hidden="true" />
      <GlideSelect
        ariaLabel="页面动效"
        value={setting}
        options={[
          { value: "system", label: "跟随系统" },
          { value: "full", label: "完整" },
          { value: "reduced", label: "简洁" },
          { value: "static", label: "静态" },
        ]}
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
