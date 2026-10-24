import React from 'react';
import { View, Text, StyleSheet, TouchableOpacity, SafeAreaView, Platform, StatusBar } from 'react-native';
import { OverviewScreen }   from './src/screens/OverviewScreen';
import { InvestigateScreen } from './src/screens/InvestigateScreen';
import { IncidentsScreen }  from './src/screens/IncidentsScreen';
import { AuditScreen }      from './src/screens/AuditScreen';
import { Colors, Spacing, Radius, Typography } from './src/theme';

// ─── Tab Definition ───────────────────────────────────────────────────────────
type Tab = 'overview' | 'investigate' | 'incidents' | 'audit';

const TABS: { id: Tab; label: string; icon: string }[] = [
  { id: 'overview',    label: 'Overview',  icon: '⬡' },
  { id: 'investigate', label: 'Debug',     icon: '🔬' },
  { id: 'incidents',   label: 'Incidents', icon: '🔔' },
  { id: 'audit',       label: 'Audit',     icon: '🔒' },
];

// ─── App ─────────────────────────────────────────────────────────────────────
export default function App() {
  const [activeTab, setActiveTab] = React.useState<Tab>('overview');

  return (
    <SafeAreaView style={styles.safe}>
      <StatusBar barStyle="dark-content" />

      {/* Top Header */}
      <View style={styles.header}>
        <View style={styles.logoRow}>
          <View style={styles.logoBox}>
            <Text style={styles.logoIcon}>⎇</Text>
          </View>
          <View>
            <Text style={styles.logoText}>RootTrace</Text>
            <Text style={styles.logoSub}>Live Debug Platform</Text>
          </View>
        </View>
        {/* Status indicator — could show real health in future */}
        <View style={styles.statusPill}>
          <Text style={styles.statusText}>LIVE</Text>
        </View>
      </View>

      {/* Page Title */}
      <View style={styles.pageTitleBar}>
        <Text style={Typography.heading2}>
          {TABS.find(t => t.id === activeTab)?.label}
        </Text>
      </View>

      {/* Screen Content */}
      <View style={{ flex: 1 }}>
        {activeTab === 'overview'    && <OverviewScreen />}
        {activeTab === 'investigate' && <InvestigateScreen />}
        {activeTab === 'incidents'   && <IncidentsScreen />}
        {activeTab === 'audit'       && <AuditScreen />}
      </View>

      {/* Bottom Tab Bar */}
      <View style={styles.tabBar}>
        {TABS.map(tab => {
          const active = activeTab === tab.id;
          return (
            <TouchableOpacity
              key={tab.id}
              style={styles.tabItem}
              onPress={() => setActiveTab(tab.id)}
              activeOpacity={0.7}
            >
              <View style={[styles.tabIconWrap, active && styles.tabIconActive]}>
                <Text style={styles.tabIcon}>{tab.icon}</Text>
              </View>
              <Text style={[styles.tabLabel, active && styles.tabLabelActive]}>
                {tab.label}
              </Text>
            </TouchableOpacity>
          );
        })}
      </View>
    </SafeAreaView>
  );
}

// ─── Styles ───────────────────────────────────────────────────────────────────
const styles = StyleSheet.create({
  safe: {
    flex: 1,
    backgroundColor: Colors.white,
    paddingTop: Platform.OS === 'android' ? StatusBar.currentHeight : 0,
  },

  // Header
  header: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    backgroundColor: Colors.white,
    borderBottomWidth: 1,
    borderBottomColor: Colors.border,
    paddingHorizontal: Spacing.md,
    paddingVertical: 12,
  },
  logoRow: { flexDirection: 'row', alignItems: 'center', gap: 10 },
  logoBox: {
    width: 32, height: 32, borderRadius: 8,
    backgroundColor: Colors.blue,
    alignItems: 'center', justifyContent: 'center',
  },
  logoIcon: { fontSize: 18, color: Colors.white },
  logoText: { fontSize: 16, fontWeight: '700', color: Colors.heading, letterSpacing: -0.3 },
  logoSub:  { fontSize: 10, color: Colors.muted, fontWeight: '500' },
  statusPill: {
    backgroundColor: '#DCFCE7', borderRadius: Radius.full,
    paddingHorizontal: 10, paddingVertical: 3,
    borderWidth: 1, borderColor: Colors.greenBorder,
  },
  statusText: { fontSize: 10, fontWeight: '700', color: Colors.green, letterSpacing: 0.5 },

  // Page title
  pageTitleBar: {
    backgroundColor: Colors.white,
    borderBottomWidth: 1, borderBottomColor: Colors.borderLight,
    paddingHorizontal: Spacing.md, paddingVertical: 10,
  },

  // Tab bar
  tabBar: {
    flexDirection: 'row',
    backgroundColor: Colors.white,
    borderTopWidth: 1, borderTopColor: Colors.border,
    paddingBottom: Platform.OS === 'ios' ? 16 : 8,
    paddingTop: 8,
  },
  tabItem: {
    flex: 1, alignItems: 'center', justifyContent: 'center', gap: 3,
  },
  tabIconWrap: {
    width: 40, height: 32, borderRadius: Radius.md,
    alignItems: 'center', justifyContent: 'center',
  },
  tabIconActive: {
    backgroundColor: Colors.blueLight,
  },
  tabIcon: { fontSize: 18 },
  tabLabel: {
    fontSize: 10, fontWeight: '500', color: Colors.muted,
  },
  tabLabelActive: {
    color: Colors.blue, fontWeight: '700',
  },
});
