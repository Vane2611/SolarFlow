import { AlertTriangle, CheckCircle } from 'lucide-react';
import type { Alert, RiskLevel } from '../../types';

interface TopAlertProps {
  alerts: Alert[] | null;
  loading: boolean;
}

function riskBg(level: RiskLevel): string {
  switch (level) {
    case 'critical': return '#fce7f3';
    case 'high': return 'var(--color-danger-light)';
    case 'medium': return 'var(--color-warning-light)';
    default: return 'var(--color-info-light)';
  }
}

function riskText(level: RiskLevel): string {
  switch (level) {
    case 'critical': return '#9d174d';
    case 'high': return '#991b1b';
    case 'medium': return '#92400e';
    default: return '#1e40af';
  }
}

const RISK_ORDER: RiskLevel[] = ['critical', 'high', 'medium', 'low'];

export function TopAlert({ alerts, loading }: TopAlertProps) {
  if (loading && !alerts) {
    return (
      <div className="card">
        <div className="loading-state">Loading alerts…</div>
      </div>
    );
  }

  const activeAlerts = alerts?.filter((a) => a.is_active) ?? [];
  const top = activeAlerts.sort(
    (a, b) => RISK_ORDER.indexOf(a.risk_level) - RISK_ORDER.indexOf(b.risk_level),
  )[0];

  if (!top) {
    return (
      <div className="card" style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
        <CheckCircle size={32} color="var(--color-success)" />
        <div>
          <div style={{ fontWeight: 600 }}>No active alerts</div>
          <div style={{ fontSize: 12, color: 'var(--color-text-secondary)' }}>
            Greenhouse conditions are within normal limits
          </div>
        </div>
      </div>
    );
  }

  return (
    <div
      className="card"
      style={{
        background: riskBg(top.risk_level),
        borderColor: riskText(top.risk_level),
      }}
    >
      <div className="card-title" style={{ color: riskText(top.risk_level) }}>
        Active Alert
      </div>
      <div style={{ display: 'flex', alignItems: 'flex-start', gap: 12 }}>
        <AlertTriangle size={24} color={riskText(top.risk_level)} style={{ flexShrink: 0, marginTop: 2 }} />
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 6 }}>
            <span className={`badge badge-${top.risk_level}`}>
              {top.risk_level.toUpperCase()}
            </span>
            <span style={{ fontSize: 12, color: 'var(--color-text-secondary)' }}>
              {top.alert_type.replace(/_/g, ' ')}
            </span>
          </div>
          <div style={{ fontWeight: 600, color: riskText(top.risk_level) }}>{top.message}</div>
          <div style={{ fontSize: 11, color: 'var(--color-text-muted)', marginTop: 6 }}>
            {new Date(top.timestamp).toLocaleString('en-GB')}
          </div>
          {activeAlerts.length > 1 && (
            <div style={{ fontSize: 12, marginTop: 8, color: 'var(--color-text-secondary)' }}>
              +{activeAlerts.length - 1} more active alert{activeAlerts.length > 2 ? 's' : ''}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
