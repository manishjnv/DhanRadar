# Tailwind Setup

```js
// tailwind.config.ts
import preset from './tokens/tailwind.config.js';
export default {
  presets: [preset],
  content: ['./src/**/*.{ts,tsx}'],
  darkMode: ['class', '.theme-dark'],
};
```
Import tokens.css in app/layout via styles/globals.css (@import './tokens.css'). Utilities: bg-surface, text-ink-muted, border-line, rounded-xl, font-display/mono. See /tokens/tailwind.config.js.
