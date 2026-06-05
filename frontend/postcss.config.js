// PostCSS config so Next.js runs Tailwind + autoprefixer over globals.css.
// Without this (and the @tailwind directives in src/app/globals.css) no utility
// classes are generated and the app renders unstyled.
module.exports = {
  plugins: {
    tailwindcss: {},
    autoprefixer: {},
  },
};
