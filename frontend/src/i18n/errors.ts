import i18n from "./index";
import { sourceResources } from "./resources";

type ErrorCode = keyof typeof sourceResources.errors.code;

const isErrorCode = (code: string): code is ErrorCode =>
  Object.hasOwn(sourceResources.errors.code, code);

/**
 * Server errors carry a stable code (+ optional params); the UI language owns the
 * wording. Codes without a translation (dynamic validation text) show the
 * server's detail unchanged.
 */
export function errorMessage(
  code: string | undefined,
  params: Record<string, unknown> | undefined,
  detail: string | undefined,
  fallback: string,
): string {
  if (code && isErrorCode(code))
    return i18n.t(`errors:code.${code}`, { ...params });
  return detail || fallback;
}

export const clientError = (
  key: keyof typeof sourceResources.errors.client,
  params?: Record<string, unknown>,
) => i18n.t(`errors:client.${key}`, { ...params });
