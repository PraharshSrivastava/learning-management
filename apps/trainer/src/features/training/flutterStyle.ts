/**
 * Flutter draws fractional borders (1.5 px) with anti-aliasing. Chrome snaps CSS borders to whole
 * pixels. An inset shadow keeps the fractional width and never changes the layout.
 */
export const ring = (width: number, color: string): string => `inset 0 0 0 ${width}px ${color}`
