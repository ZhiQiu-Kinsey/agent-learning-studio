import type { LabExtensionProps } from "../types";
import { Textarea } from "../../components/ui/textarea";
import "./structured-inputs.css";

/** Reuses the platform run button, cancellation and trace; only adds input UI. */
export default function StructuredInputs({
  studio,
  children,
}: LabExtensionProps) {
  return (
    <>
      <section className="structured-inputs" aria-label="本课结构化输入">
        <div>
          <label htmlFor="lesson-inputs">实验参数 JSON</label>
          <p>
            修改本课参数，再用下方「运行练习」运行。切换练习会载入对应的默认参数。
          </p>
        </div>
        <Textarea
          id="lesson-inputs"
          data-testid="lab-inputs-json"
          value={studio.inputText}
          onChange={(event) => studio.editInputs(event.target.value)}
          disabled={studio.running}
          aria-invalid={!!studio.inputError}
          aria-describedby={
            studio.inputError ? "lesson-input-error" : undefined
          }
          spellCheck={false}
        />
        {studio.inputError && (
          <p id="lesson-input-error" role="alert">
            {studio.inputError}
          </p>
        )}
      </section>
      {children}
    </>
  );
}
