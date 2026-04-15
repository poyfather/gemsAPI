import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./components/**/*.{js,ts,jsx,tsx,mdx}",
    "./app/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        gem: {
          bg:      "#080810",
          surface: "#0f0f1a",
          card:    "#13131f",
          border:  "#1e1e32",
          hover:   "#1a1a2e",
          accent:  "#7c3aed",
          "accent-hover": "#6d28d9",
          "accent-muted": "#4c1d95",
        },
      },
      fontFamily: {
        mono: ["var(--font-mono)", "ui-monospace", "SFMono-Regular", "monospace"],
      },
    },
  },
  plugins: [],
};

export default config;
