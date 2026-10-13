import type { SensorReading } from '../../types';

interface CurrentConditionsProps {
  reading: SensorReading | null;
  loading: boolean;
}

function tempColor(temp: number): string {
  if (temp >= 30) return 'var(--color-danger)';
  if (temp >= 28) return 'var(--color-warning)';
  return 'var(--color-success)';
}

export function CurrentConditions({ reading, loading }: CurrentConditionsProps) {
  if (loading && !reading) {
    return (
      <div className="card">
        <div className="loading-state">Loading conditions…</div>
      </div>
    );
  }

  if (!reading) {
    return (
      <div className="card">
        <div className="empty-state">No sensor data available</div>
      </div>
    );
  }

  return (
    <div className="card">
      <div className="card-title">Current Conditions</div>

      {/* Source badge */}
      <div style={{ marginBottom: 16 }}>
        <span className={`badge ${reading.data_source === 'simulated' ? 'badge-simulated' : 'badge-live'}`}>
          {reading.data_source === 'simulated' ? 'SIMULATED' : 'LIVE'}
        </span>
      </div>

      <div className="grid-2" style={{ gap: 24 }}>
        {/* Temperature */}
        <div>
          <div style={{ fontSize: 12, color: 'var(--color-text-secondary)', marginBottom: 4 }}>
            Temperature
          </div>
          <div
            style={{
              fontSize: 48,
              fontWeight: 700,
              lineHeight: 1,
              color: tempColor(reading.temperature),
            }}
          >
            {reading.temperature.toFixed(1)}
            <span style={{ fontSize: 20, fontWeight: 400 }}>°C</span>
          </div>
          <div style={{ fontSize: 11, color: 'var(--color-text-muted)', marginTop: 4 }}>
            {reading.temperature >= 30
              ? '⚠ Above threshold'
              : reading.temperature >= 28
              ? '⚠ Approaching threshold'
              : '✓ Normal'}
          </div>
        </div>

        {/* Humidity */}
        <div>
          <div style={{ fontSize: 12, color: 'var(--color-text-secondary)', marginBottom: 4 }}>
            Relative Humidity
          </div>
          <div
            style={{
              fontSize: 48,
              fontWeight: 700,
              lineHeight: 1,
              color: reading.humidity > 85 ? 'var(--color-danger)' : 'var(--color-info)',
            }}
          >
            {reading.humidity.toFixed(1)}
            <span style={{ fontSize: 20, fontWeight: 400 }}>%</span>
          </div>
          <div style={{ fontSize: 11, color: 'var(--color-text-muted)', marginTop: 4 }}>
            {reading.humidity > 85 ? '⚠ Above threshold' : '✓ Normal'}
          </div>
        </div>
      </div>

      <div
        style={{
          marginTop: 16,
          fontSize: 11,
          color: 'var(--color-text-muted)',
          borderTop: '1px solid var(--color-border)',
          paddingTop: 12,
        }}
      >
        Last reading: {new Date(reading.timestamp).toLocaleString('en-GB')}
      </div>
    </div>
  );
}
