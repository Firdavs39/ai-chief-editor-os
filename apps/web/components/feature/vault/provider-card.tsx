"use client";

import * as React from "react";
import {
  AlertTriangle,
  CheckCircle2,
  ChevronDown,
  ChevronUp,
  Loader2,
  PlayCircle,
  Save,
  Settings2,
  ShieldCheck,
  Trash2,
  XCircle,
} from "lucide-react";
import { toast } from "sonner";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { vaultApi } from "@/lib/api";
import type {
  ReadinessItem,
  VaultFieldStatus,
  VaultProviderSummary,
} from "@/lib/types";
import { cn } from "@/lib/utils";

type Props = {
  provider: VaultProviderSummary;
  adminToken: string;
  vaultEnabled: boolean;
  onUpdated: (updated: VaultProviderSummary) => void;
};

const SOURCE_VARIANT: Record<
  string,
  "mint" | "cyan" | "violet" | "amber" | "rose" | "outline"
> = {
  env: "cyan",
  vault: "violet",
  missing: "outline",
};

// ---------------------------------------------------------------------------
// Ollama presets — pure frontend convenience. Selecting a preset pre-fills
// `base_url` and `model` so most operators only ever paste an API key.
// The vault still stores the same three values exactly as before.
// ---------------------------------------------------------------------------

type OllamaPresetId = "cloud" | "local" | "custom";

type OllamaPreset = {
  id: Exclude<OllamaPresetId, "custom">;
  label: string;
  description: string;
  base_url: string;
  model: string;
  apiKeyRequired: boolean;
  apiKeyHint: string;
};

const OLLAMA_PRESETS: OllamaPreset[] = [
  {
    id: "cloud",
    label: "Ollama Cloud / Kimi K2.6",
    description: "Hosted Kimi K2.6 via ollama.com — fastest path to a real LLM.",
    base_url: "https://ollama.com",
    model: "kimi-k2.6:cloud",
    apiKeyRequired: true,
    apiKeyHint: "Paste your Ollama API key.",
  },
  {
    id: "local",
    label: "Local Ollama",
    description: "Self-hosted Ollama on this machine or your network.",
    base_url: "http://localhost:11434/v1",
    model: "kimi-k2.6:cloud",
    apiKeyRequired: false,
    apiKeyHint:
      "API key is optional for local Ollama. Backend must be able to reach your server.",
  },
];

function detectOllamaPreset(fields: VaultFieldStatus[]): OllamaPresetId {
  const base = fields.find((f) => f.key_name === "base_url");
  if (!base) return "cloud";
  const meta = base.safe_metadata as { value?: string };
  const v = (meta?.value ?? "").trim();
  if (!v) return "cloud";
  if (v === "https://ollama.com") return "cloud";
  if (v === "http://localhost:11434/v1" || v === "http://localhost:11434") return "local";
  return "custom";
}

// ---------------------------------------------------------------------------
// Status helpers
// ---------------------------------------------------------------------------

function StatusBadge({ status }: { status: string }) {
  const map: Record<
    string,
    { variant: "mint" | "cyan" | "violet" | "amber" | "rose" | "outline"; label: string }
  > = {
    valid: { variant: "mint", label: "valid" },
    configured: { variant: "violet", label: "configured" },
    unknown: { variant: "outline", label: "unknown" },
    invalid: { variant: "rose", label: "invalid" },
    error: { variant: "rose", label: "error" },
    missing_config: { variant: "amber", label: "missing" },
    disabled: { variant: "outline", label: "disabled" },
  };
  const m = map[status] ?? { variant: "outline" as const, label: status };
  return <Badge variant={m.variant}>{m.label}</Badge>;
}

