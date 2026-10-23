import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        ink: "#1c1b33",
        cream: "#fff4dc",
        paper: "#fffdf7",
        sun: "#ffd43b",
        mint: "#36d6a0",
        lilac: "#c3b1ff",
        sky: "#8fd3ff",
        blush: "#ff9aa2",
        flame: "#ff6a3d",
        amber: "#ffb35c",
        fog: "#e7e4ef",
      },
      fontFamily: {
        serif: ["Georgia", "'Times New Roman'", "serif"],
        sans: ["ui-rounded", "'Trebuchet MS'", "system-ui", "sans-serif"],
      },
      boxShadow: {
        hard: "4px 4px 0 0 #1c1b33",
        "hard-sm": "2px 2px 0 0 #1c1b33",
      },
    },
  },
  plugins: [],
};

export default config;
