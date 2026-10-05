import { useEffect, useRef, useState, type RefObject } from "react";
import { Check, LoaderCircle, X } from "lucide-react";
import { useTranslation } from "react-i18next";
import { jsonFetch } from "../../api";
import type { ProviderCatalog, ProviderProfile } from "../../types";
import { Button } from "../ui/button";
import { Input } from "../ui/input";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogTitle,
} from "../ui/dialog";
import GlideSelect from "../react-bits/GlideSelect";
import { notify } from "../toast/toast";
import type { ConnectionState } from "./connectionState";

type Props = {
  open: boolean;
  onOpenChange: (value: boolean) => void;
  onSaved: () => void;
  triggerRef: RefObject<HTMLButtonElement | null>;
  /** State of the saved connection (server status); the badge shows nothing else. */
  connection?: ConnectionState;
};

export function ModelSettings({
  open,
  onOpenChange,
  onSaved,
  triggerRef,
  connection = "unconfigured",
}: Props) {
  const connected = connection === "ready";
  const { t } = useTranslation("settings");
  const { t: tc } = useTranslation("common");
  const [providers, setProviders] = useState<ProviderProfile[]>([]);
  const [providerId, setProviderId] = useState("");
  const [modelId, setModelId] = useState("");
  const [apiKey, setApiKey] = useState("");
  const [apiBase, setApiBase] = useState("");
  const [loading, setLoading] = useState(false);
  const [loadError, setLoadError] = useState("");
  const [error, setError] = useState("");
  const [saving, setSaving] = useState(false);
  const [attempt, setAttempt] = useState(0);
  const saveController = useRef<AbortController | null>(null);
  useEffect(() => () => saveController.current?.abort(), []);
  useEffect(() => {
    if (!open) {
      setApiKey("");
      setApiBase("");
      return;
    }
    const abort = new AbortController();
    setLoading(true);
    setLoadError("");
    setError("");
    setApiKey("");
    setApiBase("");
    jsonFetch<ProviderCatalog>("/api/providers", { signal: abort.signal })
      .then((catalog) => {
        if (abort.signal.aborted) return;
        setProviders(catalog.providers);
        const current =
          catalog.providers.find(
            (item) => item.id === catalog.active_provider,
          ) || catalog.providers[0];
        setProviderId(current?.id || "");
        setModelId(current?.model || "");
      })
      .catch((reason: unknown) => {
        if (!abort.signal.aborted)
          setLoadError(
            reason instanceof Error ? reason.message : String(reason),
          );
      })
      .finally(() => {
        if (!abort.signal.aborted) setLoading(false);
      });
    return () => abort.abort();
  }, [open, attempt]);

  const provider = providers.find((item) => item.id === providerId);
  const disabled = loading || saving || !!loadError;
  function close() {
    if (saveController.current) return;
    setApiKey("");
    setApiBase("");
    onOpenChange(false);
  }
  function changeProvider(id: string) {
    setProviderId(id);
    setModelId(providers.find((item) => item.id === id)?.model || "");
    setApiKey("");
    setApiBase("");
    setError("");
  }
  async function save(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (disabled || saveController.current || !providerId || !modelId.trim())
      return;
    const abort = new AbortController();
    saveController.current = abort;
    setSaving(true);
    setError("");
    try {
      await jsonFetch("/api/settings", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        signal: abort.signal,
        body: JSON.stringify({
          provider_id: providerId,
          model: modelId.trim(),
          ...(apiKey.trim() ? { api_key: apiKey.trim() } : {}),
          ...(apiBase.trim() ? { api_base: apiBase.trim() } : {}),
        }),
      });
      if (abort.signal.aborted) return;
      setApiKey("");
      setApiBase("");
      onSaved();
      onOpenChange(false);
      notify({
        tone: "success",
        title: tc("toast.settingsSaved"),
        description: tc("toast.settingsSavedBody", {
          provider: provider?.label || providerId,
          model: modelId.trim(),
        }),
      });
    } catch (reason) {
      if (!abort.signal.aborted) {
        const message =
          reason instanceof Error ? reason.message : String(reason);
        setError(message);
        notify({
          tone: "error",
          title: tc("toast.settingsFailed"),
          description: message,
        });
      }
    } finally {
      saveController.current = null;
      if (!abort.signal.aborted) setSaving(false);
    }
  }

  return (
    <Dialog
      open={open}
      onOpenChange={(value) => {
        if (!value) close();
      }}
    >
      <DialogContent
        className="connection-dialog"
        data-connected={connected || undefined}
        showCloseButton={false}
        onCloseAutoFocus={(event) => {
          event.preventDefault();
          triggerRef.current?.focus();
        }}
        onEscapeKeyDown={(event) => {
          if (saving) event.preventDefault();
        }}
        onInteractOutside={(event) => {
          if (saving) event.preventDefault();
        }}
      >
        <div className="connection-dialog-heading">
          <DialogTitle>{t("title")}</DialogTitle>
          {/* "Connected" only while the saved connection is really ready; a
              provider that still needs a key says so instead (server status). */}
          {connected && (
            <span className="connection-badge" data-testid="connection-ready">
              <i aria-hidden="true" />
              {t("connected")}
            </span>
          )}
          {connection === "missing-key" && (
            <span
              className="connection-badge"
              data-state="missing-key"
              data-testid="connection-missing-key"
            >
              <i aria-hidden="true" />
              {t("keyNotConfigured")}
            </span>
          )}
          <Button
            type="button"
            variant="ghost"
            size="icon"
            aria-label={t("close")}
            disabled={saving}
            onClick={close}
          >
            <X size={18} />
          </Button>
        </div>
        <DialogDescription>{t("description")}</DialogDescription>
        {loading && (
          <p className="connection-status" role="status">
            <LoaderCircle size={15} className="connection-spinner" />{" "}
            {t("loading")}
          </p>
        )}
        {loadError && (
          <div className="connection-error" role="alert">
            {t("loadFailed", { reason: loadError })}
            <Button
              type="button"
              variant="ghost"
              onClick={() => setAttempt((value) => value + 1)}
            >
              {t("retry")}
            </Button>
          </div>
        )}
        <form className="connection-form" onSubmit={save}>
          <div className="form-field">
            <span className="form-field-label">{t("provider")}</span>
            <GlideSelect
              className="connection-provider"
              ariaLabel={t("provider")}
              value={providerId}
              onChange={changeProvider}
              disabled={disabled}
              showTags={false}
              size="lg"
              menuWidth={300}
              radius={10}
              surfaceColor="var(--popover)"
              textColor="var(--foreground)"
              highlightColor="var(--accent)"
              accentColor="var(--primary)"
              options={providers.map((item) => ({
                value: item.id,
                label: item.label,
              }))}
              placeholder={t("providerPlaceholder")}
            />
          </div>
          <div className="form-field">
            <label className="form-field-label" htmlFor="connection-model">
              {t("model")}
            </label>
            <Input
              id="connection-model"
              value={modelId}
              onChange={(event) => setModelId(event.target.value)}
              disabled={disabled}
              autoComplete="off"
              placeholder={t("modelPlaceholder")}
            />
          </div>
          {provider?.supports_custom_base_url && (
            <div className="form-field">
              <label className="form-field-label" htmlFor="connection-base">
                {t("baseUrl")}
              </label>
              <Input
                id="connection-base"
                type="url"
                value={apiBase}
                onChange={(event) => setApiBase(event.target.value)}
                disabled={disabled}
                autoComplete="off"
                placeholder={
                  provider.base_url_configured
                    ? t("baseUrlConfigured")
                    : t("baseUrlDefault")
                }
              />
            </div>
          )}
          <div className="form-field">
            <label className="form-field-label" htmlFor="connection-key">
              {t("apiKey")}
            </label>
            <Input
              id="connection-key"
              type="password"
              value={apiKey}
              onChange={(event) => setApiKey(event.target.value)}
              disabled={disabled}
              autoComplete="off"
              placeholder={
                provider?.api_key_configured
                  ? t("apiKeyConfigured")
                  : t("apiKeyPlaceholder")
              }
            />
          </div>
          <p className="connection-note">{t("storageNote")}</p>
          {!modelId.trim() && !loading && (
            <p className="connection-error">{t("modelRequired")}</p>
          )}
          {provider &&
            provider.requires_api_key !== false &&
            !provider.api_key_configured &&
            !apiKey.trim() && (
              <p className="connection-note">{t("keyMissing")}</p>
            )}
          {provider?.requires_api_key === false && (
            <p className="connection-note">{t("keyNotRequired")}</p>
          )}
          {error && (
            <p className="connection-error" role="alert">
              {error}
            </p>
          )}
          <Button
            className="connection-save"
            type="submit"
            disabled={disabled || !providerId || !modelId.trim()}
          >
            {saving ? (
              <LoaderCircle size={15} className="connection-spinner" />
            ) : (
              <Check size={15} />
            )}
            {t("save")}
          </Button>
        </form>
      </DialogContent>
    </Dialog>
  );
}
