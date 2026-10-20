/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    "./dashboard/templates/**/*.html",
    "./dashboard/static/dashboard/src/**/*.js"
  ],
  // Los estados se construyen dinámicamente desde los valores internos de Django.
  // Tailwind no puede descubrir `status-{{ status }}` durante el análisis.
  safelist: [
    "status-PAID",
    "status-PENDING",
    "status-FAILED",
    "status-EXPIRED",
    "status-bar-PAID",
    "status-bar-PENDING",
    "status-bar-FAILED",
    "status-bar-EXPIRED"
  ],
  darkMode: ["class", '[data-theme="dark"]'],
  theme: {
    extend: {}
  },
  plugins: []
};
