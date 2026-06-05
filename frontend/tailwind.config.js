// DhanRadar — Tailwind config
// Design tokens are generated from styles/tokens.json via scripts/gen-tokens.mjs
// DO NOT hand-edit colours/type here; edit tokens.json and re-run gen:tokens.

/** @type {import('tailwindcss').Config} */
module.exports = {
  presets: [require('./tailwind.tokens.cjs')],
  darkMode: ['class', '.theme-dark'],
  content: [
    './src/**/*.{ts,tsx}',
    './app/**/*.{ts,tsx}',
  ],
};
