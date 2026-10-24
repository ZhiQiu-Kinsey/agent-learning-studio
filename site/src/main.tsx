import React from "react";
import ReactDOM from "react-dom/client";
import "./i18n";
import { MotionProvider } from "@studio/motion";
import App from "./App";
import "./styles/foundation.css";
import "./styles/site.css";

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <MotionProvider>
      <App />
    </MotionProvider>
  </React.StrictMode>,
);
