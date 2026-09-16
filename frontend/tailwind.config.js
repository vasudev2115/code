/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
  theme: {
    extend: {
      colors: {
        ops: {
          bg: "#0b0f14",
          panel: "#131a22",
          border: "#1f2833",
          accent: "#4ade80",
        },
      },
    },
  },
  plugins: [],
};
