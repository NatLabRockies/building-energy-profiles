/** @type {import('tailwindcss').Config} */
module.exports = {
  content: ['./src/**/*.{html,ts}'],
  darkMode: 'class',
  corePlugins: {
    // Angular Material ships its own base reset + typography. Tailwind's preflight would fight
    // with Material component internals (mat-mdc-*), so it's disabled -- Tailwind is used purely
    // for layout/spacing/utility classes alongside Material components and our existing CSS.
    preflight: false,
  },
  theme: {
    extend: {},
  },
  plugins: [],
}

