import { useCallback } from 'react';
import { CheckCircle2, Lightbulb, RefreshCw, TriangleAlert } from 'lucide-react';
import { getAdvisory } from '../api/client';
import { usePolling } from '../hooks/usePolling';

const PRIORITY_LABELS = {
  urgent: 'Urgent',
  high: 'High priority',
  medium: 'Review soon',
  low: 'Routine',
} as const;

export function Advisory() {
  const fetcher = useCallback(() => getAdvisory(), []);
  const { data, loading, error } = usePolling(fetcher, 30_000);

  return (
    <div>
      <div className="advisory-intro card">
        <div className="advisory-intro-icon"><Lightbulb size={24} /></div>
        <div>
          <div className="card-title" style={{ marginBottom: 4 }}>Greenhouse advisor</div>
          <p>Practical recommendations based on your latest readings, forecasts, alerts, and automation state.</p>
        </div>
        <RefreshCw size={16} className={loading ? 'spin' : ''} aria-label="Refreshing recommendations" />
      </div>

      {error && <div className="error-state mt-16">{error}</div>}
      {loading && !data ? (
        <div className="card loading-state mt-16">Analysing greenhouse conditions…</div>
      ) : data ? (
        <>
          <div className="advisory-summary mt-16">
            {data.recommendations[0]?.priority === 'urgent' || data.recommendations[0]?.priority === 'high'
              ? <TriangleAlert size={20} />
              : <CheckCircle2 size={20} />}
            <span>{data.summary}</span>
          </div>
          <div className="advisory-list mt-16">
            {data.recommendations.map((recommendation) => (
              <article className={`advisory-card advisory-${recommendation.priority}`} key={recommendation.id}>
                <div className="advisory-card-header">
                  <div>
                    <span className="advisory-priority">{PRIORITY_LABELS[recommendation.priority]}</span>
                    <h2>{recommendation.title}</h2>
                  </div>
                  <span className="text-small text-muted">{Math.round(recommendation.confidence * 100)}% confidence</span>
                </div>
                <p className="advisory-action"><strong>What to do:</strong> {recommendation.action}</p>
                <p className="text-muted text-small">{recommendation.reason}</p>
              </article>
            ))}
          </div>
          <div className="card advisory-basis mt-16">
            <div className="card-title">Decision context</div>
            {data.data_basis.length ? data.data_basis.map((item) => <div key={item}>• {item}</div>) : <div className="text-muted">Waiting for sensor data.</div>}
            <div className="text-muted text-small mt-8">Updated {new Date(data.generated_at).toLocaleString('en-GB')}</div>
          </div>
        </>
      ) : null}
    </div>
  );
}
