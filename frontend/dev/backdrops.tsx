// Dev-only gallery of hero backdrops: http://127.0.0.1:5190/dev/backdrops.html
import { createRoot } from "react-dom/client";
import { MotionProvider } from "../src/motion";
import { Backdrop } from "../src/components/backdrops/Backdrop";
import { backdropPresets, type BackdropName } from "../src/components/backdrops/presets";
import "../src/workspace.css";

const only = new URLSearchParams(location.search).get("only")?.split(",");
const names = (Object.keys(backdropPresets) as BackdropName[]).filter(
  (name) => !only || only.includes(name),
);
createRoot(document.getElementById("root")!).render(
  <MotionProvider>
    {names.map((name) => (
      <div className="cell" key={name}>
        <b>{name}</b>
        <Backdrop name={name} />
      </div>
    ))}
  </MotionProvider>,
);
