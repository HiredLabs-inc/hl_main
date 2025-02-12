const defaultTheme = require('tailwindcss/defaultTheme')

/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    'node_modules/preline/dist/*.js',
    '../frontend/templates/**/*.html',
    '../userprofile/templates/**/*.html',
    '../bookings/templates/**/*.html',
    '../cold_apply/templates/**/*.html',
    '../resume/templates/**/*.html',
    "./src/**/*.{html,js}",
    "../core/templatetags/*.py",
    "./templatetags/*.py",
    "../templates/**/*.html",
  ],
  darkMode: 'class',
  theme: {
    extend: {
      fontFamily: {
        sans: ['Inter var', ...defaultTheme.fontFamily.sans],
      },
      colors: {
        'orange': '#f7941d',
        'hl-orange': '#fbb040',
        'hl-black': '#0e1f33',
        'hl-blue': '#1D80F7',
        'dark-orange': '#D97A08',
        'light-gray': '#c9cdd1',
      },
    },
  },
  plugins: [
      require('@tailwindcss/forms'),
      require('preline/plugin'),
  ],
}
