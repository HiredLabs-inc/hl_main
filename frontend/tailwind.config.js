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
    },
  },
  plugins: [
    require('@tailwindcss/forms'),
    require('preline/plugin'),
  ],
}