function FieldDescription({ field }: { field: VaultFieldStatus }) {
  const meta = field.safe_metadata as {
    length?: number;
    mask?: string;
    value?: string;
    is_secret?: boolean;
  };
  if (field.source === "env") {
    if (field.is_secret) {
      return (
        <span className="text-[11px] text-ink-400">
          Already set in <code className="font-mono text-ink-200">.env</code>
          {meta.length ? ` · length ${meta.length}` : ""}
        </span>
      );
    }
    return (
      <span className="text-[11px] text-ink-400">
        Already set in <code className="font-mono text-ink-200">.env</code>:{" "}
        <span className="font-mono text-ink-200">{String(meta.value ?? "")}</span>
      </span>
    );
  }
  if (field.source === "vault") {
    if (field.is_secret) {
      return (
        <span className="text-[11px] text-ink-400">
          stored · {meta.mask ?? "•••••"}
          {meta.length ? ` · length ${meta.length}` : ""}
        </span>
      );
    }
    return (
      <span className="text-[11px] text-ink-400">
        stored: <span className="font-mono text-ink-200">{String(meta.value ?? "")}</span>
      </span>
    );
  }
  return <span className="text-[11px] text-ink-500">not set</span>;
}

// ---------------------------------------------------------------------------
// Provider card
// ---------------------------------------------------------------------------

