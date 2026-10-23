import React, { useState, useEffect, useCallback } from 'react';
import {
  View, Text, ScrollView, RefreshControl,
  StyleSheet,
} from 'react-native';
import { api, AuditRecord } from '../api';
import {
  Card, SectionHeader, Badge, EmptyState, ErrorBanner, Divider,
} from '../components/ui';
import { Colors, Spacing, Typography, Radius } from '../theme';

function timeAgo(iso?: string): string {
  if (!iso) return '—';
  const diff = Date.now() - new Date(iso).getTime();
  const s = Math.floor(diff / 1000);
  if (s < 10) return 'just now';
  if (s < 60) return `${s}s ago`;
  if (s < 3600) return `${Math.floor(s / 60)}m ago`;
  return `${Math.floor(s / 3600)}h ago`;
}

export const AuditScreen: React.FC = () => {
  const [records, setRecords] = useState<AuditRecord[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchRecords = useCallback(async () => {
    try {
      const data = await api.getAuditRecords();
      setRecords(data);
      setError(null);
    } catch (e: any) {
      setError(e.message ?? 'Failed to load audit records');
    }
  }, []);

  useEffect(() => {
    fetchRecords().finally(() => setLoading(false));
  }, [fetchRecords]);

  const onRefresh = async () => {
    setRefreshing(true);
    await fetchRecords();
    setRefreshing(false);
  };

  if (loading) return (
    <View style={styles.center}>
      <Text style={Typography.bodySmall}>Loading audit records…</Text>
    </View>
  );

  return (
    <ScrollView
      style={styles.container}
      contentContainerStyle={styles.content}
      refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} />}
    >
      {error && <ErrorBanner message={error} onDismiss={() => setError(null)} />}

      <SectionHeader
        title="Operator Audit Log"
        sub={`${records.length} records · Pull to refresh`}
      />

      {records.length === 0 ? (
        <EmptyState
          icon="🔒"
          title="No audit records yet"
          sub="Patch approvals and rejections will appear here after running an investigation"
        />
      ) : (
        records.map((rec, i) => (
          <Card key={i}>
            <View style={styles.recordHeader}>
              <View style={{ flex: 1 }}>
                <Text style={[Typography.body, { fontWeight: '600', marginBottom: 2 }]}>
                  {rec.action ?? rec.event_type ?? 'Patch review'}
                </Text>
                <Text style={Typography.bodySmall}>
                  {rec.approver ?? rec.operator ?? '—'} · {timeAgo(rec.timestamp)}
                </Text>
              </View>
              <Badge
                label={rec.approved ? 'Approved' : 'Rejected'}
                variant={rec.approved ? 'green' : 'red'}
              />
            </View>
            {rec.comment && (
              <>
                <Divider />
                <Text style={[Typography.bodySmall, { fontStyle: 'italic', marginTop: 4 }]}>
                  "{rec.comment}"
                </Text>
              </>
            )}
          </Card>
        ))
      )}
    </ScrollView>
  );
};

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: Colors.surface },
  content: { padding: Spacing.md, paddingBottom: 40 },
  center: { flex: 1, alignItems: 'center', justifyContent: 'center', padding: 40 },
  recordHeader: { flexDirection: 'row', alignItems: 'flex-start', gap: 8 },
});
