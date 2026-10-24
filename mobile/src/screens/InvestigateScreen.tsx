import React, { useState } from 'react';
import {
  View, Text, ScrollView, StyleSheet, Modal,
  TextInput, Alert, ActivityIndicator,
} from 'react-native';
import { api, InvestigationResult, getApiBase } from '../api';
import {
  Card, SectionHeader, PrimaryButton, ErrorBanner,
  Badge, EmptyState, Divider,
} from '../components/ui';
import { Colors, Spacing, Typography, Radius } from '../theme';

// Map agent status to badge variant
function statusVariant(status: string): 'green' | 'red' | 'amber' | 'blue' | 'gray' {
  const s = (status ?? '').toUpperCase();
  if (s === 'COMPLETED' || s === 'VERIFIED') return 'green';
  if (s === 'VETOED' || s === 'FAILED') return 'red';
  if (s === 'AWAITING_APPROVAL') return 'amber';
  return 'blue';
}

// Map hypothesis score to confidence badge
function scoreVariant(score: number): 'red' | 'amber' | 'gray' {
  if (score >= 0.7) return 'red';
  if (score >= 0.4) return 'amber';
  return 'gray';
}

function scoreLabel(score: number): string {
  if (!isFinite(score) || isNaN(score)) return 'Unknown';
  if (score >= 0.7) return 'High';
  if (score >= 0.4) return 'Med';
  return 'Low';
}