export function ProviderCard({ provider, adminToken, vaultEnabled, onUpdated }: Props) {
  const [expanded, setExpanded] = React.useState(false);
  const [showAdvanced, setShowAdvanced] = React.useState(false);
  const [busy, setBusy] = React.useState<null | "save" | "save_test" | "test" | "delete">(
    null,
  );
  const [values, setValues] = React.useState<Record<string, string>>({});

  // Ollama-only preset state.
  const isOllama = provider.provider === "ollama";
  const [ollamaPreset, setOllamaPreset] = React.useState<OllamaPresetId>(() =>
    isOllama ? detectOllamaPreset(provider.fields) : "cloud",
  );
  // When the provider summary refreshes from the server, re-derive the preset
  // (e.g. after a save+test).
  React.useEffect(() => {
    if (isOllama) setOllamaPreset(detectOllamaPreset(provider.fields));
  }, [isOllama, provider.fields]);

  const presetConfig: OllamaPreset | null = React.useMemo(() => {
    if (!isOllama || ollamaPreset === "custom") return null;
    return OLLAMA_PRESETS.find((p) => p.id === ollamaPreset) ?? null;
  }, [isOllama, ollamaPreset]);

  function clearInputs() {
    setValues({});
  }

  function setField(key: string, v: string) {
    setValues((prev) => ({ ...prev, [key]: v }));
  }

  function applyPreset(p: OllamaPresetId) {
    setOllamaPreset(p);
    if (p === "custom") {
      // Keep whatever the user has typed; just reveal Advanced.
      setShowAdvanced(true);
      return;
    }
    const preset = OLLAMA_PRESETS.find((x) => x.id === p);
    if (!preset) return;
    setValues((prev) => ({
      ...prev,
      base_url: preset.base_url,
      model: preset.model,
    }));
    // Presets keep Advanced collapsed — the operator doesn't need to see it.
    setShowAdvanced(false);
  }

  // Split fields into primary + advanced. For Ollama with a preset, we treat
  // `base_url` and `model` as preset-driven: base_url stays under Advanced,
  // model stays visible.
  const primaryFields = provider.fields.filter((f) => !f.advanced);
  const advancedFields = provider.fields.filter((f) => f.advanced);

  // Build the payload to send to the backend. For Ollama with a preset,
  // we ensure base_url and model are sent even if the user did not type them.
  function buildPayload(): Record<string, string> {
    const filled: Record<string, string> = {};
    for (const [k, v] of Object.entries(values)) {
      if (v.length > 0) filled[k] = v;
    }
    if (isOllama && presetConfig) {
      // Pre-fill from preset if user has not overridden.
      if (!filled.base_url) filled.base_url = presetConfig.base_url;
      if (!filled.model) filled.model = presetConfig.model;
    }
    return filled;
  }

  async function doSave(thenTest: boolean) {
    if (!vaultEnabled) {
      toast.error("Vault disabled", {
        description: "MASTER_ENCRYPTION_KEY is not set on the backend.",
      });
      return;
    }
    const payload = buildPayload();
    if (Object.keys(payload).length === 0) {
      toast.error("Nothing to save", { description: "Fill at least one field." });
      return;
    }
    setBusy(thenTest ? "save_test" : "save");
    try {
      const updated = await vaultApi.save(provider.provider, payload, adminToken);
      clearInputs();
      onUpdated(updated);
      toast.success(`Saved ${updated.label}`, {
        description: "Encrypted and stored. The value is not echoed back.",
      });
      if (thenTest) {
        await doTest();
      }
    } catch (err) {
      handleError(err, "Save failed");
    } finally {
      setBusy(null);
    }
  }

  async function doTest() {
    setBusy((b) => (b === null ? "test" : b));
    try {
      const item: ReadinessItem = await vaultApi.test(provider.provider, adminToken);
      const tone =
        item.status === "valid"
          ? "success"
          : item.status === "missing_config"
          ? "warning"
          : item.status === "configured"
          ? "info"
          : "error";
      const fn =
        tone === "success"
          ? toast.success
          : tone === "warning"
          ? toast.warning
          : tone === "info"
          ? toast.info
          : toast.error;
      fn(`Tested ${provider.label}`, {
        description: item.message || item.status,
      });
      const refreshed = await vaultApi.get(provider.provider, adminToken);
      onUpdated(refreshed);
    } catch (err) {
      handleError(err, "Test failed");
    } finally {
      setBusy(null);
    }
  }

  async function doDelete(field: VaultFieldStatus) {
    if (field.source !== "vault") {
      toast.warning("Nothing to delete", {
        description: "This field is sourced from your environment, not from the vault.",
      });
      return;
    }
    const sure = window.confirm(
      `Delete ${provider.label} / ${field.label}? Encrypted value will be permanently removed.`,
    );
    if (!sure) return;
    setBusy("delete");
    try {
      const updated = await vaultApi.delete(provider.provider, field.key_name, adminToken);
      onUpdated(updated);
      toast.success("Deleted", { description: `${field.label} removed from the vault.` });
    } catch (err) {
      handleError(err, "Delete failed");
    } finally {
      setBusy(null);
    }
  }

  function handleError(err: unknown, fallback: string) {
    const msg = err instanceof Error ? err.message : String(err);
    if (msg === "admin_token_invalid" || msg === "admin_token_required") {
      toast.error("Unlock vault", { description: "Admin token is missing or invalid." });
      return;
    }
    if (msg === "vault_disabled") {
      toast.error("Vault disabled", {
        description: "MASTER_ENCRYPTION_KEY is not set on the backend.",
      });
      return;
    }
    toast.error(fallback, { description: msg.slice(0, 200) });
  }

  const lastTested = provider.last_tested_at
    ? new Date(provider.last_tested_at).toLocaleString()
    : "never";

  const SourceIcon =
    provider.status === "valid"
      ? CheckCircle2
      : provider.status === "invalid" || provider.status === "error"
      ? XCircle
      : provider.source === "env" || provider.source === "vault" || provider.source === "env+vault"
      ? ShieldCheck
      : AlertTriangle;

  const connectVerb = isOllama ? "Connect Ollama" : "Configure";
  const connectedVerb = "Reconfigure";
  const apiKeyField = provider.fields.find((f) => f.is_secret);

  return (
    <Card className="p-4 sm:p-5">
      <div className="flex items-start gap-3">
        <div
          className={cn(
            "grid h-9 w-9 place-items-center rounded-xl ring-1 shrink-0",
            provider.status === "valid"
              ? "bg-state-success/10 ring-state-success/30"
              : provider.status === "configured"
              ? "bg-accent-violet/10 ring-accent-violet/30"
              : provider.status === "invalid" || provider.status === "error"
              ? "bg-state-danger/10 ring-state-danger/30"
              : "bg-white/[0.04] ring-white/[0.06]",
          )}
        >
          <SourceIcon
            className={cn(
              "h-4 w-4",
              provider.status === "valid" && "text-state-success",
              provider.status === "configured" && "text-accent-violet",
              (provider.status === "invalid" || provider.status === "error") &&
                "text-state-danger",
            )}
            strokeWidth={2.2}
          />
        </div>
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2 flex-wrap">
            <span className="text-sm font-medium text-ink-50">{provider.label}</span>
            <StatusBadge status={provider.status} />
            <Badge
              variant={
                SOURCE_VARIANT[provider.source.replace("+", "") as keyof typeof SOURCE_VARIANT] ??
                "outline"
              }
            >
              {provider.source === "missing" ? "not connected" : `from ${provider.source}`}
            </Badge>
          </div>
          <div className="mt-1 text-[11px] text-ink-500">
            tested {lastTested}
            {provider.last_test_message && (
              <span className="ml-1 text-ink-400">— {provider.last_test_message}</span>
            )}
          </div>
        </div>
        <Button
          variant="ghost"
          size="sm"
          onClick={() => setExpanded((x) => !x)}
          className="shrink-0"
        >
          {expanded ? (
            <>
              <ChevronUp className="h-3.5 w-3.5" /> Hide
            </>
          ) : (
            <>
              <ChevronDown className="h-3.5 w-3.5" />
              {provider.status === "valid" || provider.source !== "missing"
                ? connectedVerb
                : connectVerb}
            </>
          )}
        </Button>
      </div>

      {expanded && (
        <div className="mt-4 space-y-3">
          {isOllama && (
            <OllamaPresetPicker
              selected={ollamaPreset}
              onSelect={applyPreset}
              disabled={!vaultEnabled || busy !== null}
            />
          )}

          {primaryFields.map((field) => (
            <FieldRow
              key={field.key_name}
              field={field}
              value={values[field.key_name] ?? ""}
              presetHint={
                isOllama && presetConfig && field.key_name === "api_key"
                  ? presetConfig.apiKeyHint
                  : undefined
              }
              presetOptional={
                isOllama && presetConfig && field.key_name === "api_key"
                  ? !presetConfig.apiKeyRequired
                  : false
              }
              vaultEnabled={vaultEnabled}
              onChange={(v) => setField(field.key_name, v)}
              onDelete={() => doDelete(field)}
            />
          ))}

          {advancedFields.length > 0 && (
            <div className="rounded-xl border border-white/[0.04] bg-white/[0.01]">
              <button
                type="button"
                onClick={() => setShowAdvanced((x) => !x)}
                className="flex w-full items-center gap-2 px-3 py-2 text-[11px] uppercase tracking-[0.18em] text-ink-400 hover:text-ink-200 transition-colors"
              >
                <Settings2 className="h-3 w-3" />
                Advanced endpoint settings
                {showAdvanced ? (
                  <ChevronUp className="h-3 w-3 ml-auto" />
                ) : (
                  <ChevronDown className="h-3 w-3 ml-auto" />
                )}
              </button>
              {showAdvanced && (
                <div className="border-t border-white/[0.04] p-3 space-y-3">
                  <p className="text-[11px] text-ink-500 italic">
                    Most users do not need to change these. Only override if you know your endpoint.
                  </p>
                  {advancedFields.map((field) => (
                    <FieldRow
                      key={field.key_name}
                      field={field}
                      value={values[field.key_name] ?? ""}
                      vaultEnabled={vaultEnabled}
                      onChange={(v) => {
                        // Typing in the base_url field switches Ollama to "custom" preset.
                        if (isOllama && field.key_name === "base_url" && presetConfig) {
                          setOllamaPreset("custom");
                        }
                        setField(field.key_name, v);
                      }}
                      onDelete={() => doDelete(field)}
                    />
                  ))}
                </div>
              )}
            </div>
          )}

          <div className="flex flex-wrap gap-2 pt-1">
            <Button
              variant="default"
              size="sm"
              onClick={() => doSave(false)}
              disabled={!vaultEnabled || busy !== null}
            >
              {busy === "save" ? (
                <Loader2 className="h-3.5 w-3.5 animate-spin" />
              ) : (
                <Save className="h-3.5 w-3.5" />
              )}
              Save
            </Button>
            <Button
              variant="cyan"
              size="sm"
              onClick={() => doSave(true)}
              disabled={!vaultEnabled || busy !== null}
            >
              {busy === "save_test" ? (
                <Loader2 className="h-3.5 w-3.5 animate-spin" />
              ) : (
                <PlayCircle className="h-3.5 w-3.5" />
              )}
              Save & Test
            </Button>
            <Button
              variant="outline"
              size="sm"
              onClick={() => doTest()}
              disabled={busy !== null}
            >
              {busy === "test" ? (
                <Loader2 className="h-3.5 w-3.5 animate-spin" />
              ) : (
                <PlayCircle className="h-3.5 w-3.5" />
              )}
              Test
            </Button>
            {apiKeyField?.source === "vault" && (
              <Button
                variant="outline"
                size="sm"
                onClick={() => doDelete(apiKeyField)}
                disabled={busy !== null}
                title="Remove the saved API key from the vault"
              >
                <Trash2 className="h-3.5 w-3.5" /> Disconnect
              </Button>
            )}
          </div>
        </div>
      )}
    </Card>
  );
}

