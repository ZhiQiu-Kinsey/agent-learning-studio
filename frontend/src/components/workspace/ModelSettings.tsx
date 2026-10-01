import { useEffect, useRef, useState, type RefObject } from "react";
import { Check, LoaderCircle, X } from "lucide-react";
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

type Props = {
  open: boolean;
  onOpenChange: (value: boolean) => void;
  onSaved: () => void;
  triggerRef: RefObject<HTMLButtonElement | null>;
};

export function ModelSettings({
  open,
  onOpenChange,
  onSaved,
  triggerRef,
}: Props) {
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
    } catch (reason) {
      if (!abort.signal.aborted)
        setError(reason instanceof Error ? reason.message : String(reason));
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
          <DialogTitle>模型连接设置</DialogTitle>
          <Button
            type="button"
            variant="ghost"
            size="icon"
            aria-label="关闭连接设置"
            disabled={saving}
            onClick={close}
          >
            <X size={18} />
          </Button>
        </div>
        <DialogDescription>
          选择服务商与模型，每个服务商分别保存连接配置。
        </DialogDescription>
        {loading && (
          <p className="connection-status" role="status">
            <LoaderCircle size={15} className="connection-spinner" />{" "}
            正在读取服务商配置…
          </p>
        )}
        {loadError && (
          <div className="connection-error" role="alert">
            服务商配置加载失败：{loadError}
            <Button
              type="button"
              variant="ghost"
              onClick={() => setAttempt((value) => value + 1)}
            >
              重试
            </Button>
          </div>
        )}
        <form className="connection-form" onSubmit={save}>
          <div className="form-field">
            <span className="form-field-label">服务商</span>
            <GlideSelect
              className="connection-provider"
              ariaLabel="服务商"
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
              placeholder="请选择服务商"
            />
          </div>
          <div className="form-field">
            <label className="form-field-label" htmlFor="connection-model">
              模型 ID
            </label>
            <Input
              id="connection-model"
              value={modelId}
              onChange={(event) => setModelId(event.target.value)}
              disabled={disabled}
              autoComplete="off"
              placeholder="填写服务商提供的模型 ID"
            />
          </div>
          {provider?.supports_custom_base_url && (
            <div className="form-field">
              <label className="form-field-label" htmlFor="connection-base">
                API Base URL（可选）
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
                    ? "地址已配置，留空保留已有配置"
                    : "留空使用服务商默认地址"
                }
              />
            </div>
          )}
          <div className="form-field">
            <label className="form-field-label" htmlFor="connection-key">
              API Key（可选）
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
                  ? "密钥已配置，留空保留已有密钥"
                  : "填写当前服务商的密钥"
              }
            />
          </div>
          <p className="connection-note">
            密钥与自定义地址只保存在本次后端进程内存中。留空保留已有配置。
          </p>
          {!modelId.trim() && !loading && (
            <p className="connection-error">请填写模型 ID，再保存连接配置。</p>
          )}
          {provider &&
            provider.requires_api_key !== false &&
            !provider.api_key_configured &&
            !apiKey.trim() && (
              <p className="connection-note">
                当前服务商尚未配置 API Key，填写密钥后才能运行真实模型。
              </p>
            )}
          {provider?.requires_api_key === false && (
            <p className="connection-note">此服务无需 API Key，留空即可。</p>
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
            保存模型配置
          </Button>
        </form>
      </DialogContent>
    </Dialog>
  );
}
