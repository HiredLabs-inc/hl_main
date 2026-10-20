// The staff dashboard's board (pipeline/templates/pipeline/partials/board*.html).
// A move swaps one card in place; this files it under its step's column,
// keeps focus on it and fades the "just moved" ring. Undo on the move toast
// is a second move back. Cards can also be dragged to another column, which
// posts the same move as the Move menu.
import htmx from 'htmx.org'
import Sortable from 'sortablejs'

const RING_MS = 4000
const OVER = ['ring-2', 'ring-hl-blue']

// A refused move (409, 403, 400) still answers with the card as it now is
htmx.on('htmx:beforeSwap', (event) => {
  if (event.detail.xhr.getResponseHeader('HX-Board-Card')) {
    event.detail.shouldSwap = true
    event.detail.isError = false
  }
})

function dropTarget(list) {
  return list.closest('[data-board-column]') || list
}

function clearOver() {
  document.querySelectorAll('[data-board-over]').forEach((el) => {
    el.classList.remove(...OVER)
    el.removeAttribute('data-board-over')
  })
}

function pointerStrip(event) {
  const e = event.originalEvent
  const point = e && e.changedTouches ? e.changedTouches[0] : e
  if (!point || point.clientX === undefined) return null
  const under = document.elementFromPoint(point.clientX, point.clientY)
  return under && under.closest('[data-board-strip]')
}

function drop(card, step, strip) {
  if (strip) {
    // Dropped on a collapsed step: open it and put the card in its column
    document.querySelector(`[data-board-cards="${step}"]`).append(card)
    window.dispatchEvent(new CustomEvent('board-open', { detail: Number(step) }))
  }
  card.classList.add('board-saving')
  htmx.ajax('POST', card.dataset.moveUrl, {
    target: card,
    swap: 'outerHTML',
    values: { step, from_step: card.dataset.step, render: 'card' },
  })
}

function makeSortable(list) {
  if (Sortable.get(list)) return
  Sortable.create(list, {
    group: 'board',
    sort: false,
    draggable: '[data-board-card]',
    // Links, buttons and the menu keep working; locked cards don't move
    filter: 'a, button, [role=menu], [data-locked]',
    preventOnFilter: false,
    // Mouse events rather than HTML5 drag and drop: same behaviour everywhere
    forceFallback: true,
    fallbackOnBody: true,
    delayOnTouchOnly: true,
    delay: 150,
    emptyInsertThreshold: 24,
    ghostClass: 'opacity-40',
    onMove(event) {
      clearOver()
      if (event.to !== event.from) {
        const target = dropTarget(event.to)
        target.classList.add(...OVER)
        target.setAttribute('data-board-over', '')
      }
      // Never put the card inside a collapsed strip: it would widen the strip
      // and shift every column after it. onEnd handles a drop there.
      return !event.to.hasAttribute('data-board-strip')
    },
    onEnd(event) {
      clearOver()
      const card = event.item
      const strip = pointerStrip(event)
      if (strip) {
        drop(card, strip.dataset.boardStrip, true)
      } else if (event.to !== event.from && event.to.dataset.boardCards !== card.dataset.step) {
        drop(card, event.to.dataset.boardCards, false)
      }
    },
  })
}

htmx.onLoad((element) => {
  if (!element.querySelectorAll) return
  const lists = [element, ...element.querySelectorAll('[data-board-cards], [data-board-strip]')]
  lists.filter((el) => el.matches('[data-board-cards], [data-board-strip]')).forEach(makeSortable)
  if (!element.matches('[data-board-card]')) return
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
  } else if (element.hasAttribute('data-board-moved')) {
    // Columns are oldest in step first, and a card that just moved is the newest
    column.append(element)
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
