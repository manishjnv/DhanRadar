import type { Config } from 'tailwindcss';
// Reads CSS vars from styles/tokens.css. Theme switch = class on <html>.
export default {
  darkMode: ['class', '.theme-dark'],
  theme: { extend: {
    colors: {
      navy: '#0B1F3A', blue: { DEFAULT: '#2563EB', 700: '#1D4ED8' }, emerald: '#10B981',
      bg: 'var(--bg)', 'bg-alt': 'var(--bg-alt)', surface: 'var(--surface)',
      'surface-2': 'var(--surface-2)', ink: 'var(--text)', 'ink-2': 'var(--text-secondary)',
      'ink-muted': 'var(--text-muted)', line: 'var(--border)', 'line-strong': 'var(--border-strong)',
      positive: 'var(--positive)', negative: 'var(--negative)', warn: 'var(--warn)',
    },
    fontFamily: { display: ['Manrope','sans-serif'], sans: ['Inter','sans-serif'], mono: ['JetBrains Mono','monospace'] },
    borderRadius: { md: '8px', lg: '12px', xl: '16px', '2xl': '20px' },
  }},
} satisfies Partial<Config>;
