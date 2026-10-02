// Runs before styles/React paint; external file respects the local server's CSP.
(() => {
  let preference = "system";
  try {
    const saved = localStorage.getItem("agent-lab-theme");
    if (["light", "dark", "system"].includes(saved)) preference = saved;
  } catch { /* Theme still works when browser storage is unavailable. */ }
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
