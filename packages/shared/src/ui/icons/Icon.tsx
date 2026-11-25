import type { CSSProperties } from 'react'
import { iconData, type IconName } from './iconData'

export type { IconName }

interface IconProps {
  name: IconName
  size?: number
  color?: string
  className?: string
  style?: CSSProperties
  /** Accessible label. Without it the icon is decorative. */
  label?: string
}

/** Material icon with the Flutter `Icons.*` name, rendered as inline SVG. */
export function Icon({ name, size = 24, color, className, style, label }: IconProps) {
  const { viewBox, body } = iconData[name]
  return (
    <svg
      viewBox={viewBox}
      width={size}
      height={size}
      fill={color ?? 'currentColor'}
      className={className}
      style={{ flexShrink: 0, ...style }}
      role={label ? 'img' : undefined}
      aria-label={label}
      aria-hidden={label ? undefined : true}
      focusable="false"
      // body is SVG markup from the icon set bundled with the app, never user input.
      // nosemgrep: typescript.react.security.audit.react-dangerouslysetinnerhtml.react-dangerouslysetinnerhtml
      dangerouslySetInnerHTML={{ __html: body }}
    />
  )
}
