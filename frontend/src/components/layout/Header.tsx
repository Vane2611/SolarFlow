import { Wifi, WifiOff, AlertCircle } from 'lucide-react';

interface HeaderProps {
  title: string;
  lastUpdated: Date | null;
  simulationMode: boolean;
  connectionStatus: 'connected' | 'disconnected' | 'simulated' | null;
  error: string | null;
}

export function Header({
  title,
  lastUpdated,
  simulationMode,
  connectionStatus,
  error,
}: HeaderProps) {
  const formatTime = (date: Date) =>
    date.toLocaleTimeString('en-GB', { hour: '2-digit', minute: '2-digit', second: '2-digit' });

  const connColor =
    connectionStatus === 'connected'
      ? 'var(--color-success)'
      : connectionStatus === 'simulated'
      ? 'var(--color-warning)'
      : 'var(--color-danger)';

  return (
    <header
      style={{
        height: 60,
        background: 'var(--color-surface)',
        borderBottom: '1px solid var(--color-border)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        padding: '0 24px',
        flexShrink: 0,
        gap: 16,
      }}
    >
      <h1 style={{ fontSize: 18, fontWeight: 700, color: 'var(--color-text-primary)' }}>
        {title}
      </h1>

      <div style={{ display: 'flex', alignItems: 'center', gap: 16 }}>
        {/* Simulation badge */}
        {simulationMode && (
          <span className="badge badge-simulated">
            <AlertCircle size={10} />
            Simulated Data
          </span>
        )}

        {/* Error indicator */}
        {error && (
          <span
            style={{
              fontSize: 12,
              color: 'var(--color-danger)',
              maxWidth: 200,
              overflow: 'hidden',
              textOverflow: 'ellipsis',
              whiteSpace: 'nowrap',
            }}
            title={error}
          >
            {error}
          </span>
        )}

        {/* Last updated */}
        {lastUpdated && (
          <span style={{ fontSize: 12, color: 'var(--color-text-muted)' }}>
            Updated {formatTime(lastUpdated)}
          </span>
        )}

        {/* Connection status */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
          {connectionStatus === 'disconnected' ? (
            <WifiOff size={16} color={connColor} />
          ) : (
            <Wifi size={16} color={connColor} />
          )}
          <span style={{ fontSize: 12, color: connColor, fontWeight: 600 }}>
            {connectionStatus === 'connected'
              ? 'Live'
              : connectionStatus === 'simulated'
              ? 'Simulated'
              : connectionStatus === 'disconnected'
              ? 'Offline'
              : '—'}
          </span>
        </div>
      </div>
    </header>
  );
}
