/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        bg: "#0a0e1a",
        panel: "#141a2c",
        border: "#222a44",
        accent: "#FFCC66",
        ytube: "#cc2229",
        pex: "#0aa777",
      },
    },
  },
  plugins: [],
};
