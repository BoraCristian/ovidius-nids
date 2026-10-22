/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,jsx,ts,tsx}'],
  darkMode: 'class',
  theme: {
    extend: {
      colors: {
        navy: {
          950: '#050A14',
          900: '#0A1220',
          850: '#0E1828',
          800: '#12213A',
          700: '#1A2D4F',
          600: '#253E6B',
        },
        cyan: {
          400: '#22D3EE',
          500: '#06B6D4',
          600: '#0891B2',
        },
        severity: {
          low: '#38BDF8',
          medium: '#FACC15',
          high: '#FB923C',
          critical: '#EF4444',
        },
      },
      fontFamily: {
        sans: ['"Inter"', 'ui-sans-serif', 'system-ui'],
        mono: ['"JetBrains Mono"', 'ui-monospace', 'SFMono-Regular'],
      },
      boxShadow: {
        glow: '0 0 24px rgba(34,211,238,0.25)',
      },
      keyframes: {
        pulseBorder: {
          '0%,100%': { boxShadow: '0 0 0 0 rgba(34,211,238,0.0)' },
          '50%':     { boxShadow: '0 0 0 6px rgba(34,211,238,0.15)' },
        },
      },
      animation: {
        pulseBorder: 'pulseBorder 2.4s ease-in-out infinite',
      },
    },
  },
  plugins: [],
};
