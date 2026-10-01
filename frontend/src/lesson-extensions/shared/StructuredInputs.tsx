import { useState } from "react";
import { useTranslation } from "react-i18next";
import type { LabExtensionProps } from "../types";
import { Textarea } from "../../components/ui/textarea";
import { Button } from "../../components/ui/button";
import { SchemaInputs } from "../../components/lab/SchemaInputs";
import "./structured-inputs.css";

/**
 * Reuses the platform run button, cancellation and trace; only adds input UI.
 * Controls are generated from the lesson's INPUT_MODEL schema with labels from
 * lesson content; JSON editing stays available as the advanced mode and is the
 * only mode when a lesson publishes no schema. The server validates either way.
 */
export default function StructuredInputs({
  studio,
  children,
}: LabExtensionProps) {
  const { t } = useTranslation("lab", { keyPrefix: "inputs" });
  const schema = studio.detail?.input_schema ?? null;
  const fields = studio.detail?.learning?.scenes.lab?.inputs ?? [];
  const [json, setJson] = useState(!schema);
  const advanced = json || !schema;
  return (
    <>
      <section
        className="structured-inputs"
        aria-label={t("region")}
        data-testid="lab-inputs"
      >
        <div className="structured-inputs-heading">
          <div>
            {advanced ? (
              <label htmlFor="lesson-inputs">{t("jsonLabel")}</label>
            ) : (
              <strong>{t("title")}</strong>
            )}
            <p>{t("help")}</p>
          </div>
          {schema && (
            <Button
              type="button"
              variant="ghost"
              size="sm"
              data-testid="lab-inputs-mode"
              disabled={studio.running || (advanced && !!studio.inputError)}
              onClick={() => setJson(!advanced)}
            >
              {advanced ? t("simple") : t("advanced")}
            </Button>
          )}
        </div>
        {advanced ? (
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
        ) : (
          <SchemaInputs
            schema={schema!}
            fields={fields}
            values={studio.inputs}
            onChange={studio.setInputs}
            disabled={studio.running}
          />
        )}
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
