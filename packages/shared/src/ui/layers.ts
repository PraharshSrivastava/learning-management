// Stacking layers for modal dialogs and drawers.
//
// Radix renders a dialog's overlay and its window in separate portals, and the order they are
// attached to the page depends on when each one mounts. With both on the same layer, the overlay
// can end up above the window: the window looks dimmed and every click lands on the overlay.
// The window is therefore always one layer above its overlay. Toasts (60) and tooltips (70) stay
// above both.

/** The dimmed backdrop behind a modal dialog or drawer. */
export const OVERLAY_LAYER = 'z-40'

/** The dialog or drawer window itself, always above its overlay. */
export const WINDOW_LAYER = 'z-41'