export const InvestigateScreen: React.FC = () => {
  const [investigation, setInvestigation] = useState<InvestigationResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [approvalVisible, setApprovalVisible] = useState(false);
  const [approvalEmail, setApprovalEmail] = useState('lead_sre@company.com');
  const [approvalPassword, setApprovalPassword] = useState('');
  const [approvalLoading, setApprovalLoading] = useState(false);
  const [approvalError, setApprovalError] = useState<string | null>(null);

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
    if (!approvalPassword.trim()) {
      setApprovalError('Enter your password to approve');
      return;
    }
    setApprovalLoading(true);
    setApprovalError(null);
    try {
      // Step 1: authenticate to get a real session token
      const base = getApiBase();
      const sessionRes = await fetch(`${base}/api/auth/session`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email: approvalEmail.trim(), password: approvalPassword.trim() }),
      });
      if (!sessionRes.ok) {
        const body = await sessionRes.json().catch(() => ({}));
        throw new Error(body?.detail ?? 'Authentication failed. Check your email/password.');
      }
      const { session_token } = await sessionRes.json();

      // Step 2: approve with the verified session token
      await api.approvePatch({
        run_id: investigation.run_id,
        patch_hash: investigation.proposed_patch.patch_hash,
        auth_token: session_token,
        comment: 'Mobile operator approval',
      });

      setApprovalVisible(false);
      setApprovalPassword('');
      setApprovalError(null);
      Alert.alert('✅ Patch Approved', 'The patch has been applied and recovery verification is running.');
      setInvestigation(null);
    } catch (e: any) {
      setApprovalError(e.message ?? 'Approval failed');
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
                <Card key={h.id ?? i}>
                  <View style={styles.hypothesisRow}>
                    <View style={{ flex: 1 }}>
                      <Text style={[Typography.body, { fontWeight: '600', marginBottom: 2 }]}>{h.title}</Text>
                      <Text style={Typography.bodySmall} numberOfLines={3}>{h.description}</Text>
                      <Text style={[Typography.bodySmall, { marginTop: 4, color: Colors.muted }]}>
                        Score: {isFinite(h.score) ? (h.score * 100).toFixed(0) : '—'}% · {h.status}
                      </Text>
                    </View>
                    <Badge
                      label={scoreLabel(h.score)}
                      variant={scoreVariant(h.score)}
                    />
                  </View>
                </Card>
              ))}
            </>
          )}

          {/* Agent Traces */}
          {investigation.agent_traces.length > 0 && (
            <>
              <SectionHeader title="Agent Traces" sub={`${investigation.agent_traces.length} agents`} />
              {investigation.agent_traces.map((t, i) => (
                <Card key={t.agent_id ?? i}>
                  <View style={styles.traceHeader}>
                    <Badge label={t.role_name} variant={statusVariant(t.status)} />
                    <Badge label={t.status} variant={statusVariant(t.status)} size="sm" />
                  </View>
                  <Divider />
                  <Text style={[Typography.bodySmall, { marginTop: 6 }]} numberOfLines={5}>
                    {t.summary}
                  </Text>
                  {t.tool_calls && t.tool_calls.length > 0 && (
                    <Text style={[Typography.label, { marginTop: 6, color: Colors.muted }]}>
                      Tools: {t.tool_calls.join(' · ')}
                    </Text>
                  )}
                  <Text style={[Typography.label, { marginTop: 4, color: Colors.muted }]}>
                    {t.execution_time_ms}ms
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
                <Text style={[Typography.bodySmall, { marginTop: 8, marginBottom: 12, color: Colors.secondary }]}>
                  Tap "Approve Patch" to authenticate and authorise this code change. An immutable audit record will be created.
                </Text>
                <View style={styles.patchActions}>
                  <PrimaryButton
                    label="Approve Patch"
                    variant="primary"
                    onPress={() => {
                      setApprovalError(null);
                      setApprovalPassword('');
                      setApprovalVisible(true);
                    }}
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
            <Text style={[Typography.heading2, { marginBottom: 4 }]}>Approve Patch</Text>
            <Text style={[Typography.bodySmall, { marginBottom: Spacing.md }]}>
              Enter your operator credentials to authorise this code change. A session token will be issued and an immutable audit record created.
            </Text>

            {/* Email row */}
            <Text style={[Typography.label, { marginBottom: 4 }]}>Operator Email</Text>
            <TextInput
              style={styles.tokenInput}
              placeholder="lead_sre@company.com"
              value={approvalEmail}
              onChangeText={setApprovalEmail}
              autoCapitalize="none"
              autoCorrect={false}
              keyboardType="email-address"
              placeholderTextColor={Colors.muted}
            />

            {/* Password row */}
            <Text style={[Typography.label, { marginBottom: 4, marginTop: 8 }]}>Password</Text>
            <TextInput
              style={styles.tokenInput}
              placeholder="Enter password (e.g. 123456)"
              value={approvalPassword}
              onChangeText={(v) => { setApprovalPassword(v); setApprovalError(null); }}
              secureTextEntry
              autoCapitalize="none"
              autoCorrect={false}
              placeholderTextColor={Colors.muted}
            />

            {approvalError && (
              <View style={styles.approvalErrorBox}>
                <Text style={styles.approvalErrorText}>⚠ {approvalError}</Text>
              </View>
            )}

            {approvalLoading && (
              <View style={styles.loadingRow}>
                <ActivityIndicator size="small" color={Colors.blue} />
                <Text style={[Typography.bodySmall, { marginLeft: 8 }]}>Authenticating & applying patch…</Text>
              </View>
            )}

            <View style={styles.modalActions}>
              <PrimaryButton
                label="Cancel"
                variant="ghost"
                onPress={() => { setApprovalVisible(false); setApprovalPassword(''); setApprovalError(null); }}
                disabled={approvalLoading}
              />
              <View style={{ width: 10 }} />
              <PrimaryButton
                label="Approve"
                variant="primary"
                onPress={handleApprove}
                loading={approvalLoading}
                disabled={approvalLoading}
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
  traceHeader: { flexDirection: 'row', alignItems: 'center', gap: 8, marginBottom: 6 },
  patchCard: { borderColor: Colors.amberBorder },
  patchHeader: { marginBottom: 4 },
  diffBox: {
    backgroundColor: Colors.dark, borderRadius: Radius.md,
    padding: Spacing.md, marginVertical: 8, overflow: 'hidden',
  },
  patchActions: { flexDirection: 'row', marginTop: 4 },
  modalOverlay: {
    flex: 1, backgroundColor: 'rgba(0,0,0,0.5)',
    justifyContent: 'flex-end',
  },
  modalCard: {
    backgroundColor: Colors.white, borderTopLeftRadius: 20, borderTopRightRadius: 20,
    padding: Spacing.lg, paddingBottom: 40,
  },
  tokenInput: {
    borderWidth: 1, borderColor: Colors.border, borderRadius: Radius.md,
    padding: 12, fontSize: 14, color: Colors.heading,
    backgroundColor: Colors.surface,
  },
  modalActions: { flexDirection: 'row', marginTop: 16 },
  approvalErrorBox: {
    backgroundColor: Colors.redLight, borderColor: Colors.redBorder, borderWidth: 1,
    borderRadius: Radius.sm, padding: 10, marginTop: 10,
  },
  approvalErrorText: { fontSize: 13, color: Colors.red },
  loadingRow: { flexDirection: 'row', alignItems: 'center', marginTop: 10 },
});
