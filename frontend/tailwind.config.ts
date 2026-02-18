
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
        background: "#050209",
        primary: "#4328C0",     // Blue Violet
        secondary: "#1D0F59",   // Dark Indigo
        accent: "#9067F1",      // Lavender
        soft: "#B19ABF",        // Pastel Violet
        warm: "#5D3034",        // Warm Brown
        textLight: "#FDFCFC",   // Off-White
      },
      fontFamily: {
        sans: ['Poppins', 'sans-serif'],
      },
      backgroundImage: {
        "gradient-radial": "radial-gradient(var(--tw-gradient-stops))",
      },
    },
  },
  plugins: [],
};
export default config;