// ---------------------------------------------------------------------------
// Subcomponents
// ---------------------------------------------------------------------------

function OllamaPresetPicker({
  selected,
  onSelect,
  disabled,
}: {
  selected: OllamaPresetId;
  onSelect: (id: OllamaPresetId) => void;
  disabled: boolean;
}) {
  return (
    <div>
      <div className="text-[11px] font-medium uppercase tracking-[0.18em] text-ink-400 mb-1.5">
        Choose how you run Ollama
      </div>
      <div className="grid gap-2 sm:grid-cols-2">
        {OLLAMA_PRESETS.map((p) => {
          const active = selected === p.id;
          return (
            <button
              key={p.id}
              type="button"
              disabled={disabled}
              onClick={() => onSelect(p.id)}
              className={cn(
                "text-left rounded-xl border p-3 transition-colors",
                active
                  ? "border-accent-violet/40 bg-accent-violet/[0.08]"
                  : "border-white/[0.06] bg-white/[0.015] hover:bg-white/[0.03]",
                disabled && "opacity-60 cursor-not-allowed",
              )}
            >
              <div className="flex items-center gap-2 text-[12px] font-medium text-ink-50">
                {p.label}
                {active && <Badge variant="violet">selected</Badge>}
              </div>
              <p className="mt-1 text-[11px] text-ink-400 leading-snug">{p.description}</p>
            </button>
          );
        })}
      </div>
      {selected === "custom" && (
        <p className="mt-2 text-[11px] text-accent-amber">
          Custom endpoint mode — set your base URL under Advanced settings below.
        </p>
      )}
    </div>
  );
}

