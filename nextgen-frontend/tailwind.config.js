/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,jsx}"],
  theme: {
    extend: {
      colors: {
        brand: {
          navy: "#221f54",
          red: "#da3f3f",
          gray: "#9c9c9c",
          border: "#e3e3e3",
          field: "#fbfbfb",
        },
      },
    },
  },
  plugins: [],
};
