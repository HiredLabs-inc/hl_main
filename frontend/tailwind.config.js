/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    '../bookings/templates/**/*.html',
    '../cold_apply/templates/**/*.html',
    '../resume/templates/**/*.html',
    "./src/**/*.{html,js}",
    "../core/templatetags/*.py",
    "./templatetags/*.py"
  ],
  theme: {
    extend: {
      fontFamily: {
        inter: ['Inter', 'sans-serif'],
      },
    },
  },
  plugins: [
    require('@tailwindcss/forms'),
  ],
}

