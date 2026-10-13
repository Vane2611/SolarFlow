import { AlertTriangle, AlertCircle, Info, CheckCircle } from 'lucide-react';
import type { Alert, RiskLevel } from '../../types';

interface AlertListProps {
  alerts: Alert[];
  filterLevel: RiskLevel | 'all';
}

function riskColor(level: RiskLevel): string {
  switch (level) {
    case 'critical': return '#9d174d';
    case 'high': return '#991b1b';
    case 'medium': return '#92400e';
    default: return '#1e40af';
  }
}

function riskBg(level: RiskLevel): string {
  switch (level) {
    case 'critical': return '#fce7f3';
    case 'high': return 'var(--color-danger-light)';
    case 'medium': return 'var(--color-warning-light)';
    default: return 'var(--color-info-light)';
  }
}

function RiskIcon({ level }: { level: RiskLevel }) {
  const color = riskColor(level);
  switch (level) {
    case 'critical':
    case 'high':
      return <AlertTriangle size={18} color={color} />;
    case 'medium':
      return <AlertCircle size={18} color={color} />;
    default:
      return <Info size={18} color={color} />;
  }
}

export function AlertList({ alerts, filterLevel }: AlertListProps) {
  const filtered =
    filterLevel === 'all' ? alerts : alerts.filter((a) => a.risk_level === filterLevel);

  if (filtered.length === 0) {
    return (
      <div className="empty-state">
        <CheckCircle size={24} color="var(--color-success)" style={{ marginRight: 8 }} />
        No alerts to display
      </div>
    );
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
      {filtered.map((alert) => (
        <div
          key={alert.id}
          style={{
            background: riskBg(alert.risk_level),
            border: `1px solid ${riskColor(alert.risk_level)}40`,
            borderLeft: `4px solid ${riskColor(alert.risk_level)}`,
            borderRadius: 8,
            padding: '12px 16px',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'flex-start', gap: 10 }}>
            <RiskIcon level={alert.risk_level} />
            <div style={{ flex: 1 }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 4, flexWrap: 'wrap' }}>
                <span className={`badge badge-${alert.risk_level}`}>
                  {alert.risk_level.toUpperCase()}
                </span>
                <span
                  style={{
                    fontSize: 12,
                    color: 'var(--color-text-secondary)',
                    background: 'rgba(0,0,0,0.06)',
                    padding: '1px 6px',
                    borderRadius: 4,
                  }}
                >
                  {alert.alert_type.replace(/_/g, ' ')}
                </span>
                {!alert.is_active && (
                  <span
                    style={{
                      fontSize: 11,
                      color: 'var(--color-success)',
                      fontWeight: 600,
                    }}
                  >
                    RESOLVED
                  </span>
                )}
              </div>
              <div style={{ fontWeight: 600, color: riskColor(alert.risk_level), fontSize: 14 }}>
                {alert.message}
              </div>
              <div
                style={{
                  display: 'flex',
                  gap: 16,
                  marginTop: 6,
                  fontSize: 11,
                  color: 'var(--color-text-muted)',
                }}
              >
                <span>Triggered: {new Date(alert.timestamp).toLocaleString('en-GB')}</span>
                {alert.resolved_at && (
                  <span>
                    Resolved: {new Date(alert.resolved_at).toLocaleString('en-GB')}
                  </span>
                )}
              </div>
            </div>
          </div>
        </div>
      ))}
    </div>
  );
}
