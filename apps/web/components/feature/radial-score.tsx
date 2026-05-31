import * as React from "react";

export function RadialScore({
  value,
  size = 56,
  thickness = 4,
  label,
}: {
  value: number; // 0..1
  size?: number;
  thickness?: number;
  label?: string;
}) {
  const clamped = Math.max(0, Math.min(1, value));
  const r = (size - thickness) / 2;
  const c = 2 * Math.PI * r;
  const offset = c * (1 - clamped);
  const score = Math.round(clamped * 100);
  const color = score >= 75 ? "#8b5cf6" : score >= 55 ? "#22d3ee" : "#737a89";
  return (
    <div
      className="relative grid place-items-center"
      style={{ width: size, height: size }}
      aria-label={`Рейтинг ${score}`}
    >
      <svg width={size} height={size} className="-rotate-90">
        <circle
          cx={size / 2}
          cy={size / 2}
          r={r}
          stroke="rgba(255,255,255,0.06)"
          strokeWidth={thickness}
          fill="none"
        />
        <circle
          cx={size / 2}
          cy={size / 2}
          r={r}
          stroke={color}
          strokeWidth={thickness}
          strokeLinecap="round"
          fill="none"
          strokeDasharray={c}
          strokeDashoffset={offset}
          style={{
            filter:
              score >= 75
                ? "drop-shadow(0 0 6px rgba(139,92,246,0.55))"
                : score >= 55
                ? "drop-shadow(0 0 6px rgba(34,211,238,0.4))"
                : "none",
            transition: "stroke-dashoffset 0.3s ease",
          }}
        />
      </svg>
      <div className="absolute inset-0 grid place-items-center">
        <div className="display num text-[15px] font-semibold leading-none text-ink-50">
          {score}
        </div>
        {label && (
          <div className="mt-0.5 text-[9px] uppercase tracking-[0.16em] text-ink-500">
            {label}
          </div>
        )}
      </div>
    </div>
  );
}
