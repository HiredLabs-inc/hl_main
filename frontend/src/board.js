// The staff dashboard's board (pipeline/templates/pipeline/partials/board*.html).
// A move swaps one card in place; this files it under its step's column,
// keeps focus on it and fades the "just moved" ring. Undo on the move toast
// is a second move back.
import htmx from 'htmx.org'

const RING_MS = 4000

// A refused move (409, 403, 400) still answers with the card as it now is
htmx.on('htmx:beforeSwap', (event) => {
  if (event.detail.xhr.getResponseHeader('HX-Board-Card')) {
    event.detail.shouldSwap = true
    event.detail.isError = false
  }
})

htmx.onLoad((element) => {
  if (!element.matches || !element.matches('[data-board-card]')) return
  const step = element.dataset.step
  const column = document.querySelector(`[data-board-cards="${step}"]`)
  if (!column) {
    // Its step is on a phase the filters hide
    element.remove()
    return
  }
  if (element.parentElement !== column) {
    column.append(element)
    window.dispatchEvent(new CustomEvent('board-open', { detail: Number(step) }))
  }
  // The swap took focus from the menu; give it back once a collapsed column has opened
  if (!document.activeElement || document.activeElement === document.body) {
    setTimeout(() => {
      const button = element.querySelector('[data-move-button]')
      if (button) button.focus({ preventScroll: true })
      element.scrollIntoView({ block: 'nearest', inline: 'nearest' })
    })
  }
  if (element.hasAttribute('data-board-moved')) {
    setTimeout(() => element.classList.remove('ring-2', 'ring-hl-blue'), RING_MS)
  }
})

// Called by the toaster's Undo with the toast's undo: {url, card, values}
window.boardUndo = ({ url, card, values }) => {
  const target = document.getElementById(card)
  if (target) {
    htmx.ajax('POST', url, { target, swap: 'outerHTML', values })
  } else {
    // The card isn't on the page (filtered out), so redraw the board after
    htmx.ajax('POST', url, { swap: 'none', values }).then(() => htmx.trigger(document.body, 'enrollment-changed'))
  }
}
