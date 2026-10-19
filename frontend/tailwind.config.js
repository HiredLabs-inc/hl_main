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
        // public site (templates extending new_home_base.html)
        display: ['"Plus Jakarta Sans"', ...defaultTheme.fontFamily.sans],
        code: ['"JetBrains Mono"', ...defaultTheme.fontFamily.mono],
      },
      colors: {
        'orange': '#f7941d',
        'hl-orange': '#fbb040',
        'hl-black': '#0e1f33',
        'hl-blue': '#1D80F7',
        'dark-orange': '#D97A08',
        'light-gray': '#c9cdd1',
        // public site palette
        'hl-navy': '#0e1f33',
        'hl-navy-2': '#16304B',
        'hl-navy-line': '#2E4560',
        'hl-ink': '#3B4A5C',
        'hl-muted': '#5A6878',
        'hl-line': '#E4E8EE',
        'hl-mist': '#F5F7FA',
        'hl-cream': '#FFF3E3',
        'hl-amber': '#8A4A05',
        'hl-orange-text': '#B45F06',
        'hl-steel': '#C9D1DC',
      },
    },
  },
  plugins: [
      require('@tailwindcss/forms'),
      require('preline/plugin'),
  ],
}
