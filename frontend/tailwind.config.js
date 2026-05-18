// DhanRadar — Tailwind preset
// Usage:  presets: [require('./brand/tailwind.config.js')]

module.exports = {
  theme: {
    extend: {
      colors: {
        navy:    '#0B1F3A',
        royal:   '#1E5EFF',
        emerald: { DEFAULT: '#00B386', dark: '#1FD79A' },
        cyan:    '#00C2FF',
        amber:   '#F5A623',
        red:     { DEFAULT: '#E5484D', dark: '#FF6166' },

        // Surfaces (use with CSS vars in your globals.css for theme switching)
        bg: 'var(--bg)',
        surface: 'var(--surface)',
        'surface-2': 'var(--surface-2)',
        'surface-3': 'var(--surface-3)',
        ink: 'var(--text)',
        'ink-secondary': 'var(--text-secondary)',
        'ink-muted': 'var(--text-muted)',
        'ink-faint': 'var(--text-faint)',
        line: 'var(--border)',
        'line-strong': 'var(--border-strong)',
      },
      fontFamily: {
        sans:  ['Geist', 'ui-sans-serif', 'system-ui', '-apple-system', 'sans-serif'],
        mono:  ['Geist Mono', 'ui-monospace', 'SF Mono', 'monospace'],
        serif: ['Instrument Serif', 'Georgia', 'serif'],
      },
      fontSize: {
        'display':  ['64px', { lineHeight: '1.02', letterSpacing: '-0.035em', fontWeight: '500' }],
        'h1':       ['40px', { lineHeight: '1.05', letterSpacing: '-0.025em', fontWeight: '500' }],
        'h2':       ['28px', { lineHeight: '1.15', letterSpacing: '-0.02em',  fontWeight: '500' }],
        'h3':       ['18px', { lineHeight: '1.3',  letterSpacing: '-0.01em',  fontWeight: '500' }],
        'body':     ['15px', { lineHeight: '1.55', letterSpacing: '-0.005em' }],
        'small':    ['13px', { lineHeight: '1.45' }],
        'caption':  ['11px', { lineHeight: '1.3',  letterSpacing: '0.08em', fontWeight: '500' }],
      },
      borderRadius: {
        sm:  '4px',
        md:  '8px',
        lg:  '12px',
        xl:  '14px',
        '2xl': '18px',
      },
      boxShadow: {
        sm: '0 1px 2px rgba(15,20,35,0.04)',
        md: '0 4px 16px rgba(15,20,35,0.06)',
        lg: '0 24px 60px -20px rgba(15,20,35,0.18)',
      },
    },
  },
};
