import React from 'react';
import { View, Text, StyleSheet, TouchableOpacity, ActivityIndicator } from 'react-native';
import { Colors, Radius, Spacing, Typography } from '../theme';

// ─── StatusDot ───────────────────────────────────────────────────────────────
export const StatusDot: React.FC<{ ok: boolean; size?: number }> = ({ ok, size = 8 }) => (
  <View style={[
    styles.dot,
    { width: size, height: size, borderRadius: size / 2, backgroundColor: ok ? Colors.green : Colors.red }
  ]} />
);

// ─── Badge ───────────────────────────────────────────────────────────────────
type BadgeVariant = 'green' | 'red' | 'blue' | 'amber' | 'gray';

const badgeColors: Record<BadgeVariant, { bg: string; border: string; text: string }> = {
  green: { bg: Colors.greenLight, border: Colors.greenBorder, text: Colors.green },
  red:   { bg: Colors.redLight,   border: Colors.redBorder,   text: Colors.red   },
  blue:  { bg: Colors.blueLight,  border: Colors.blueBorder,  text: Colors.blue  },
  amber: { bg: Colors.amberLight, border: Colors.amberBorder, text: Colors.amber },
  gray:  { bg: '#F9FAFB',         border: '#E5E7EB',          text: '#6B7280'    },
};

export const Badge: React.FC<{ label: string; variant?: BadgeVariant; size?: 'sm' | 'md' }> = ({
  label, variant = 'gray', size = 'sm',
}) => {
  const c = badgeColors[variant];
  return (
    <View style={[
      styles.badge,
      { backgroundColor: c.bg, borderColor: c.border },
      size === 'md' && { paddingHorizontal: 10, paddingVertical: 4, borderRadius: Radius.md },
    ]}>
      <Text style={[styles.badgeText, { color: c.text }, size === 'md' && { fontSize: 12 }]}>
        {label.toUpperCase()}
      </Text>
    </View>
  );
};

// ─── Card ─────────────────────────────────────────────────────────────────────
export const Card: React.FC<{
  children: React.ReactNode;
  style?: object;
  onPress?: () => void;
}> = ({ children, style, onPress }) => {
  if (onPress) {
    return (
      <TouchableOpacity activeOpacity={0.7} onPress={onPress} style={[styles.card, style]}>
        {children}
      </TouchableOpacity>
    );
  }
  return <View style={[styles.card, style]}>{children}</View>;
};

// ─── MetricCard ──────────────────────────────────────────────────────────────
export const MetricCard: React.FC<{
  label: string;
  value: string;
  sub?: string;
  accent?: BadgeVariant;
  onPress?: () => void;
}> = ({ label, value, sub, accent = 'blue', onPress }) => {
  const c = badgeColors[accent];
  return (
    <Card onPress={onPress} style={styles.metricCard}>
      <Text style={[Typography.label, { marginBottom: Spacing.sm }]}>{label}</Text>
      <Text style={[Typography.heading1, { color: c.text, marginBottom: 2 }]}>{value}</Text>
      {sub ? <Text style={Typography.bodySmall}>{sub}</Text> : null}
    </Card>
  );
};

// ─── SectionHeader ───────────────────────────────────────────────────────────
export const SectionHeader: React.FC<{
  title: string;
  sub?: string;
  action?: React.ReactNode;
}> = ({ title, sub, action }) => (
  <View style={styles.sectionHeader}>
    <View style={{ flex: 1 }}>
      <Text style={Typography.heading3}>{title}</Text>
      {sub ? <Text style={[Typography.bodySmall, { marginTop: 2 }]}>{sub}</Text> : null}
    </View>
    {action}
  </View>
);

