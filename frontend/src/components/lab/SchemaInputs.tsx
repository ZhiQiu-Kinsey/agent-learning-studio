import { useId } from "react";
import { useTranslation } from "react-i18next";
import type { InputField } from "../../content/types.gen";
import RubberSegment from "../react-bits/RubberSegment";
import ScrubField from "../react-bits/ScrubField";
import ElasticSlider from "../react-bits/ElasticSlider";
import SquishSwitch from "../react-bits/SquishSwitch";
import GlideSelect from "../react-bits/GlideSelect";
import { Input } from "../ui/input";
import { Textarea } from "../ui/textarea";
import { segmentColors } from "./controlColors";

/** The subset of JSON Schema that Pydantic emits for lesson INPUT_MODELs. */
export interface PropertySchema {
  type?: "string" | "integer" | "number" | "boolean";
  enum?: string[];
  minimum?: number;
  maximum?: number;
  minLength?: number;
  maxLength?: number;
  title?: string;
}
export interface InputSchema {
  properties: Record<string, PropertySchema>;
}

export type ControlKind =
  | "segment"
  | "select"
  | "switch"
  | "scrub"
  | "elastic"
  | "text"
  | "textarea"
  | "unsupported";

/** Integer ranges up to this many steps fit an elastic slider's whole track. */
export const ELASTIC_MAX_STEPS = 30;

/**
 * Picks a control from the schema alone; labels come from lesson content.
 * Bounded numbers: a short integer range becomes an elastic slider (the whole
 * range is visible and each value is one drag or arrow press away); wide or
 * fractional ranges stay a ScrubField (precise drag plus typing).
 */
export function controlFor(property: PropertySchema): ControlKind {
  if (property.enum?.length)
    return property.enum.length <= 4 ? "segment" : "select";
  if (property.type === "boolean") return "switch";
  if (
    (property.type === "integer" || property.type === "number") &&
    property.minimum !== undefined &&
    property.maximum !== undefined
  )
    return property.type === "integer" &&
      property.maximum - property.minimum <= ELASTIC_MAX_STEPS
      ? "elastic"
      : "scrub";
  if (property.type === "string")
    return (property.maxLength ?? 0) > 120 ? "textarea" : "text";
  return "unsupported";
}

export function SchemaInputs({
  schema,
  fields,
  values,
  onChange,
  disabled,
}: {
  schema: InputSchema;
  fields: InputField[];
  values: Record<string, unknown>;
  onChange: (values: Record<string, unknown>) => void;
  disabled?: boolean;
}) {
  const { t } = useTranslation("lab", { keyPrefix: "inputs" });
  const baseId = useId();
  const set = (name: string, value: unknown) =>
    onChange({ ...values, [name]: value });
  return (
    <div className="schema-inputs" data-testid="schema-inputs">
      {Object.entries(schema.properties).map(([name, property]) => {
        const field = fields.find((item) => item.name === name);
        const label = field?.label ?? property.title ?? name;
        const id = `${baseId}-${name}`;
        const kind = controlFor(property);
        const optionLabel = (value: string) =>
          field?.options.find((option) => option.value === value)?.label ??
          value;
        const value = values[name];
        return (
          <div
            className="schema-input"
            key={name}
            data-control={kind}
            data-testid={`input-${name}`}
          >
            {/* Text inputs get a real <label>; ScrubField labels its own input; the
                rest name themselves via aria-label, so the heading is plain text. */}
            {kind === "text" || kind === "textarea" ? (
              <label htmlFor={id} className="schema-input-label">
                {label}
              </label>
            ) : kind === "elastic" ? (
              <span id={`${id}-label`} className="schema-input-label">
                {label}
              </span>
            ) : kind !== "scrub" ? (
              <span className="schema-input-label" aria-hidden="true">
                {label}
              </span>
            ) : null}
            {kind === "segment" && (
              <RubberSegment
                aria-label={label}
                items={property.enum!.map((option) => ({
                  value: option,
                  label: optionLabel(option),
                }))}
                value={String(value ?? property.enum![0])}
                onChange={(next) => set(name, next)}
                disabled={disabled}
                size="sm"
                {...segmentColors}
              />
            )}
            {kind === "select" && (
              <GlideSelect
                ariaLabel={label}
                value={String(value ?? "")}
                options={property.enum!.map((option) => ({
                  value: option,
                  label: optionLabel(option),
                }))}
                onChange={(next) => set(name, next)}
                disabled={disabled}
                size="sm"
                accentColor="var(--text)"
                surfaceColor="var(--surface)"
                highlightColor="var(--surface-muted)"
                textColor="var(--text)"
              />
            )}
            {kind === "switch" && (
              <SquishSwitch
                id={id}
                ariaLabel={label}
                checked={value === true}
                onChange={(next) => set(name, next)}
                disabled={disabled}
                trackColor="var(--surface-muted)"
                trackOnColor="var(--role-runtime)"
              />
            )}
            {kind === "scrub" && (
              <>
                <ScrubField
                  label={label}
                  suffix=""
                  value={typeof value === "number" ? value : property.minimum}
                  min={property.minimum}
                  max={property.maximum}
                  step={property.type === "integer" ? 1 : 0.1}
                  size="md"
                  className="schema-scrub"
                  showDelta={false}
                  accent="var(--role-runtime)"
                  chipColor="var(--surface-muted)"
                  disabled={disabled}
                  onChange={(next) =>
                    set(
                      name,
                      property.type === "integer" ? Math.round(next) : next,
                    )
                  }
                />
                <small>
                  {t("range", { min: property.minimum, max: property.maximum })}
                </small>
              </>
            )}
            {kind === "elastic" && (
              <ElasticSlider
                ariaLabelledBy={`${id}-label`}
                value={typeof value === "number" ? value : property.minimum!}
                min={property.minimum!}
                max={property.maximum!}
                step={1}
                disabled={disabled}
                accent="var(--role-runtime)"
                className="schema-elastic"
                data-testid={`input-${name}-slider`}
                onChange={(next) => set(name, Math.round(next))}
              />
            )}
            {kind === "text" && (
              <Input
                id={id}
                value={typeof value === "string" ? value : ""}
                maxLength={property.maxLength}
                onChange={(event) => set(name, event.target.value)}
                disabled={disabled}
              />
            )}
            {kind === "textarea" && (
              <Textarea
                id={id}
                value={typeof value === "string" ? value : ""}
                maxLength={property.maxLength}
                onChange={(event) => set(name, event.target.value)}
                disabled={disabled}
              />
            )}
            {kind === "unsupported" && <small>{t("unsupported")}</small>}
            {property.maxLength && (kind === "text" || kind === "textarea") && (
              <small>{t("length", { max: property.maxLength })}</small>
            )}
            {field?.help && <p className="schema-input-help">{field.help}</p>}
          </div>
        );
      })}
    </div>
  );
}
