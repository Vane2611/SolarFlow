import { useState, useCallback, useEffect } from 'react';
import { Fan, Power, PowerOff, Clock, Thermometer, Droplets, Zap, RefreshCw } from 'lucide-react';
import type { ControlMode, ControlState, ManualAction, SensorReading } from '../../types';
import { setControlMode, sendManualOverride } from '../../api/client';

interface ControlPanelProps {
  controlState: ControlState | null;
  loading: boolean;
  onRefresh: () => void;
  latestReading?: SensorReading | null;
}

const ALLOWED_ACTIONS: ManualAction[] = ['fan_on', 'fan_off', 'noop'];

const DURATION_OPTIONS = [
  { label: '5 minutes', value: 300 },
  { label: '10 minutes', value: 600 },
  { label: '15 minutes', value: 900 },
  { label: '30 minutes', value: 1800 },
  { label: '1 hour', value: 3600 },
];

const MODE_INFO: Record<ControlMode, { label: string; description: string; color: string }> = {
  reactive: {
    label: 'Reactive',
    description: 'Fan activates when measured temperature exceeds the configured threshold (32°C).',
    color: '#f59e0b',
  },
  predictive: {
    label: 'Predictive',
    description: 'Fan activates early based on 10–15 min forecasts, before threshold is breached.',
    color: '#3b82f6',
  },
  manual: {
    label: 'Manual',
    description: 'Fan is controlled exclusively by manual override commands below.',
    color: '#8b5cf6',
  },
};

/** Spinning keyframe injected once */
const SPIN_STYLE_ID = 'solarflow-fan-spin';
function ensureSpinStyle() {
  if (document.getElementById(SPIN_STYLE_ID)) return;
  const style = document.createElement('style');
  style.id = SPIN_STYLE_ID;
  style.textContent = `
    @keyframes fanSpin { from { transform: rotate(0deg); } to { transform: rotate(360deg); } }
    .fan-spinning { animation: fanSpin 0.6s linear infinite; }
    .fan-idle { animation: none; }
  `;
  document.head.appendChild(style);
}

