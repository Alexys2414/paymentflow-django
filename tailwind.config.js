/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    "./dashboard/templates/**/*.html",
    "./dashboard/static/dashboard/src/**/*.js"
  ],
  darkMode: ["class", '[data-theme="dark"]'],
  theme: {
    extend: {}
  },
  plugins: []
};
