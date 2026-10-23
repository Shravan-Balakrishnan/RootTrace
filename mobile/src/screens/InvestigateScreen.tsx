import React, { useState } from 'react';
import {
  View, Text, ScrollView, StyleSheet, Modal,
  TextInput, Alert,
} from 'react-native';
import { api, InvestigationResult } from '../api';
import {
  Card, SectionHeader, PrimaryButton, ErrorBanner,
  Badge, EmptyState, Divider,
} from '../components/ui';
import { Colors, Spacing, Typography, Radius } from '../theme';

export const InvestigateScreen: React.FC = () => {
  const [investigation, setInvestigation] = useState<InvestigationResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [approvalVisible, setApprovalVisible] = useState(false);
  const [authToken, setAuthToken] = useState('');
  const [approvalLoading, setApprovalLoading] = useState(false);

  const handleInvestigate = async () => {
    setLoading(true);
    setError(null);
    setInvestigation(null);
    try {
      const result = await api.investigate();
      setInvestigation(result);
    } catch (e: any) {
      setError(e.message ?? 'Investigation failed');
    } finally {
      setLoading(false);
    }
  };

  const handleApprove = async () => {
    if (!investigation?.proposed_patch) return;
    if (!authToken.trim()) {
      Alert.alert('Auth required', 'Enter your session token to approve');
      return;
    }
    setApprovalLoading(true);
    try {
      await api.approvePatch({
        run_id: investigation.run_id,
        patch_hash: investigation.proposed_patch.patch_hash,
        auth_token: authToken.trim(),
        comment: 'Mobile operator approval',
      });
      setApprovalVisible(false);
      setAuthToken('');
      Alert.alert('✅ Patch Approved', 'The patch has been applied and recovery verification is running.');
      setInvestigation(null);
    } catch (e: any) {
      Alert.alert('Approval failed', e.message ?? 'Unknown error');
    } finally {
      setApprovalLoading(false);
    }
  };

  const handleReject = async () => {
    if (!investigation) return;
    try {
      await api.rejectPatch(investigation.run_id, 'Rejected via mobile review');
      Alert.alert('Rejected', 'The patch proposal has been rejected.');
      setInvestigation(null);
    } catch (e: any) {
      Alert.alert('Error', e.message);
    }
  };

  return (
    <ScrollView style={styles.container} contentContainerStyle={styles.content}>
      {error && <ErrorBanner message={error} onDismiss={() => setError(null)} />}

      {/* Run Investigation */}
      <Card>
        <Text style={[Typography.heading3, { marginBottom: 4 }]}>AI Investigation</Text>
        <Text style={[Typography.bodySmall, { marginBottom: Spacing.md }]}>
          Launch the 4-agent pipeline to collect evidence, generate hypotheses, and propose a code repair.
        </Text>
        <PrimaryButton
          label={loading ? 'Investigating…' : 'Run Investigation'}
          onPress={handleInvestigate}
          loading={loading}
          disabled={loading}
        />
      </Card>

      {/* Results */}
      {investigation && (
        <>
          {/* Diagnosis */}
          <SectionHeader title="Diagnosis" />
          <Card>
            {investigation.abstained ? (
              <View>
                <Badge label="Abstained" variant="amber" />
                <Text style={[Typography.body, { marginTop: 8, color: Colors.amber }]}>
                  {investigation.abstention_reason ?? 'Insufficient evidence to diagnose root cause.'}
                </Text>
              </View>
            ) : (
              <Text style={Typography.body}>{investigation.diagnosis ?? 'No diagnosis available.'}</Text>
            )}
          </Card>

          {/* Hypotheses */}
          {investigation.hypotheses.length > 0 && (
            <>
              <SectionHeader title="Hypotheses" sub={`${investigation.hypotheses.length} competing hypotheses`} />
              {investigation.hypotheses.map((h, i) => (
                <Card key={i}>
                  <View style={styles.hypothesisRow}>
                    <View style={{ flex: 1 }}>
                      <Text style={[Typography.body, { marginBottom: 4 }]}>{h.text}</Text>
                      <Text style={Typography.bodySmall}>Confidence: {Math.round(h.confidence * 100)}%</Text>
                    </View>
                    <Badge
                      label={h.confidence > 0.7 ? 'High' : h.confidence > 0.4 ? 'Med' : 'Low'}
                      variant={h.confidence > 0.7 ? 'red' : h.confidence > 0.4 ? 'amber' : 'gray'}
                    />
                  </View>
                </Card>
              ))}
            </>
          )}

          {/* Agent Traces */}
          {investigation.agent_traces.length > 0 && (
            <>
              <SectionHeader title="Agent Traces" sub={`${investigation.agent_traces.length} steps`} />
              {investigation.agent_traces.map((t, i) => (
                <Card key={i}>
                  <View style={styles.traceHeader}>
                    <Badge label={t.agent} variant="blue" />
                    <Text style={[Typography.bodySmall, { marginLeft: 8, flex: 1 }]}>{t.step}</Text>
                  </View>
                  <Divider />
                  <Text style={[Typography.bodySmall, { marginTop: 4 }]} numberOfLines={4}>
                    {t.output}
                  </Text>
                </Card>
              ))}
            </>
          )}

          {/* Patch Proposal */}
          {investigation.proposed_patch && (
            <>
              <SectionHeader title="Proposed Patch" />
              <Card style={styles.patchCard}>
                <View style={styles.patchHeader}>
                  <Badge label="Awaiting Approval" variant="amber" size="md" />
                </View>
                <Text style={[Typography.body, { fontWeight: '600', marginVertical: 8 }]}>
                  {investigation.proposed_patch.summary}
                </Text>
                <View style={styles.diffBox}>
                  <Text style={Typography.mono} numberOfLines={20}>
                    {investigation.proposed_patch.diff}
                  </Text>
                </View>
                <View style={styles.patchActions}>
                  <PrimaryButton
                    label="Approve Patch"
                    variant="primary"
                    onPress={() => setApprovalVisible(true)}
                  />
                  <View style={{ width: 10 }} />
                  <PrimaryButton
                    label="Reject"
                    variant="danger"
                    onPress={handleReject}
                  />
                </View>
              </Card>
            </>
          )}
        </>
      )}

      {!investigation && !loading && (
        <EmptyState
          icon="🔍"
          title="No investigation active"
          sub="Tap 'Run Investigation' to start the 4-agent analysis pipeline"
        />
      )}

      {/* Approval Modal */}
      <Modal
        visible={approvalVisible}
        transparent
        animationType="slide"
        onRequestClose={() => setApprovalVisible(false)}
      >
        <View style={styles.modalOverlay}>
          <View style={styles.modalCard}>
            <Text style={[Typography.heading2, { marginBottom: 8 }]}>Approve Patch</Text>
            <Text style={[Typography.bodySmall, { marginBottom: Spacing.md }]}>
              Enter your session token to authorize this code change. This action creates an immutable audit record.
            </Text>
            <TextInput
              style={styles.tokenInput}
              placeholder="Session token"
              value={authToken}
              onChangeText={setAuthToken}
              secureTextEntry
              autoCapitalize="none"
              autoCorrect={false}
              placeholderTextColor={Colors.muted}
            />
            <View style={styles.modalActions}>
              <PrimaryButton
                label="Cancel"
                variant="ghost"
                onPress={() => { setApprovalVisible(false); setAuthToken(''); }}
              />
              <View style={{ width: 10 }} />
              <PrimaryButton
                label="Approve"
                variant="primary"
                onPress={handleApprove}
                loading={approvalLoading}
              />
            </View>
          </View>
        </View>
      </Modal>
    </ScrollView>
  );
};

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: Colors.surface },
  content: { padding: Spacing.md, paddingBottom: 40 },
  hypothesisRow: { flexDirection: 'row', alignItems: 'flex-start', gap: 8 },
  traceHeader: { flexDirection: 'row', alignItems: 'center', marginBottom: 6 },
  patchCard: { borderColor: Colors.amberBorder },
  patchHeader: { marginBottom: 4 },
  diffBox: {
    backgroundColor: Colors.dark, borderRadius: Radius.md,
    padding: Spacing.md, marginVertical: 8, overflow: 'hidden',
  },
  patchActions: { flexDirection: 'row', marginTop: 12 },
  modalOverlay: {
    flex: 1, backgroundColor: 'rgba(0,0,0,0.5)',
    justifyContent: 'flex-end',
  },
  modalCard: {
    backgroundColor: Colors.white, borderTopLeftRadius: 20, borderTopRightRadius: 20,
    padding: Spacing.lg, paddingBottom: 36,
  },
  tokenInput: {
    borderWidth: 1, borderColor: Colors.border, borderRadius: Radius.md,
    padding: 12, fontSize: 14, color: Colors.heading, marginBottom: 16,
    backgroundColor: Colors.surface,
  },
  modalActions: { flexDirection: 'row' },
});
