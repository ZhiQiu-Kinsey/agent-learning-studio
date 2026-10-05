import { describe, expect, it } from "vitest";
import { connectionState } from "../connectionState";

describe("connectionState", () => {
  it("is ready only when a needed key is configured", () => {
    expect(
      connectionState({ config_ready: true, api_key_configured: true }),
    ).toBe("ready");
    expect(
      connectionState({
        config_ready: true,
        api_key_configured: true,
        requires_api_key: true,
      }),
    ).toBe("ready");
  });

  it("reports a missing key instead of claiming the connection works", () => {
    // Address and model saved, no key: the badge must not say "connected".
    expect(
      connectionState({
        config_ready: true,
        api_key_configured: false,
        requires_api_key: true,
      }),
    ).toBe("missing-key");
    // Older servers omit requires_api_key; a key is then assumed to be needed.
    expect(
      connectionState({ config_ready: true, api_key_configured: false }),
    ).toBe("missing-key");
  });

  it("treats a provider that needs no key as ready without one", () => {
    expect(
      connectionState({
        config_ready: true,
        api_key_configured: false,
        requires_api_key: false,
      }),
    ).toBe("ready");
  });

  it("is unconfigured without an address and model, or before status loads", () => {
    expect(
      connectionState({
        config_ready: false,
        api_key_configured: true,
        requires_api_key: true,
      }),
    ).toBe("unconfigured");
    expect(connectionState(null)).toBe("unconfigured");
    expect(connectionState(undefined)).toBe("unconfigured");
  });
});
