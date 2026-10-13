import { Wifi, WifiOff, Server } from 'lucide-react';
import type { DeviceStatus } from '../../types';

interface DeviceHealthProps {
  status: DeviceStatus | null;
  loading: boolean;
}

const STALE_THRESHOLD_MS = 30_000;

function ConnectionDot({ status }: { status: DeviceStatus['connection_status'] | null }) {
  if (!status) return <span className="status-dot status-dot-gray" />;
  if (status === 'connected') return <span className="status-dot status-dot-green" />;
  if (status === 'simulated') return <span className="status-dot status-dot-amber" />;
  return <span className="status-dot status-dot-red" />;
}

export function DeviceHealthCard({ status, loading }: DeviceHealthProps) {
  if (loading && !status) {
    return (
      <div className="card">
        <div className="loading-state">Loading device status…</div>
      </div>
    );
  }

  if (!status) {
    return (
      <div className="card">
        <div className="empty-state">Device status unavailable</div>
      </div>
    );
  }

  const lastReadingDate = status.last_reading_at ? new Date(status.last_reading_at) : null;
  const isStale =
    lastReadingDate !== null && Date.now() - lastReadingDate.getTime() > STALE_THRESHOLD_MS;

  return (
    <div className="card">
      <div className="card-title">Device Health</div>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
        {/* Connection status */}
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            {status.connection_status === 'disconnected' ? (
              <WifiOff size={16} color="var(--color-danger)" />
            ) : (
              <Wifi size={16} color={status.connection_status === 'connected' ? 'var(--color-success)' : 'var(--color-warning)'} />
            )}
            <span style={{ fontSize: 14, fontWeight: 500 }}>Connection</span>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
            <ConnectionDot status={status.connection_status} />
            <span
              style={{
                fontSize: 13,
                fontWeight: 600,
                color: status.connection_status === 'connected'
                  ? 'var(--color-success)'
                  : status.connection_status === 'simulated'
                  ? 'var(--color-warning)'
                  : 'var(--color-danger)',
              }}
            >
              {status.connection_status.toUpperCase()}
            </span>
          </div>
        </div>

        {/* Mode */}
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <Server size={16} color="var(--color-text-secondary)" />
            <span style={{ fontSize: 14, fontWeight: 500 }}>Mode</span>
          </div>
          <span>
            {status.simulation_mode ? (
              <span className="badge badge-simulated">SIMULATED</span>
            ) : (
              <span className="badge badge-live">HARDWARE</span>
            )}
          </span>
        </div>

        {/* Serial port */}
        {status.serial_port !== null && (
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
            <span style={{ fontSize: 14, fontWeight: 500, color: 'var(--color-text-secondary)' }}>
              Serial Port
            </span>
            <code style={{ fontSize: 13, background: 'var(--color-bg)', padding: '2px 6px', borderRadius: 4 }}>
              {status.serial_port}
            </code>
          </div>
        )}

        {/* Last reading */}
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: 4 }}>
          <span style={{ fontSize: 14, fontWeight: 500, color: 'var(--color-text-secondary)' }}>
            Last Reading
          </span>
          <span style={{ fontSize: 13, color: isStale ? 'var(--color-danger)' : 'var(--color-text-primary)' }}>
            {lastReadingDate
              ? lastReadingDate.toLocaleString('en-GB')
              : 'Never'}
            {isStale && (
              <span style={{ marginLeft: 6, fontWeight: 600, color: 'var(--color-danger)' }}>
                ⚠ STALE
              </span>
            )}
          </span>
        </div>

        {/* Firmware */}
        {status.firmware_version !== null && (
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
            <span style={{ fontSize: 14, fontWeight: 500, color: 'var(--color-text-secondary)' }}>
              Firmware
            </span>
            <code style={{ fontSize: 13 }}>{status.firmware_version}</code>
          </div>
        )}

        {/* Uptime */}
        {status.uptime_seconds !== null && (
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
            <span style={{ fontSize: 14, fontWeight: 500, color: 'var(--color-text-secondary)' }}>
              Uptime
            </span>
            <span style={{ fontSize: 13 }}>
              {Math.floor(status.uptime_seconds / 3600)}h{' '}
              {Math.floor((status.uptime_seconds % 3600) / 60)}m
            </span>
          </div>
        )}

        {/* Last error */}
        {status.last_error !== null && (
          <div
            style={{
              padding: '8px 12px',
              background: 'var(--color-danger-light)',
              borderRadius: 6,
              fontSize: 12,
              color: 'var(--color-danger)',
            }}
          >
            <strong>Last error:</strong> {status.last_error}
          </div>
        )}
      </div>
    </div>
  );
}
