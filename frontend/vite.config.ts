import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";
export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: {
      "@": new URL("./src", import.meta.url).pathname.replace(
        /^\/([A-Za-z]:)/,
        "$1",
      ),
    },
  },
  server: {
    proxy: {
      "/api": {
        target: "http://127.0.0.1:8765",
        changeOrigin: true,
        configure(proxy) {
          proxy.on("proxyReq", (outgoing, incoming) => {
            // Translate only same-origin development requests. Foreign origins remain
            // untouched and are rejected by the backend's existing request guard.
            if (incoming.headers.origin === `http://${incoming.headers.host}`) {
              outgoing.setHeader("origin", "http://127.0.0.1:8765");
            }
          });
        },
      },
    },
  },
});
