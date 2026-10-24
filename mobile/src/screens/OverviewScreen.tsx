import React, { useState, useEffect, useCallback, useRef } from 'react';
import {
  View, Text, ScrollView, RefreshControl,
  StyleSheet, TouchableOpacity, Animated, TextInput, Platform,
} from 'react-native';
import { api, LiveStatus, getApiBase, setApiBase } from '../api';
import {
  StatusDot, Badge, Card, MetricCard, SectionHeader,
  PrimaryButton, EmptyState, ErrorBanner, Divider,
} from '../components/ui';
import { Colors, Spacing, Typography, Radius } from '../theme';

function formatUptime(s?: number): string {
  if (!s) return '—';
  if (s < 60) return `${Math.floor(s)}s`;
  if (s < 3600) return `${Math.floor(s / 60)}m ${Math.floor(s % 60)}s`;
  return `${Math.floor(s / 3600)}h ${Math.floor((s % 3600) / 60)}m`;
}

function timeAgo(iso?: string): string {
  if (!iso) return '—';
  const diff = Date.now() - new Date(iso).getTime();
  const s = Math.floor(diff / 1000);
  if (s < 10) return 'just now';
  if (s < 60) return `${s}s ago`;
  if (s < 3600) return `${Math.floor(s / 60)}m ago`;
  return `${Math.floor(s / 3600)}h ago`;
}