export function ControlPanel({ controlState, loading, onRefresh, latestReading }: ControlPanelProps) {
  const [modeChanging, setModeChanging] = useState(false);
  const [overrideDuration, setOverrideDuration] = useState(300);
  const [actionError, setActionError] = useState<string | null>(null);
  const [actionLoading, setActionLoading] = useState(false);
  const [overrideSecondsLeft, setOverrideSecondsLeft] = useState<number | null>(null);

  useEffect(() => { ensureSpinStyle(); }, []);

  // Live countdown for override expiry
  useEffect(() => {
    const expiresAt = controlState?.manual_override_expires_at
      ? new Date(controlState.manual_override_expires_at)
      : null;

    if (!expiresAt || !controlState?.manual_override_active) {
      setOverrideSecondsLeft(null);
      return;
    }

    const tick = () => {
      const left = Math.max(0, Math.round((expiresAt.getTime() - Date.now()) / 1000));
      setOverrideSecondsLeft(left);
    };
    tick();
    const id = setInterval(tick, 1000);
    return () => clearInterval(id);
  }, [controlState?.manual_override_expires_at, controlState?.manual_override_active]);

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

  if (loading && !controlState) {
    return (
      <div className="card">
        <div className="loading-state">Loading control state…</div>
      </div>
    );
  }

  const fanOn = controlState?.fan_state === 'on';
  const currentMode = (controlState?.mode ?? 'reactive') as ControlMode;
  const modeInfo = MODE_INFO[currentMode] ?? MODE_INFO.reactive;

  const tempC = latestReading?.temperature ?? null;
  const humPct = latestReading?.humidity ?? null;

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>

      {/* ── Live sensor context bar ── */}
      {(tempC !== null || humPct !== null) && (
        <div className="card" style={{ padding: '12px 20px' }}>
          <div style={{ display: 'flex', gap: 32, alignItems: 'center', flexWrap: 'wrap' }}>
            <span style={{ fontSize: 12, fontWeight: 600, color: 'var(--color-text-muted)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
              Live Conditions
            </span>
            {tempC !== null && (
              <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                <Thermometer size={16} color={tempC >= 32 ? '#dc2626' : tempC >= 30 ? '#f59e0b' : '#16a34a'} />
                <span style={{ fontWeight: 700, fontSize: 18, color: tempC >= 32 ? '#dc2626' : tempC >= 30 ? '#f59e0b' : 'var(--color-text-primary)' }}>
                  {tempC.toFixed(1)}°C
                </span>
                {tempC >= 32 && (
                  <span style={{ fontSize: 11, padding: '2px 6px', background: '#fef2f2', color: '#dc2626', borderRadius: 4, fontWeight: 600 }}>
                    ABOVE LIMIT
                  </span>
                )}
                {tempC >= 30 && tempC < 32 && (
                  <span style={{ fontSize: 11, padding: '2px 6px', background: '#fffbeb', color: '#d97706', borderRadius: 4, fontWeight: 600 }}>
                    WARNING
                  </span>
                )}
              </div>
            )}
            {humPct !== null && (
              <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                <Droplets size={16} color={humPct > 85 ? '#dc2626' : 'var(--color-text-secondary)'} />
                <span style={{ fontWeight: 700, fontSize: 18, color: humPct > 85 ? '#dc2626' : 'var(--color-text-primary)' }}>
                  {humPct.toFixed(1)}%
                </span>
              </div>
            )}
          </div>
        </div>
      )}

      {/* ── Control Mode ── */}
      <div className="card">
        <div className="card-title">Control Mode</div>
        <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap' }}>
          {(Object.keys(MODE_INFO) as ControlMode[]).map((m) => {
            const info = MODE_INFO[m];
            const isActive = currentMode === m;
            return (
              <label
                key={m}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: 8,
                  padding: '10px 18px',
                  borderRadius: 8,
                  border: `2px solid ${isActive ? info.color : 'var(--color-border)'}`,
                  background: isActive ? `${info.color}18` : 'var(--color-surface)',
                  cursor: modeChanging ? 'not-allowed' : 'pointer',
                  fontWeight: isActive ? 700 : 400,
                  fontSize: 14,
                  transition: 'all 0.15s',
                  color: isActive ? info.color : 'var(--color-text-primary)',
                }}
              >
                <input
                  type="radio"
                  name="control-mode"
                  value={m}
                  checked={isActive}
                  disabled={modeChanging}
                  onChange={() => { void handleModeChange(m); }}
                  style={{ accentColor: info.color }}
                />
                {info.label}
              </label>
            );
          })}
        </div>
        <div style={{ fontSize: 13, color: 'var(--color-text-muted)', marginTop: 10, padding: '8px 12px', background: 'var(--color-bg)', borderRadius: 6 }}>
          <strong style={{ color: modeInfo.color }}>{modeInfo.label}:</strong>{' '}{modeInfo.description}
        </div>
      </div>

      {/* ── Fan Status ── */}
      <div className="card">
        <div className="card-title">Fan Status</div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 20 }}>
          {/* Animated fan icon */}
          <div
            style={{
              width: 72,
              height: 72,
              borderRadius: '50%',
              background: fanOn
                ? 'linear-gradient(135deg, #16a34a, #22c55e)'
                : 'linear-gradient(135deg, #94a3b8, #cbd5e1)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              boxShadow: fanOn ? '0 0 16px rgba(22,163,74,0.4)' : 'none',
              transition: 'background 0.3s, box-shadow 0.3s',
              flexShrink: 0,
            }}
          >
            <Fan
              size={36}
              color="#fff"
              className={fanOn ? 'fan-spinning' : 'fan-idle'}
            />
          </div>

          <div style={{ flex: 1 }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 4 }}>
              <span style={{
                fontWeight: 800,
                fontSize: 22,
                color: fanOn ? '#16a34a' : '#64748b',
              }}>
                Fan {fanOn ? 'ON' : 'OFF'}
              </span>
              {fanOn && (
                <span style={{ fontSize: 11, padding: '2px 8px', background: '#dcfce7', color: '#16a34a', borderRadius: 99, fontWeight: 700, border: '1px solid #86efac' }}>
                  RUNNING
                </span>
              )}
            </div>
            {controlState?.last_action_reason && (
              <div style={{ fontSize: 13, color: 'var(--color-text-secondary)', lineHeight: 1.5 }}>
                <Zap size={12} style={{ display: 'inline', marginRight: 4, verticalAlign: 'middle' }} />
                {controlState.last_action_reason}
              </div>
            )}
          </div>
        </div>

        {controlState?.manual_override_active && overrideSecondsLeft !== null && (
          <div
            style={{
              marginTop: 16,
              padding: '10px 14px',
              background: '#fffbeb',
              border: '1px solid #fcd34d',
              borderRadius: 8,
              fontSize: 13,
              display: 'flex',
              alignItems: 'center',
              gap: 8,
              color: '#92400e',
            }}
          >
            <Clock size={15} color="#d97706" />
            <span>
              Manual override active — expires in{' '}
              <strong>{Math.floor(overrideSecondsLeft / 60)}m {overrideSecondsLeft % 60}s</strong>
            </span>
          </div>
        )}
      </div>

      {/* ── Manual Override ── */}
      <div className="card">
        <div className="card-title">Manual Override</div>
        <div style={{ marginBottom: 16 }}>
          <label style={{ fontSize: 13, color: 'var(--color-text-secondary)', display: 'block', marginBottom: 6 }}>
            Duration
          </label>
          <select
            value={overrideDuration}
            onChange={(e) => setOverrideDuration(Number(e.target.value))}
            style={{
              padding: '7px 12px',
              borderRadius: 6,
              border: '1px solid var(--color-border)',
              fontSize: 13,
              background: 'var(--color-surface)',
              minWidth: 160,
            }}
          >
            {DURATION_OPTIONS.map((o) => (
              <option key={o.value} value={o.value}>
                {o.label}
              </option>
            ))}
          </select>
        </div>

        <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap' }}>
          <button
            onClick={() => { void handleOverride('fan_on'); }}
            disabled={actionLoading || fanOn}
            title={fanOn ? 'Fan is already ON' : 'Turn fan on manually'}
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: 8,
              padding: '11px 22px',
              background: fanOn ? '#d1fae5' : '#16a34a',
              color: fanOn ? '#16a34a' : '#fff',
              border: `2px solid ${fanOn ? '#86efac' : 'transparent'}`,
              borderRadius: 8,
              fontWeight: 700,
              fontSize: 14,
              opacity: actionLoading ? 0.6 : 1,
              cursor: actionLoading || fanOn ? 'not-allowed' : 'pointer',
              transition: 'all 0.15s',
            }}
          >
            <Power size={16} />
            Fan On
          </button>
          <button
            onClick={() => { void handleOverride('fan_off'); }}
            disabled={actionLoading || !fanOn}
            title={!fanOn ? 'Fan is already OFF' : 'Turn fan off manually'}
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: 8,
              padding: '11px 22px',
              background: !fanOn ? '#fee2e2' : '#dc2626',
              color: !fanOn ? '#dc2626' : '#fff',
              border: `2px solid ${!fanOn ? '#fca5a5' : 'transparent'}`,
              borderRadius: 8,
              fontWeight: 700,
              fontSize: 14,
              opacity: actionLoading ? 0.6 : 1,
              cursor: actionLoading || !fanOn ? 'not-allowed' : 'pointer',
              transition: 'all 0.15s',
            }}
          >
            <PowerOff size={16} />
            Fan Off
          </button>
          <button
            onClick={() => { void onRefresh(); }}
            disabled={actionLoading}
            title="Refresh control state"
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: 6,
              padding: '11px 16px',
              background: 'var(--color-bg)',
              color: 'var(--color-text-secondary)',
              border: '1px solid var(--color-border)',
              borderRadius: 8,
              fontSize: 13,
              cursor: 'pointer',
            }}
          >
            <RefreshCw size={14} />
            Refresh
          </button>
        </div>

        {actionError && (
          <div className="error-state" style={{ marginTop: 14 }}>
            {actionError}
          </div>
        )}
      </div>
    </div>
  );
}
