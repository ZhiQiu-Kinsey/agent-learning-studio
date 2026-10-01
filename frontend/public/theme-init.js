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

// Motion level before first paint; MotionProvider keeps it current afterwards.
(() => {
  let preference = "system";
  try {
    const saved = localStorage.getItem("agent-lab-motion");
    if (["system", "full", "reduced", "static"].includes(saved)) preference = saved;
  } catch { /* Fall back to the OS preference. */ }
  const level = preference === "system"
    ? (matchMedia("(prefers-reduced-motion: reduce)").matches ? "static" : "full")
    : preference;
  document.documentElement.dataset.motion = level;
  document.documentElement.dataset.motionPreference = preference;
})();