export const OverviewScreen: React.FC = () => {
  const [status, setStatus] = useState<LiveStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [processLoading, setProcessLoading] = useState(false);
  const [currentUrl, setCurrentUrl] = useState(getApiBase());
  const [inputUrl, setInputUrl] = useState(getApiBase());
  const [showConfig, setShowConfig] = useState(false);
  const pingAnim = useRef(new Animated.Value(1)).current;

  const fetchStatus = useCallback(async () => {
    try {
      const s = await api.getStatus();
      setStatus(s);
      setError(null);
    } catch (e: any) {
      setError(e.message ?? 'Failed to connect to backend');
    }
  }, []);

  useEffect(() => {
    fetchStatus().finally(() => setLoading(false));
    const iv = setInterval(fetchStatus, 5000);
    return () => clearInterval(iv);
  }, [fetchStatus]);

  // Pulse animation for healthy dot
  useEffect(() => {
    if (status?.health?.healthy) {
      Animated.loop(
        Animated.sequence([
          Animated.timing(pingAnim, { toValue: 1.6, duration: 900, useNativeDriver: true }),
          Animated.timing(pingAnim, { toValue: 1, duration: 900, useNativeDriver: true }),
        ]),
      ).start();
    }
  }, [status?.health?.healthy]);

  const onRefresh = async () => {
    setRefreshing(true);
    await fetchStatus();
    setRefreshing(false);
  };

  const handleAction = async (action: () => Promise<void>) => {
    setProcessLoading(true);
    try { await action(); await fetchStatus(); }
    catch (e: any) { setError(e.message); }
    finally { setProcessLoading(false); }
  };

  const running = status?.process?.running ?? false;
  const healthy = status?.health?.healthy ?? false;
  const overall = running && healthy;

  return (
    <ScrollView
      style={styles.container}
      contentContainerStyle={styles.content}
      refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} />}
    >
      {/* Backend Endpoint Control Bar */}
      <View style={styles.serverBar}>
        <View style={{ flex: 1, flexDirection: 'row', alignItems: 'center' }}>
          <Text style={styles.serverBarLabel}>API Host:</Text>
          <Text style={styles.serverBarUrl} numberOfLines={1}>{currentUrl}</Text>
        </View>
        <TouchableOpacity
          onPress={() => {
            setInputUrl(currentUrl);
            setShowConfig(!showConfig);
          }}
          style={styles.serverBarBtnWrap}
        >
          <Text style={styles.serverBarBtnText}>{showConfig ? 'Close' : 'Change'}</Text>
        </TouchableOpacity>
      </View>

      {/* Endpoint Configuration Drawer */}
      {showConfig && (
        <View style={styles.configBox}>
          <Text style={[Typography.bodySmall, { color: Colors.secondary, marginBottom: 6 }]}>
            Change Backend URL (LAN IP or Tunnel):
          </Text>
          <TextInput
            style={styles.urlInput}
            value={inputUrl}
            onChangeText={setInputUrl}
            placeholder="http://192.168.2.19:8000"
            autoCapitalize="none"
            autoCorrect={false}
          />
          <View style={{ flexDirection: 'row', justifyContent: 'flex-end', marginTop: 8 }}>
            <TouchableOpacity
              style={styles.saveBtn}
              onPress={() => {
                setApiBase(inputUrl);
                setCurrentUrl(getApiBase());
                setShowConfig(false);
                fetchStatus();
              }}
            >
              <Text style={styles.saveBtnText}>Connect & Re-sync</Text>
            </TouchableOpacity>
          </View>
        </View>
      )}

      {error && (
        <View style={{ marginBottom: Spacing.sm }}>
          <ErrorBanner message={error} onDismiss={() => setError(null)} />
          <Text style={styles.troubleshootHint}>
            💡 Tip: Ensure phone is on the same Wi-Fi. In Windows Settings, set your Wi-Fi profile to "Private Network" so Windows Firewall doesn't block port 8000.
          </Text>
        </View>
      )}

      {/* Health Banner */}
      <View style={[
        styles.healthBanner,
        { backgroundColor: overall ? Colors.greenLight : running ? Colors.amberLight : Colors.redLight },
        { borderColor: overall ? Colors.greenBorder : running ? Colors.amberBorder : Colors.redBorder },
      ]}>
        <View style={styles.healthLeft}>
          <View style={{ position: 'relative', marginRight: 10 }}>
            {overall && (
              <Animated.View style={[
                styles.pingRing,
                { transform: [{ scale: pingAnim }], backgroundColor: Colors.green },
              ]} />
            )}
            <StatusDot ok={overall} size={10} />
          </View>
          <View style={{ flex: 1 }}>
            <Text style={[Typography.body, { fontWeight: '600', color: Colors.heading }]}>
              {overall ? 'Live-lab is healthy'
                : running ? 'Process running — health check failing'
                : 'Live-lab process is offline'}
            </Text>
            <Text style={[Typography.bodySmall, { marginTop: 2 }]}>
              {status
                ? `Uptime ${formatUptime(status.process?.uptime_seconds)} · HTTP ${status.health?.status_code ?? '—'} · Updated ${timeAgo(status.timestamp)}`
                : loading ? 'Loading…' : 'Cannot reach backend'}
            </Text>
          </View>
        </View>
      </View>

      {/* Metric Grid */}
      <View style={styles.metricRow}>
        <MetricCard
          label="Process"
          value={running ? 'Running' : 'Stopped'}
          sub={`PID ${status?.process?.pid ?? '—'}`}
          accent={running ? 'green' : 'red'}
        />
        <View style={{ width: Spacing.sm }} />
        <MetricCard
          label="Uptime"
          value={formatUptime(status?.process?.uptime_seconds)}
          sub="Since last start"
          accent="blue"
        />
      </View>
      <View style={styles.metricRow}>
        <MetricCard
          label="Health"
          value={healthy ? '✓ OK' : '✗ Fail'}
          sub={`HTTP ${status?.health?.status_code ?? '—'} · ${status?.health?.latency_ms ?? '—'}ms`}
          accent={healthy ? 'green' : 'red'}
        />
        <View style={{ width: Spacing.sm }} />
        <MetricCard
          label="AI Agents"
          value="4"
          sub="Active agent roles"
          accent="blue"
        />
      </View>

      {/* Process Controls */}
      <SectionHeader title="Process Control" sub="Manage the live-lab Flask service" />
      <Card>
        <View style={styles.processInfo}>
          <Text style={[Typography.body, { fontWeight: '600' }]}>live-lab-checkout</Text>
          <Text style={Typography.bodySmall}>Port 5001 · Flask · PID {status?.process?.pid ?? '—'}</Text>
        </View>
        <Divider />
        <View style={styles.processButtons}>
          {!running ? (
            <PrimaryButton
              label="Start Process"
              variant="primary"
              onPress={() => handleAction(() => api.startProcess())}
              loading={processLoading}
            />
          ) : (
            <>
              <PrimaryButton
                label="Restart"
                variant="ghost"
                onPress={() => handleAction(() => api.restartProcess())}
                loading={processLoading}
              />
              <View style={{ width: 8 }} />
              <PrimaryButton
                label="Stop"
                variant="danger"
                onPress={() => handleAction(() => api.stopProcess())}
                loading={processLoading}
              />
            </>
          )}
        </View>
      </Card>
    </ScrollView>
  );
};

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: Colors.surface },
  content: { padding: Spacing.md, paddingBottom: Spacing.xl },
  healthBanner: {
    borderRadius: Radius.lg, borderWidth: 1,
    padding: Spacing.md, marginBottom: Spacing.md,
  },
  healthLeft: { flexDirection: 'row', alignItems: 'flex-start' },
  pingRing: {
    position: 'absolute', width: 10, height: 10,
    borderRadius: 5, opacity: 0.35, top: 0, left: 0,
  },
  metricRow: {
    flexDirection: 'row', marginBottom: 0,
  },
  processInfo: { marginBottom: Spacing.sm },
  processButtons: { flexDirection: 'row', marginTop: Spacing.sm },
  serverBar: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    backgroundColor: Colors.white,
    paddingHorizontal: Spacing.sm,
    paddingVertical: 6,
    borderRadius: Radius.md,
    borderWidth: 1,
    borderColor: Colors.border,
    marginBottom: Spacing.sm,
  },
  serverBarLabel: {
    fontSize: 11,
    fontWeight: '700',
    color: Colors.secondary,
    marginRight: 4,
  },
  serverBarUrl: {
    fontSize: 11,
    fontFamily: Platform.OS === 'ios' ? 'Courier' : 'monospace',
    color: Colors.blue,
    flex: 1,
  },
  serverBarBtnWrap: {
    backgroundColor: Colors.blueLight,
    paddingHorizontal: 8,
    paddingVertical: 3,
    borderRadius: Radius.sm,
  },
  serverBarBtnText: {
    fontSize: 11,
    fontWeight: '600',
    color: Colors.blue,
  },
  configBox: {
    backgroundColor: Colors.white,
    padding: Spacing.sm,
    borderRadius: Radius.md,
    borderWidth: 1,
    borderColor: Colors.border,
    marginBottom: Spacing.sm,
  },
  urlInput: {
    backgroundColor: Colors.surface,
    borderWidth: 1,
    borderColor: Colors.border,
    borderRadius: Radius.sm,
    paddingHorizontal: Spacing.sm,
    paddingVertical: 6,
    fontSize: 13,
    fontFamily: Platform.OS === 'ios' ? 'Courier' : 'monospace',
    color: Colors.heading,
  },
  saveBtn: {
    backgroundColor: Colors.blue,
    paddingHorizontal: 12,
    paddingVertical: 6,
    borderRadius: Radius.sm,
  },
  saveBtnText: {
    color: Colors.white,
    fontSize: 12,
    fontWeight: '600',
  },
  troubleshootHint: {
    fontSize: 11,
    color: Colors.secondary,
    marginTop: 4,
    lineHeight: 16,
  },
});
