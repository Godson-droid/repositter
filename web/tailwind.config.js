/** @type {import('tailwindcss').Config} */
// RepoSitter design tokens — OLED-first system, see DESIGN.md.
export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        // Surfaces — true black OLED ramp, no grey wash
        night: {
          950: '#000000', // page background — true black
          900: '#050507', // sunken sections
          850: '#0a0a0e', // card surface
          800: '#101016', // raised elements
          700: '#17171f', // hover states
          600: '#23232e', // strong borders
        },
        line: 'rgba(240, 240, 255, 0.08)',
        // Brand accent — iris violet, RepoSitter's own identity
        iris: {
          200: '#cdc6ff',
          300: '#b3a8ff',
          400: '#9787ff',
          500: '#7c6cff', // core accent
          600: '#6553e6',
          700: '#4f3fc0',
        },
        // Semantic
        amber: {
          300: '#fcd34d',
          400: '#fbbf24',
          500: '#f59e0b',
        },
        rose: {
          300: '#fda4af',
          400: '#fb7185',
          500: '#f43f5e',
        },
        mint: {
          300: '#6ee7b7',
          400: '#34d399',
          500: '#10b981',
        },
        // Text ramp — cool neutral, tuned for black
        moon: {
          100: '#f4f4f8', // primary text
          200: '#d9d9e2',
          300: '#c3c3cf', // secondary text
          400: '#9a9aa8',
          500: '#63636f', // captions, micro-labels
        },
      },
      fontFamily: {
        display: ['Sora', 'Inter', 'sans-serif'],
        sans: ['Inter', 'system-ui', 'sans-serif'],
        mono: ['"JetBrains Mono"', 'ui-monospace', 'SFMono-Regular', 'monospace'],
      },
      fontSize: {
        'display-xl': ['3.5rem', { lineHeight: '1.04', letterSpacing: '-0.03em' }],
        'display-lg': ['2.5rem', { lineHeight: '1.1', letterSpacing: '-0.025em' }],
        h2: ['1.875rem', { lineHeight: '1.15', letterSpacing: '-0.02em' }],
        card: ['1.1875rem', { lineHeight: '1.3', letterSpacing: '-0.01em' }],
        dense: ['0.84375rem', { lineHeight: '1.45' }],
        small: ['0.78125rem', { lineHeight: '1.45' }],
      },
      borderRadius: {
        card: '1.25rem',
        panel: '1rem',
      },
      boxShadow: {
        card: '0 1px 0 0 rgba(255,255,255,0.04) inset, 0 12px 32px -12px rgba(0,0,0,0.8)',
        glow: '0 0 0 1px rgba(124,108,255,0.4), 0 8px 40px -8px rgba(124,108,255,0.5)',
        pop: '0 16px 40px -12px rgba(0,0,0,0.9)',
      },
      keyframes: {
        'fade-up': {
          '0%': { opacity: '0', transform: 'translateY(10px)' },
          '100%': { opacity: '1', transform: 'translateY(0)' },
        },
        'ping-soft': {
          '0%': { transform: 'scale(1)', opacity: '0.7' },
          '80%, 100%': { transform: 'scale(2.6)', opacity: '0' },
        },
        'pulse-dot': {
          '0%, 100%': { opacity: '1' },
          '50%': { opacity: '0.35' },
        },
      },
      animation: {
        'fade-up': 'fade-up 0.6s cubic-bezier(0.22, 1, 0.36, 1) both',
        'ping-soft': 'ping-soft 2.2s cubic-bezier(0, 0, 0.2, 1) infinite',
        'pulse-dot': 'pulse-dot 2s ease-in-out infinite',
      },
    },
  },
  plugins: [],
}
