import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";

const frontendSrc = new URL("../frontend/src", import.meta.url).pathname.replace(
  /^\/([A-Za-z]:)/,
  "$1",
);

// The site reuses the platform's replay components from ../frontend/src. Their bare imports
// must resolve to this package's copies (one React, one i18next instance), so every runtime
// dependency is deduped to site/node_modules and the frontend's node_modules is never needed.
const shared = [
  "react",
  "react-dom",
  "react/jsx-runtime",
  "i18next",
  "react-i18next",
  "motion",
  "lucide-react",
  "prismjs",
  "radix-ui",
  "class-variance-authority",
  "cn",
  "gsap",
  "ogl",
  "@hugeicons/react",
  "@hugeicons/core-free-icons",
  // Imported by platform modules the replay pulls in (react-bits, api, i18n).
  "@gsap/react",
  "eventsource-parser",
  "i18next-resources-to-backend",
];

export default defineConfig({
  // GitHub Pages serves the project site under /<repo>/.
  base: process.env.SITE_BASE ?? "/agent-learning-studio/",
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: { "@": frontendSrc, "@studio": frontendSrc },
    dedupe: shared,
  },
  server: { fs: { allow: [".", "../frontend/src"] } },
});
