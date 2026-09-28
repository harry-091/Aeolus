/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        'navy': '#061522',
        'polar-navy': '#0B3048',
        'antarctic-blue': '#12627A',
        'ocean-blue': '#176B87',
        'glacial-blue': '#3AA6C8',
        'ice-blue': '#8ED8E8',
        'ice-white': '#F3FAFC',
        'snow': '#EAF7FA',
        'slate': '#526573',
        'signature-coral': '#FF6B5E',
        'soft-coral': '#FF8A7A',
        'deep-coral': '#D94F45',
        'risk-safe': '#38B98A',
        'risk-caution': '#F2C94C',
        'risk-high': '#F2994A',
        'risk-critical': '#E05252'
      },
      fontFamily: {
        sans: ['"Plus Jakarta Sans"', 'Inter', 'system-ui', 'sans-serif'],
        mono: ['"JetBrains Mono"', '"IBM Plex Mono"', 'monospace'],
      },
      backgroundImage: {
        'hero-gradient': 'linear-gradient(to bottom, rgba(6, 21, 34, 0.4), rgba(6, 21, 34, 0.95))',
      }
    },
  },
  plugins: [],
}
