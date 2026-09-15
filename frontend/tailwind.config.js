/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  darkMode: 'class',
  theme: {
    extend: {
      colors: {
        canvas: {
          bg: '#0f172a',
          grid: '#1e293b',
          card: '#1e293b',
          border: '#334155',
        }
      }
    },
  },
  plugins: [],
}
