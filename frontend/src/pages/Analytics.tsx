import { useCallback, useState } from 'react';
import { usePolling } from '../hooks/usePolling';
import { getAnalyticsComparison } from '../api/client';
import { ComparisonChart } from '../components/analytics/ComparisonChart';

const HOUR_OPTIONS = [6, 12, 24, 48, 72];

export function Analytics() {
  const [hours, setHours] = useState(24);

  const fetcher = useCallback(() => getAnalyticsComparison(hours), [hours]);
  const { data: snapshots, loading, error, lastUpdated } = usePolling(fetcher, 10_000);

  return (
    <div>
      {error && <div className="error-state" style={{ marginBottom: 16 }}>{error}</div>}

      <div className="card" style={{ marginBottom: 20 }}>
        <div
          style={{
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
            marginBottom: 16,
          }}
        >
          <div className="card-title" style={{ margin: 0 }}>
            Reactive vs Predictive Comparison
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <span style={{ fontSize: 13, color: 'var(--color-text-secondary)' }}>Period:</span>
            <select
              value={hours}
              onChange={(e) => setHours(Number(e.target.value))}
              style={{
                padding: '4px 8px',
                borderRadius: 6,
                border: '1px solid var(--color-border)',
                fontSize: 13,
                background: 'var(--color-surface)',
              }}
            >
              {HOUR_OPTIONS.map((h) => (
                <option key={h} value={h}>
                  Last {h}h
                </option>
              ))}
            </select>
          </div>
        </div>

        {loading && !snapshots ? (
          <div className="loading-state">Loading analytics…</div>
        ) : (
          <ComparisonChart snapshots={snapshots ?? []} />
        )}

        {lastUpdated && (
          <div style={{ fontSize: 11, color: 'var(--color-text-muted)', marginTop: 8 }}>
            Updated: {lastUpdated.toLocaleTimeString('en-GB')}
          </div>
        )}
      </div>

      <div
        style={{
          padding: '12px 16px',
          background: 'var(--color-info-light)',
          borderRadius: 8,
          fontSize: 13,
          color: 'var(--color-info)',
        }}
      >
        <strong>How to read this chart:</strong> Lower temp/humidity exceedance and avg response
        time indicate better performance. Fan runtime alone is not a quality metric — predictive
        mode may run the fan earlier but prevent threshold breaches.
      </div>
    </div>
  );
}
