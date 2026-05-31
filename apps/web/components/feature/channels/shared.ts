import type { StyleProfile } from "@/lib/types";

/**
 * Shared constants/helpers for the Channels UI.
 *
 * Note on style profiles: the backend exposes a single default StyleProfile
 * (`GET /style-profile`) rather than a list endpoint. So the selector offers
 * "Default profile" (its id) plus an explicit "No style profile" option. When
 * a channel already references some other profile id (e.g. created via API),
 * we still surface that id so the value round-trips correctly.
 */

export const STYLE_NONE_VALUE = "__none__";

export const LANG_OPTIONS: { value: string; label: string }[] = [
  { value: "ru", label: "Русский (ru)" },
  { value: "en", label: "Английский (en)" },
  { value: "uz", label: "Узбекский (uz)" },
];

// Native <select> styled to match the dark Input. Kept as a string so both
// the create sheet and the card editor render identically.
export const selectClassName =
  "flex h-9 w-full appearance-none rounded-lg border border-white/[0.08] bg-white/[0.03] px-3 py-2 text-sm text-ink-50 transition-colors focus:outline-none focus:border-accent-violet/40 focus:bg-white/[0.05] disabled:cursor-not-allowed disabled:opacity-50";

export type StyleOption = { value: string; label: string };

/**
 * Build the style-profile <select> options from the known default profile,
 * optionally including a channel's currently-attached id even when it is not
 * the default (so the displayed value never silently resets).
 */
export function styleOptionsFrom(
  profile: StyleProfile | null,
  currentId?: string | null,
): StyleOption[] {
  const options: StyleOption[] = [
    { value: STYLE_NONE_VALUE, label: "Без стиля" },
  ];
  const seen = new Set<string>();
  if (profile?.id) {
    options.push({ value: profile.id, label: `${profile.name || "по умолчанию"} (по умолчанию)` });
    seen.add(profile.id);
  }
  if (currentId && !seen.has(currentId)) {
    options.push({ value: currentId, label: `Профиль ${currentId.slice(0, 8)}…` });
  }
  return options;
}

export function styleLabelFor(
  styleId: string | null,
  profile: StyleProfile | null,
): string {
  if (!styleId) return "Без стиля";
  if (profile?.id && profile.id === styleId) return profile.name || "по умолчанию";
  return `${styleId.slice(0, 8)}…`;
}
