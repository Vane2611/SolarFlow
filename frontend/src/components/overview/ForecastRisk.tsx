import type { PredictionsResponse } from '../../types';

interface ForecastRiskProps {
  predictions: PredictionsResponse | null;
  loading: boolean;
}

export function ForecastRisk({ predictions, loading }: ForecastRiskProps) {
  if (loading && !predictions) {
    return (
      <div className="card">
        <div className="loading-state">Loading forecast…</div>
      </div>
    );
  }

  if (!predictions?.latest) {
    return (
      <div className="card">
        <div className="card-title">Forecast Risk</div>
        <div className="empty-state">No forecast available yet</div>
      </div>
    );
  }

  const { latest, data_is_synthetic } = predictions;
  const forecasts = latest.forecasts ?? [];

  // Find highest risk point (highest predicted temperature)
  const peakForecast = forecasts.reduce(
    (max, f) => (f.predicted_temperature > (max?.predicted_temperature ?? -Infinity) ? f : max),
    forecasts[0] ?? null,
  );

  const atRisk = peakForecast !== null && peakForecast.predicted_temperature >= 28;
  const critical = peakForecast !== null && peakForecast.predicted_temperature >= 30;

  const riskColor = critical
    ? 'var(--color-danger)'
    : atRisk
    ? 'var(--color-warning)'
    : 'var(--color-success)';

  const riskLabel = critical ? 'HIGH' : atRisk ? 'MEDIUM' : 'LOW';

  return (
    <div className="card">
      <div className="card-title">Forecast Risk</div>

      {data_is_synthetic && (
        <div style={{ marginBottom: 12 }}>
          <span className="badge badge-unvalidated">UNVALIDATED MODEL</span>
        </div>
      )}

      <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 16 }}>
        <div
          style={{
            width: 48,
            height: 48,
            borderRadius: '50%',
            background: riskColor,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            color: '#fff',
            fontWeight: 700,
            fontSize: 11,
            flexShrink: 0,
          }}
        >
          {riskLabel}
        </div>
        <div>
          <div style={{ fontWeight: 600, fontSize: 15 }}>
            {critical
              ? 'Overheating risk predicted'
              : atRisk
              ? 'Temperature approaching limit'
              : 'Conditions look stable'}
          </div>
          <div style={{ fontSize: 12, color: 'var(--color-text-secondary)', marginTop: 2 }}>
            Model: {latest.model_version}
          </div>
        </div>
      </div>

      {peakForecast && (
        <div
          style={{
            background: 'var(--color-bg)',
            borderRadius: 8,
            padding: '12px 16px',
            fontSize: 13,
          }}
        >
          <div style={{ marginBottom: 6 }}>
            <span style={{ color: 'var(--color-text-secondary)' }}>Predicted peak temp: </span>
            <strong style={{ color: riskColor }}>
              {peakForecast.predicted_temperature.toFixed(1)}°C
            </strong>
            <span style={{ color: 'var(--color-text-muted)', marginLeft: 6, fontSize: 12 }}>
              at +{peakForecast.horizon_minutes} min
            </span>
          </div>
          <div>
            <span style={{ color: 'var(--color-text-secondary)' }}>Predicted humidity: </span>
            <strong>{peakForecast.predicted_humidity.toFixed(1)}%</strong>
          </div>
        </div>
      )}
    </div>
  );
}
