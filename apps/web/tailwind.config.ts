import type { Config } from "tailwindcss";

const config: Config = {
  darkMode: "class",
  content: [
    "./app/**/*.{ts,tsx}",
    "./components/**/*.{ts,tsx}",
    "./lib/**/*.{ts,tsx}",
  ],
  theme: {
    container: {
      center: true,
      padding: { DEFAULT: "1rem", sm: "1.5rem", lg: "2rem" },
      screens: { "2xl": "1400px", "3xl": "1600px", "4xl": "1920px" },
    },
    screens: {
      sm: "640px",
      md: "768px",
      lg: "1024px",
      xl: "1280px",
      "2xl": "1536px",
      "3xl": "1920px",
      "4xl": "2560px",
    },
    extend: {
      fontFamily: {
        sans: [
          "var(--font-inter)",
          "ui-sans-serif",
          "system-ui",
          "-apple-system",
          "Segoe UI",
          "Helvetica Neue",
          "Arial",
        ],
        mono: ["ui-monospace", "JetBrains Mono", "SFMono-Regular", "Menlo", "monospace"],
      },
      colors: {
        bg: {
          base: "#06070b",
          raised: "#0a0c12",
          sunken: "#04050a",
          panel: "#0d1018",
        },
        ink: {
          50: "#f5f6f8",
          100: "#e6e8ee",
          200: "#c5cad4",
          300: "#9ea4b1",
          400: "#737a89",
          500: "#525866",
          600: "#3b414e",
          700: "#262b36",
          800: "#171a22",
          900: "#0d1018",
        },
        accent: {
          violet: "#8b5cf6",
          "violet-dim": "#6d4dd6",
          "violet-deep": "#5b3fb8",
          cyan: "#22d3ee",
          "cyan-dim": "#0e9fb6",
          amber: "#f59e0b",
          rose: "#fb7185",
          mint: "#34d399",
          emerald: "#10b981",
        },
        state: {
          success: "#34d399",
          warning: "#f59e0b",
          danger: "#fb7185",
          info: "#22d3ee",
        },
        glass: {
          DEFAULT: "rgba(255,255,255,0.025)",
          strong: "rgba(255,255,255,0.055)",
          line: "rgba(255,255,255,0.07)",
          "line-strong": "rgba(255,255,255,0.13)",
        },
      },
      borderRadius: {
        xl: "14px",
        "2xl": "18px",
        "3xl": "24px",
      },
      boxShadow: {
        glow: "0 0 0 1px rgba(139, 92, 246, 0.24), 0 18px 48px -18px rgba(139, 92, 246, 0.35)",
        "glow-cyan": "0 0 0 1px rgba(34, 211, 238, 0.24), 0 18px 48px -18px rgba(34, 211, 238, 0.35)",
        card: "0 1px 0 rgba(255,255,255,0.04) inset, 0 0 0 1px rgba(255,255,255,0.05), 0 28px 60px -32px rgba(0,0,0,0.75)",
        "card-hover": "0 1px 0 rgba(255,255,255,0.06) inset, 0 0 0 1px rgba(255,255,255,0.10), 0 36px 72px -32px rgba(0,0,0,0.85)",
        elev: "0 36px 90px -42px rgba(139, 92, 246, 0.55), 0 0 0 1px rgba(255,255,255,0.06)",
        "inner-line": "inset 0 1px 0 rgba(255,255,255,0.07)",
      },
      backgroundImage: {
        "grid-glow":
          "radial-gradient(80% 60% at 20% 0%, rgba(139, 92, 246, 0.14), transparent 60%), radial-gradient(60% 40% at 90% 30%, rgba(34, 211, 238, 0.10), transparent 60%)",
        "card-shine":
          "linear-gradient(135deg, rgba(255,255,255,0.07) 0%, rgba(255,255,255,0.02) 40%, rgba(255,255,255,0) 100%)",
        "mesh-fade":
          "linear-gradient(180deg, rgba(8,9,13,0) 0%, rgba(8,9,13,0.8) 60%, rgba(8,9,13,1) 100%)",
        "violet-mesh":
          "radial-gradient(120% 80% at 50% 0%, rgba(139, 92, 246, 0.16), rgba(139, 92, 246, 0) 60%)",
        "hairline":
          "linear-gradient(90deg, rgba(255,255,255,0) 0%, rgba(255,255,255,0.10) 20%, rgba(255,255,255,0.10) 80%, rgba(255,255,255,0) 100%)",
      },
      animation: {
        "pulse-soft": "pulseSoft 3.4s ease-in-out infinite",
        shimmer: "shimmer 2.2s linear infinite",
        "fade-in": "fadeIn 0.5s ease-out",
      },
      keyframes: {
        pulseSoft: {
          "0%, 100%": { opacity: "0.7" },
          "50%": { opacity: "1" },
        },
        shimmer: {
          "0%": { backgroundPosition: "-200% 0" },
          "100%": { backgroundPosition: "200% 0" },
        },
        fadeIn: {
          "0%": { opacity: "0", transform: "translateY(4px)" },
          "100%": { opacity: "1", transform: "translateY(0)" },
        },
      },
    },
  },
  plugins: [require("tailwindcss-animate")],
};

export default config;
