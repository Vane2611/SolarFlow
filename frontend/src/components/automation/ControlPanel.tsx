import { useState, useCallback } from 'react';
import { Fan, Power, PowerOff, Clock } from 'lucide-react';
import type { ControlMode, ControlState, ManualAction } from '../../types';
import { setControlMode, sendManualOverride } from '../../api/client';

interface ControlPanelProps {
  controlState: ControlState | null;
  loading: boolean;
  onRefresh: () => void;
}

// Allowed actions — validated client-side before sending
const ALLOWED_ACTIONS: ManualAction[] = ['fan_on', 'fan_off', 'noop'];

const DURATION_OPTIONS = [
  { label: '5 minutes', value: 300 },
  { label: '10 minutes', value: 600 },
  { label: '15 minutes', value: 900 },
  { label: '30 minutes', value: 1800 },
  { label: '1 hour', value: 3600 },
];

export function ControlPanel({ controlState, loading, onRefresh }: ControlPanelProps) {
  const [modeChanging, setModeChanging] = useState(false);
  const [overrideDuration, setOverrideDuration] = useState(300);
  const [actionError, setActionError] = useState<string | null>(null);
  const [actionLoading, setActionLoading] = useState(false);

  const handleModeChange = useCallback(
    async (mode: ControlMode) => {
      setModeChanging(true);
      setActionError(null);
      try {
        await setControlMode({ mode });
        onRefresh();
      } catch (err) {
        setActionError(err instanceof Error ? err.message : 'Failed to set mode');
      } finally {
        setModeChanging(false);
      }
    },
    [onRefresh],
  );

  const handleOverride = useCallback(
    async (action: ManualAction) => {
      // Client-side validation: only allow known actions
      if (!ALLOWED_ACTIONS.includes(action)) {
        setActionError(`Invalid action: "${action}". Allowed: ${ALLOWED_ACTIONS.join(', ')}`);
        return;
      }
      setActionLoading(true);
      setActionError(null);
      try {
        await sendManualOverride({ action, duration_seconds: overrideDuration });
        onRefresh();
      } catch (err) {
        setActionError(err instanceof Error ? err.message : 'Failed to send override');
      } finally {
        setActionLoading(false);
      }
    },
    [overrideDuration, onRefresh],
  );

  const overrideExpiresAt = controlState?.manual_override_expires_at
    ? new Date(controlState.manual_override_expires_at)
    : null;

  const overrideSecondsLeft =
    overrideExpiresAt !== null
      ? Math.max(0, Math.round((overrideExpiresAt.getTime() - Date.now()) / 1000))
      : null;

  if (loading && !controlState) {
    return (
      <div className="card">
        <div className="loading-state">Loading control state…</div>
      </div>
    );
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
      {/* Mode selector */}
      <div className="card">
        <div className="card-title">Control Mode</div>
        <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap' }}>
          {(['reactive', 'predictive', 'manual'] as ControlMode[]).map((m) => {
            const isActive = controlState?.mode === m;
            return (
              <label
                key={m}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: 8,
                  padding: '10px 16px',
                  borderRadius: 8,
                  border: `2px solid ${isActive ? 'var(--color-sidebar-bg)' : 'var(--color-border)'}`,
                  background: isActive ? '#e7f5ee' : 'var(--color-surface)',
                  cursor: modeChanging ? 'not-allowed' : 'pointer',
                  fontWeight: isActive ? 600 : 400,
                  fontSize: 14,
                  transition: 'all 0.15s',
                }}
              >
                <input
                  type="radio"
                  name="control-mode"
                  value={m}
                  checked={isActive}
                  disabled={modeChanging}
                  onChange={() => { void handleModeChange(m); }}
                  style={{ accentColor: 'var(--color-sidebar-bg)' }}
                />
                {m.charAt(0).toUpperCase() + m.slice(1)}
              </label>
            );
          })}
        </div>
        <div style={{ fontSize: 12, color: 'var(--color-text-muted)', marginTop: 8 }}>
          {controlState?.mode === 'reactive' &&
            'Fan activates when measured temperature exceeds the configured threshold.'}
          {controlState?.mode === 'predictive' &&
            'Fan activates before temperature exceeds threshold, based on 10–30 min forecasts.'}
          {controlState?.mode === 'manual' &&
            'Fan is controlled exclusively by manual override commands below.'}
        </div>
      </div>

      {/* Fan status */}
      <div className="card">
        <div className="card-title">Fan Status</div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 16 }}>
          <div
            style={{
              width: 56,
              height: 56,
              borderRadius: '50%',
              background:
                controlState?.fan_state === 'on'
                  ? 'var(--color-success)'
                  : 'var(--color-text-muted)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
            }}
          >
            <Fan size={28} color="#fff" />
          </div>
          <div>
            <div style={{ fontWeight: 700, fontSize: 18 }}>
              Fan is {controlState?.fan_state?.toUpperCase() ?? '—'}
            </div>
            {controlState?.last_action_reason && (
              <div style={{ fontSize: 13, color: 'var(--color-text-secondary)', marginTop: 4 }}>
                <strong>Reason:</strong> {controlState.last_action_reason}
              </div>
            )}
          </div>
        </div>

        {controlState?.manual_override_active && overrideSecondsLeft !== null && (
          <div
            style={{
              marginTop: 12,
              padding: '8px 12px',
              background: 'var(--color-warning-light)',
              borderRadius: 6,
              fontSize: 12,
              display: 'flex',
              alignItems: 'center',
              gap: 6,
            }}
          >
            <Clock size={14} color="var(--color-warning)" />
            <span>
              Manual override active — expires in {Math.floor(overrideSecondsLeft / 60)}m{' '}
              {overrideSecondsLeft % 60}s
            </span>
          </div>
        )}
      </div>

      {/* Manual override */}
      <div className="card">
        <div className="card-title">Manual Override</div>
        <div style={{ marginBottom: 12 }}>
          <label style={{ fontSize: 13, color: 'var(--color-text-secondary)', display: 'block', marginBottom: 6 }}>
            Duration
          </label>
          <select
            value={overrideDuration}
            onChange={(e) => setOverrideDuration(Number(e.target.value))}
            style={{
              padding: '6px 10px',
              borderRadius: 6,
              border: '1px solid var(--color-border)',
              fontSize: 13,
              background: 'var(--color-surface)',
            }}
          >
            {DURATION_OPTIONS.map((o) => (
              <option key={o.value} value={o.value}>
                {o.label}
              </option>
            ))}
          </select>
        </div>

        <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap' }}>
          <button
            onClick={() => { void handleOverride('fan_on'); }}
            disabled={actionLoading}
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: 8,
              padding: '10px 20px',
              background: 'var(--color-success)',
              color: '#fff',
              borderRadius: 8,
              fontWeight: 600,
              fontSize: 14,
              opacity: actionLoading ? 0.6 : 1,
              cursor: actionLoading ? 'not-allowed' : 'pointer',
            }}
          >
            <Power size={16} />
            Fan On
          </button>
          <button
            onClick={() => { void handleOverride('fan_off'); }}
            disabled={actionLoading}
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: 8,
              padding: '10px 20px',
              background: 'var(--color-danger)',
              color: '#fff',
              borderRadius: 8,
              fontWeight: 600,
              fontSize: 14,
              opacity: actionLoading ? 0.6 : 1,
              cursor: actionLoading ? 'not-allowed' : 'pointer',
            }}
          >
            <PowerOff size={16} />
            Fan Off
          </button>
        </div>

        {actionError && (
          <div className="error-state" style={{ marginTop: 12 }}>
            {actionError}
          </div>
        )}
      </div>
    </div>
  );
}
