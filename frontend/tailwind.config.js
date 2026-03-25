/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,jsx,ts,tsx}"],
  theme: {
    extend: {
      colors: {
        surface: "#0d0d0d",
        "surface-1": "#161616",
        "surface-2": "#1e1e1e",
        border: "#2a2a2a",
        "text-primary": "#e8e8e8",
        "text-muted": "#888888",
        accent: "#4ade80",
        "accent-dim": "#166534",
        danger: "#f87171",
      },
      fontFamily: {
        sans: ["Inter", "system-ui", "sans-serif"],
        mono: ["JetBrains Mono", "Fira Code", "monospace"],
      },
      maxWidth: {
        content: "720px",
      },
    },
  },
  plugins: [],
};