function FieldRow({
  field,
  value,
  presetHint,
  presetOptional,
  vaultEnabled,
  onChange,
  onDelete,
}: {
  field: VaultFieldStatus;
  value: string;
  presetHint?: string;
  presetOptional?: boolean;
  vaultEnabled: boolean;
  onChange: (v: string) => void;
  onDelete: () => void;
}) {
  const required = field.required && !presetOptional;
  return (
    <div className="rounded-xl border border-white/[0.05] bg-white/[0.015] p-3">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <label
            htmlFor={`${field.key_name}-input`}
            className="text-[12px] font-medium text-ink-100"
          >
            {field.label}
            {required && <span className="text-accent-rose ml-0.5">*</span>}
            {presetOptional && (
              <span className="ml-1.5 text-[10px] uppercase tracking-wide text-ink-500">
                optional
              </span>
            )}
          </label>
          <div className="mt-0.5">
            <FieldDescription field={field} />
          </div>
        </div>
        <Badge variant={SOURCE_VARIANT[field.source] ?? "outline"}>
          {field.source === "missing" ? "not set" : field.source}
        </Badge>
      </div>
      <div className="mt-2 flex gap-2">
        <Input
          id={`${field.key_name}-input`}
          type={field.is_secret ? "password" : "text"}
          placeholder={
            field.source === "vault" || field.source === "env"
              ? "•••••• configured — type to replace"
              : field.placeholder
          }
          autoComplete="off"
          spellCheck={false}
          value={value}
          onChange={(e) => onChange(e.target.value)}
          disabled={!vaultEnabled || field.source === "env"}
          className="font-mono"
        />
        {field.source === "vault" && (
          <Button
            variant="outline"
            size="sm"
            onClick={onDelete}
            title="Remove this stored secret"
          >
            <Trash2 className="h-3.5 w-3.5" />
          </Button>
        )}
      </div>
      {presetHint && (
        <div className="mt-1.5 text-[11px] text-ink-400">{presetHint}</div>
      )}
      {field.source === "env" && (
        <div className="mt-1.5 text-[11px] text-ink-500 italic">
          Already configured outside the vault. Remove it from your environment to manage it here.
        </div>
      )}
    </div>
  );
}
