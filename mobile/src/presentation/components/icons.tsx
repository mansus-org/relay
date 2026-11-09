import Svg, { Circle, Path } from 'react-native-svg'

import { colors } from '../theme'

type Props = { size?: number; color?: string }

/**
 * The line icons from mobile-mockups/shared.css, drawn at the same 24 unit box with the same square
 * caps, so a row and a result read as one alphabet.
 */
const stroke = {
  fill: 'none' as const,
  strokeWidth: 2,
  strokeLinecap: 'square' as const,
  strokeLinejoin: 'miter' as const,
}


export function NodesIcon({ size = 24, color = colors.ink }: Props) {
  return (
    <Svg width={size} height={size} viewBox="0 0 24 24" accessibilityElementsHidden importantForAccessibility="no-hide-descendants">
      <Circle {...stroke} stroke={color} cx={9} cy={8} r={3.2} />
      <Path {...stroke} stroke={color} d="M3 20c0-3.3 2.7-6 6-6s6 2.7 6 6" />
      <Circle {...stroke} stroke={color} cx={17} cy={9} r={2.4} />
      <Path {...stroke} stroke={color} d="M17 14c2.2 0 4 1.8 4 4" />
    </Svg>
  )
}



export function GlobeIcon({ size = 24, color = colors.ink }: Props) {
  return (
    <Svg width={size} height={size} viewBox="0 0 24 24" accessibilityElementsHidden importantForAccessibility="no-hide-descendants">
      <Circle {...stroke} stroke={color} cx={12} cy={12} r={9} />
      <Path {...stroke} stroke={color} d="M3 12h18M12 3c3 3 3 15 0 18M12 3c-3 3-3 15 0 18" />
    </Svg>
  )
}

export function ChevronIcon({ size = 24, color = colors.ink }: Props) {
  return (
    <Svg width={size} height={size} viewBox="0 0 24 24" accessibilityElementsHidden importantForAccessibility="no-hide-descendants">
      <Path {...stroke} strokeWidth={2.4} stroke={color} d="M9 5l7 7-7 7" />
    </Svg>
  )
}

export function CheckIcon({ size = 24, color = colors.ink }: Props) {
  return (
    <Svg width={size} height={size} viewBox="0 0 24 24" accessibilityElementsHidden importantForAccessibility="no-hide-descendants">
      <Path {...stroke} strokeWidth={2.6} stroke={color} d="M5 12.5l4.5 4.5L19 7" />
    </Svg>
  )
}

export function WarnIcon({ size = 24, color = colors.ochre }: Props) {
  return (
    <Svg width={size} height={size} viewBox="0 0 24 24" accessibilityElementsHidden importantForAccessibility="no-hide-descendants">
      <Path {...stroke} strokeWidth={2.6} stroke={color} d="M12 6.5v7M12 17.5v.5" />
    </Svg>
  )
}

export function ShieldIcon({ size = 24, color = colors.ink }: Props) {
  return (
    <Svg width={size} height={size} viewBox="0 0 24 24" accessibilityElementsHidden importantForAccessibility="no-hide-descendants">
      <Path {...stroke} stroke={color} d="M12 3l8 3v6c0 4.4-3.2 7.8-8 9-4.8-1.2-8-4.6-8-9V6z" />
    </Svg>
  )
}
