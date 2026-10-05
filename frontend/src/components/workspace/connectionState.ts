import type { Status } from "../../types";

/**
 * What the saved connection can do, from the server's status only. The key
 * itself never reaches the browser; the server reports whether one is set.
 *
 * - `ready`: address and model are set, and a key is set or not needed.
 * - `missing-key`: address and model are set, but the provider needs a key.
 * - `unconfigured`: address or model is missing (or status not loaded yet).
 */
export type ConnectionState = "ready" | "missing-key" | "unconfigured";

export function connectionState(
  status:
    | Pick<Status, "config_ready" | "api_key_configured" | "requires_api_key">
    | null
    | undefined,
): ConnectionState {
  if (!status?.config_ready) return "unconfigured";
  return status.requires_api_key === false || status.api_key_configured
    ? "ready"
    : "missing-key";
}
