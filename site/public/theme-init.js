// Runs before styles and React paint, so the first frame already has the right theme.
(() => {
  // The site opens dark; a visitor's own choice (light, dark or system) is remembered.
  let preference = "dark";
  try {
    const saved = localStorage.getItem("agent-lab-theme");
    if (["light", "dark", "system"].includes(saved)) preference = saved;
  } catch { /* Without storage the site stays dark. */ }
  const theme = preference === "system"
    ? (matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light")
    : preference;
  document.documentElement.dataset.theme = theme;
  document.documentElement.dataset.themePreference = preference;
  document.documentElement.style.colorScheme = theme;
})();

// Motion follows the OS preference only; MotionProvider keeps it current afterwards.
document.documentElement.dataset.motion = matchMedia("(prefers-reduced-motion: reduce)").matches
  ? "static"
  : "full";
