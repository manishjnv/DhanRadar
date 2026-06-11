// DhanRadar Website — Tailwind preset v1.0
// Usage:  presets: [require('./design-system/tailwind.config.js')]

module.exports = {
  theme: {
    extend: {
      colors: {
        navy:    '#0B1F3A',
        blue:    { DEFAULT: '#2563EB', 600: '#2563EB', 700: '#1D4ED8', 50: '#EFF6FF' },
        emerald: { DEFAULT: '#10B981', dark: '#22D3A6' },
        cyan:    '#06B6D4',
        amber:   '#F59E0B',
        red:     '#EF4444',

        // Theme-aware (drive these via CSS vars in globals.css)
        bg:           'var(--bg)',
        'bg-alt':     'var(--bg-alt)',
        surface:      'var(--surface)',
        'surface-2':  'var(--surface-2)',
        'surface-3':  'var(--surface-3)',
        ink:          'var(--text)',
        'ink-2':      'var(--text-secondary)',
        'ink-muted':  'var(--text-muted)',
        'ink-faint':  'var(--text-faint)',
        line:         'var(--border)',
        'line-strong':'var(--border-strong)',
      },
      fontFamily: {
        display: ['Manrope', 'ui-sans-serif', 'system-ui', '-apple-system', 'sans-serif'],
        sans:    ['Inter',   'ui-sans-serif', 'system-ui', '-apple-system', 'sans-serif'],
        mono:    ['ui-monospace', 'SF Mono', 'JetBrains Mono', 'monospace'],
      },
      fontSize: {
        'display':  ['60px', { lineHeight: '1.05', letterSpacing: '-0.03em',  fontWeight: '700' }],
        'h1':       ['44px', { lineHeight: '1.08', letterSpacing: '-0.025em', fontWeight: '700' }],
        'h2':       ['32px', { lineHeight: '1.15', letterSpacing: '-0.02em',  fontWeight: '700' }],
        'h3':       ['22px', { lineHeight: '1.25', letterSpacing: '-0.015em', fontWeight: '600' }],
        'h4':       ['16px', { lineHeight: '1.4',  letterSpacing: '-0.005em', fontWeight: '600' }],
        'body':     ['16px', { lineHeight: '1.6' }],
        'small':    ['14px', { lineHeight: '1.5' }],
        'caption':  ['12px', { lineHeight: '1.3', letterSpacing: '0.08em', fontWeight: '500' }],
      },
      borderRadius: {
        sm:  '6px',
        md:  '8px',
        lg:  '12px',
        xl:  '16px',
        '2xl': '20px',
      },
      boxShadow: {
        xs: '0 1px 2px rgba(15,23,42,0.04)',
        sm: '0 1px 3px rgba(15,23,42,0.06), 0 1px 2px rgba(15,23,42,0.04)',
        md: '0 4px 12px rgba(15,23,42,0.06), 0 2px 4px rgba(15,23,42,0.04)',
        lg: '0 16px 40px -12px rgba(15,23,42,0.12)',
        xl: '0 28px 60px -20px rgba(15,23,42,0.18)',
        ring: '0 0 0 3px rgba(37,99,235,0.16)',
      },
      screens: {
        sm: '640px', md: '768px', lg: '1024px', xl: '1280px', '2xl': '1536px',
      },
      transitionTimingFunction: {
        'spring': 'cubic-bezier(0.16, 1, 0.3, 1)',
      },
    },
  },
};
