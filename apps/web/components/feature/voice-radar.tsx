import * as React from "react";

type Slider = { key: string; value: number };

export function VoiceRadar({ sliders, size = 220 }: { sliders: Slider[]; size?: number }) {
  if (!sliders.length) {
    sliders = [
      { key: "expert", value: 0.5 },
      { key: "playful", value: 0.5 },
      { key: "contrarian", value: 0.5 },
      { key: "warm", value: 0.5 },
    ];
  }
  const cx = size / 2;
  const cy = size / 2;
  const radius = size / 2 - 28;
  const angleFor = (i: number) => -Math.PI / 2 + (i * 2 * Math.PI) / sliders.length;
  const point = (v: number, i: number) => {
    const a = angleFor(i);
    return [cx + Math.cos(a) * radius * v, cy + Math.sin(a) * radius * v] as const;
  };
  const polyPoints = sliders
    .map((s, i) => {
      const [x, y] = point(Math.max(0.05, s.value), i);
      return `${x.toFixed(1)},${y.toFixed(1)}`;
    })
    .join(" ");

  return (
    <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`} className="block">
      <defs>
        <radialGradient id="voice-fill" cx="50%" cy="50%" r="50%">
          <stop offset="0%" stopColor="#8b5cf6" stopOpacity={0.45} />
          <stop offset="100%" stopColor="#22d3ee" stopOpacity={0.05} />
        </radialGradient>
        <linearGradient id="voice-stroke" x1="0" y1="0" x2="1" y2="1">
          <stop offset="0%" stopColor="#8b5cf6" />
          <stop offset="100%" stopColor="#22d3ee" />
        </linearGradient>
      </defs>

      {/* concentric guides */}
      {[0.25, 0.5, 0.75, 1].map((r, idx) => (
        <circle
          key={idx}
          cx={cx}
          cy={cy}
          r={radius * r}
          fill="none"
          stroke="rgba(255,255,255,0.05)"
          strokeWidth={1}
        />
      ))}

      {/* axes */}
      {sliders.map((_, i) => {
        const [x, y] = point(1, i);
        return (
          <line
            key={i}
            x1={cx}
            y1={cy}
            x2={x}
            y2={y}
            stroke="rgba(255,255,255,0.05)"
            strokeWidth={1}
          />
        );
      })}

      {/* data polygon */}
      <polygon
        points={polyPoints}
        fill="url(#voice-fill)"
        stroke="url(#voice-stroke)"
        strokeWidth={1.5}
      />

      {/* points + labels */}
      {sliders.map((s, i) => {
        const [px, py] = point(s.value, i);
        const [lx, ly] = point(1.18, i);
        return (
          <g key={s.key}>
            <circle cx={px} cy={py} r={3} fill="#8b5cf6" stroke="#0a0c12" strokeWidth={2} />
            <text
              x={lx}
              y={ly}
              fontSize={10}
              textAnchor="middle"
              dominantBaseline="middle"
              fill="rgba(229,232,239,0.85)"
              style={{ textTransform: "uppercase", letterSpacing: "0.18em" }}
            >
              {s.key}
            </text>
            <text
              x={lx}
              y={ly + 12}
              fontSize={11}
              textAnchor="middle"
              dominantBaseline="middle"
              fill="rgba(255,255,255,0.95)"
              fontWeight={600}
            >
              {Math.round(s.value * 100)}
            </text>
          </g>
        );
      })}
    </svg>
  );
}
