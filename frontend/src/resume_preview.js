// The resume preview (resume/templates/resume/base_resume.html) doesn't extend
// base.html, so it loads htmx and Alpine from here for its inline edit and
// delete controls. No CSS: Tailwind's preflight would restyle the resume.
import htmx from 'htmx.org'
import Alpine from 'alpinejs'

window.htmx = htmx
window.Alpine = Alpine
Alpine.start()
