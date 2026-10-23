import { useColorScheme } from 'react-native';

// ─── RootTrace design tokens ───────────────────────────────────────────────────
export const Colors = {
  // Primary palette
  blue:         '#2563EB',
  blueLight:    '#EFF6FF',
  blueBorder:   '#BFDBFE',

  // Status
  green:        '#16A34A',
  greenLight:   '#F0FDF4',
  greenBorder:  '#BBF7D0',

  red:          '#DC2626',
  redLight:     '#FFF1F2',
  redBorder:    '#FECDD3',

  amber:        '#D97706',
  amberLight:   '#FFFBEB',
  amberBorder:  '#FDE68A',

  // Neutrals
  white:        '#FFFFFF',
  surface:      '#F9FAFB',
  border:       '#E5E7EB',
  borderLight:  '#F3F4F6',
  muted:        '#9CA3AF',
  secondary:    '#6B7280',
  primary:      '#374151',
  heading:      '#111827',

  // Dark palette (kept for code terminal sections)
  dark:         '#111827',
  darkCard:     '#1F2937',
  darkBorder:   'rgba(255,255,255,0.1)',
  darkText:     '#F8FAFC',
  darkMuted:    '#6B7280',
} as const;

export const Spacing = {
  xs:  4,
  sm:  8,
  md:  16,
  lg:  24,
  xl:  32,
} as const;

export const Radius = {
  sm:  6,
  md:  10,
  lg:  14,
  full: 999,
} as const;

export const Typography = {
  heading1:  { fontSize: 22, fontWeight: '700' as const, color: Colors.heading, letterSpacing: -0.4 },
  heading2:  { fontSize: 17, fontWeight: '700' as const, color: Colors.heading, letterSpacing: -0.2 },
  heading3:  { fontSize: 15, fontWeight: '600' as const, color: Colors.heading },
  body:      { fontSize: 14, fontWeight: '400' as const, color: Colors.primary },
  bodySmall: { fontSize: 12, fontWeight: '400' as const, color: Colors.secondary },
  label:     { fontSize: 11, fontWeight: '600' as const, color: Colors.muted, textTransform: 'uppercase' as const, letterSpacing: 0.6 },
  mono:      { fontSize: 12, fontFamily: 'Courier New' as const, color: Colors.darkText },
} as const;
