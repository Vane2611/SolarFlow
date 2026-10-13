import { useCallback } from 'react';
import { usePolling } from '../hooks/usePolling';
import { getDeviceStatus } from '../api/client';
import { DeviceHealthCard } from '../components/devices/DeviceHealth';

export function DeviceHealthPage() {
  const fetcher = useCallback(() => getDeviceStatus(), []);
  const { data: status, loading, error, lastUpdated } = usePolling(fetcher, 10_000);

  return (
    <div>
      {error && <div className="error-state" style={{ marginBottom: 16 }}>{error}</div>}

      <div className="grid-2" style={{ marginBottom: 20 }}>
        <DeviceHealthCard status={status} loading={loading} />

        <div className="card">
          <div className="card-title">Connection Guide</div>
          <div style={{ fontSize: 13, color: 'var(--color-text-secondary)', lineHeight: 1.6 }}>
            <p style={{ marginBottom: 8 }}>
              <strong>Simulated mode:</strong> The backend generates synthetic sensor data. No
              hardware is required.
            </p>
            <p style={{ marginBottom: 8 }}>
              <strong>Hardware mode:</strong> Connect the Arduino via USB, set the{' '}
              <code>SERIAL_PORT</code> environment variable, and restart the backend. The firmware
              sends readings every 5 seconds.
            </p>
            <p>
              <strong>Stale data:</strong> A warning appears if the last reading is more than 30
              seconds old, which may indicate a sensor or connection problem.
            </p>
          </div>
        </div>
      </div>

      {/* Raw status JSON */}
      {status && (
        <div className="card">
          <div className="card-title">Raw Device Status</div>
          <pre
            style={{
              fontSize: 12,
              background: '#1e293b',
              color: '#e2e8f0',
              padding: '16px',
              borderRadius: 8,
              overflowX: 'auto',
              lineHeight: 1.5,
            }}
          >
            {JSON.stringify(status, null, 2)}
          </pre>
        </div>
      )}

      {lastUpdated && (
        <div style={{ fontSize: 11, color: 'var(--color-text-muted)', marginTop: 12 }}>
          Last updated: {lastUpdated.toLocaleTimeString('en-GB')}
        </div>
      )}
    </div>
  );
}