// ─── PrimaryButton ────────────────────────────────────────────────────────────
export const PrimaryButton: React.FC<{
  label: string;
  onPress: () => void;
  loading?: boolean;
  disabled?: boolean;
  variant?: 'primary' | 'ghost' | 'danger';
  icon?: React.ReactNode;
}> = ({ label, onPress, loading, disabled, variant = 'primary', icon }) => {
  const variantStyle = {
    primary: { bg: Colors.blue,  text: Colors.white, border: Colors.blue  },
    ghost:   { bg: Colors.white, text: Colors.primary, border: Colors.border },
    danger:  { bg: Colors.white, text: Colors.red,   border: Colors.redBorder },
  }[variant];

  return (
    <TouchableOpacity
      onPress={onPress}
      disabled={loading || disabled}
      activeOpacity={0.75}
      style={[
        styles.btn,
        { backgroundColor: variantStyle.bg, borderColor: variantStyle.border },
        (loading || disabled) && { opacity: 0.5 },
      ]}
    >
      {loading
        ? <ActivityIndicator size="small" color={variantStyle.text} />
        : (
          <View style={styles.btnInner}>
            {icon}
            <Text style={[styles.btnText, { color: variantStyle.text }]}>{label}</Text>
          </View>
        )
      }
    </TouchableOpacity>
  );
};

// ─── EmptyState ──────────────────────────────────────────────────────────────
export const EmptyState: React.FC<{ icon?: string; title: string; sub?: string }> = ({ icon, title, sub }) => (
  <View style={styles.empty}>
    {icon ? <Text style={styles.emptyIcon}>{icon}</Text> : null}
    <Text style={[Typography.heading3, { textAlign: 'center', marginBottom: 4 }]}>{title}</Text>
    {sub ? <Text style={[Typography.bodySmall, { textAlign: 'center' }]}>{sub}</Text> : null}
  </View>
);

// ─── ErrorBanner ─────────────────────────────────────────────────────────────
export const ErrorBanner: React.FC<{ message: string; onDismiss?: () => void }> = ({ message, onDismiss }) => (
  <View style={styles.errorBanner}>
    <Text style={styles.errorText} numberOfLines={3}>{message}</Text>
    {onDismiss && (
      <TouchableOpacity onPress={onDismiss}>
        <Text style={[styles.errorText, { fontWeight: '700', marginLeft: 8 }]}>✕</Text>
      </TouchableOpacity>
    )}
  </View>
);

// ─── Divider ─────────────────────────────────────────────────────────────────
export const Divider = () => <View style={styles.divider} />;

// ─── Styles ──────────────────────────────────────────────────────────────────
const styles = StyleSheet.create({
  dot: {
    flexShrink: 0,
  },
  badge: {
    paddingHorizontal: 6, paddingVertical: 2,
    borderRadius: Radius.sm, borderWidth: 1,
    alignSelf: 'flex-start',
  },
  badgeText: {
    fontSize: 10, fontWeight: '700', letterSpacing: 0.4,
  },
  card: {
    backgroundColor: Colors.white,
    borderRadius: Radius.lg,
    borderWidth: 1, borderColor: Colors.border,
    padding: Spacing.md,
    marginBottom: Spacing.sm,
  },
  metricCard: {
    flex: 1, minWidth: 140,
    marginBottom: Spacing.md,
  },
  sectionHeader: {
    flexDirection: 'row', alignItems: 'flex-end',
    justifyContent: 'space-between',
    marginBottom: Spacing.md,
  },
  btn: {
    borderRadius: Radius.md, borderWidth: 1,
    paddingVertical: 10, paddingHorizontal: 18,
    alignItems: 'center', justifyContent: 'center',
  },
  btnInner: {
    flexDirection: 'row', alignItems: 'center', gap: 6,
  },
  btnText: {
    fontSize: 14, fontWeight: '600',
  },
  empty: {
    alignItems: 'center', paddingVertical: 48, paddingHorizontal: 24,
  },
  emptyIcon: {
    fontSize: 40, marginBottom: 12,
  },
  errorBanner: {
    backgroundColor: Colors.redLight, borderWidth: 1, borderColor: Colors.redBorder,
    borderRadius: Radius.md, padding: Spacing.md,
    flexDirection: 'row', alignItems: 'center',
    marginBottom: Spacing.md,
  },
  errorText: {
    color: Colors.red, fontSize: 13, flex: 1,
  },
  divider: {
    height: 1, backgroundColor: Colors.borderLight, marginVertical: Spacing.sm,
  },
});
