import { useCallback } from 'react';
import { usePolling } from '../hooks/usePolling';
import { getPredictions, getReadingHistory } from '../api/client';
import { ForecastChart } from '../components/predictions/ForecastChart';

export function Predictions() {
  const predFetcher = useCallback(() => getPredictions(), []);
  const histFetcher = useCallback(() => getReadingHistory(100), []);

  const { data: predictions, loading, error } = usePolling(predFetcher, 30_000);
  const { data: history } = usePolling(histFetcher, 30_000);

  return (
    <div>
      {error && <div className="error-state" style={{ marginBottom: 16 }}>{error}</div>}

      <div className="card">
        <div className="card-title">30-Minute Forecast</div>
        {loading && !predictions ? (
          <div className="loading-state">Loading forecast…</div>
        ) : (
          <ForecastChart
            history={history ?? []}
            forecast={predictions?.latest ?? null}
            dataIsSynthetic={predictions?.data_is_synthetic ?? true}
          />
        )}
      </div>
    </div>
  );
}
