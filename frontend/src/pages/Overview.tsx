import { useCallback } from 'react';
import { usePolling } from '../hooks/usePolling';
import { getLatestReading, getPredictions, getAlerts, getReadingHistory } from '../api/client';
import { CurrentConditions } from '../components/overview/CurrentConditions';
import { ForecastRisk } from '../components/overview/ForecastRisk';
import { TopAlert } from '../components/overview/TopAlert';
import { LiveChart } from '../components/monitoring/LiveChart';

export function Overview() {
  const readingFetcher = useCallback(() => getLatestReading(), []);
  const predictionFetcher = useCallback(() => getPredictions(), []);
  const alertsFetcher = useCallback(() => getAlerts(false), []);
  const historyFetcher = useCallback(() => getReadingHistory(60), []);

  const { data: reading, loading: readingLoading } = usePolling(readingFetcher, 5_000);
  const { data: predictions, loading: predLoading } = usePolling(predictionFetcher, 5_000);
  const { data: alerts, loading: alertsLoading } = usePolling(alertsFetcher, 5_000);
  const { data: history } = usePolling(historyFetcher, 5_000);

  return (
    <div>
      <div className="grid-3" style={{ marginBottom: 20 }}>
        <CurrentConditions reading={reading} loading={readingLoading} />
        <ForecastRisk predictions={predictions} loading={predLoading} />
        <TopAlert alerts={alerts} loading={alertsLoading} />
      </div>

      <div className="card">
        <div className="card-title">Live Temperature &amp; Humidity</div>
        <LiveChart readings={history ?? []} />
      </div>
    </div>
  );
}
