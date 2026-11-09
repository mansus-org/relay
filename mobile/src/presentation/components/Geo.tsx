import Svg, { Defs, Path, Pattern, Rect } from 'react-native-svg'
import { StyleSheet, View, type ViewStyle } from 'react-native'

import { colors } from '../theme'

type Place = Pick<ViewStyle, 'top' | 'right' | 'left' | 'bottom'>

type ShapeProps = Place & { size: number; color?: string }

const place = ({ top, right, left, bottom }: Place): ViewStyle => ({ position: 'absolute', top, right, left, bottom })

export function GeoSun({ size, color = colors.ochre, ...at }: ShapeProps) {
  return <View style={[place(at), { width: size, height: size, borderRadius: size / 2, backgroundColor: color }]} />
}

export function GeoRing({ size, color = colors.paper, ...at }: ShapeProps) {
  return (
    <View
      style={[place(at), { width: size, height: size, borderRadius: size / 2, borderWidth: 3, borderColor: color, opacity: 0.5 }]}
    />
  )
}

export function GeoSquare({ size, color = colors.red, ...at }: ShapeProps) {
  return <View style={[place(at), { width: size, height: size, backgroundColor: color }]} />
}

/** Triangle matching `.geo-wedge` (clip-path 0 30%, 100% 0, 25% 100%); `flip` mirrors it. */
export function GeoWedge({ size, color = colors.red, flip = false, ...at }: ShapeProps & { flip?: boolean }) {
  const w = size
  const h = size * 0.42
  const d = flip
    ? `M${w} ${h * 0.3} L0 0 L${w * 0.75} ${h} Z`
    : `M0 ${h * 0.3} L${w} 0 L${w * 0.25} ${h} Z`
  return (
    <View style={[place(at), { width: w, height: h }]}>
      <Svg width={w} height={h}>
        <Path d={d} fill={color} />
      </Svg>
    </View>
  )
}

export function GeoBar({ width, color = colors.red, rotate = '-12deg', ...at }: Place & { width: number; color?: string; rotate?: string }) {
  return <View style={[place(at), { width, height: 16, backgroundColor: color, transform: [{ rotate }] }]} />
}

/** Graph paper on a black band: 26px cells in faint paper lines. */
export function GridPaperDark() {
  return (
    <Svg style={{ position: 'absolute', top: 0, left: 0, right: 0, bottom: 0 }} width="100%" height="100%">
      <Defs>
        <Pattern id="grid" width={26} height={26} patternUnits="userSpaceOnUse">
          <Path d="M26 0 H0 V26" fill="none" stroke={colors.paper} strokeOpacity={0.08} strokeWidth={1} />
        </Pattern>
      </Defs>
      <Rect width="100%" height="100%" fill="url(#grid)" />
    </Svg>
  )
}

/** The same graph paper the other way round, for a light surface: faint ink lines on paper. */
export function GridPaperLight() {
  return (
    <Svg style={StyleSheet.absoluteFill} width="100%" height="100%">
      <Defs>
        <Pattern id="grid-light" width={26} height={26} patternUnits="userSpaceOnUse">
          <Path d="M26 0 H0 V26" fill="none" stroke={colors.ink} strokeOpacity={0.09} strokeWidth={1} />
        </Pattern>
      </Defs>
      <Rect width="100%" height="100%" fill="url(#grid-light)" />
    </Svg>
  )
}
