/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,jsx}'],
  theme: {
    extend: {
      colors: {
        base: {
          950: '#080B10',
          900: '#0A0E14',
          800: '#111722',
          700: '#1A2232',
          600: '#263044',
          500: '#3A4863',
        },
        signal: {
          teal: '#00D9C0',
          tealDim: '#0A9E8C',
          amber: '#F5A623',
          red: '#FF4757',
          blue: '#5B8DEF',
          grey: '#7B879E',
        },
      },
      fontFamily: {
        mono: ['"JetBrains Mono"', 'ui-monospace', 'SFMono-Regular', 'monospace'],
        sans: ['"Inter"', 'system-ui', 'sans-serif'],
      },
    },
  },
  plugins: [],
}
