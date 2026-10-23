import React, { useState, useEffect, useCallback } from 'react';
import {
  View, Text, ScrollView, RefreshControl, StyleSheet,
} from 'react-native';
import { api, PostmortemRecord } from '../api';
import {
  Card, SectionHeader, Badge, EmptyState, ErrorBanner,
} from '../components/ui';
import { Colors, Spacing, Typography } from '../theme';

const SEVERITY_VARIANT: Record<string, 'red' | 'amber' | 'green' | 'gray'> = {
  HIGH:     'red',
  CRITICAL: 'red',
  MEDIUM:   'amber',
  LOW:      'green',
};

export const IncidentsScreen: React.FC = () => {
  const [records, setRecords] = useState<PostmortemRecord[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchRecords = useCallback(async () => {
    try {
      const data = await api.getPostmortems();
      setRecords(data);
      setError(null);
    } catch (e: any) {
      setError(e.message ?? 'Failed to load incident history');
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
      <Text style={Typography.bodySmall}>Loading incident history…</Text>
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
        title="Incident History"
        sub={`${records.length} postmortem records`}
      />

      {records.length === 0 ? (
        <EmptyState
          icon="✅"
          title="No incidents on record"
          sub="Run an investigation to generate your first postmortem"
        />
      ) : (
        records.map((pm, i) => (
          <Card key={i}>
            <View style={styles.row}>
              <View style={{ flex: 1 }}>
                <Text style={[Typography.body, { fontWeight: '600', marginBottom: 2 }]}>
                  {pm.title ?? pm.incident_id ?? `Incident #${i + 1}`}
                </Text>
                <Text style={Typography.bodySmall}>
                  {pm.affected_services?.join(', ') ?? '—'}
                </Text>
              </View>
              <View style={{ alignItems: 'flex-end', gap: 4 }}>
                {pm.severity && (
                  <Badge
                    label={pm.severity}
                    variant={SEVERITY_VARIANT[pm.severity] ?? 'gray'}
                  />
                )}
                <Badge label="Resolved" variant="green" />
              </View>
            </View>
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
  row: { flexDirection: 'row', alignItems: 'flex-start', gap: 8 },
});
