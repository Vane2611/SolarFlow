import { useCallback, useState } from 'react';
import { usePolling } from '../hooks/usePolling';
import { getAlerts } from '../api/client';
import { AlertList } from '../components/alerts/AlertList';
import type { RiskLevel } from '../types';

type FilterLevel = RiskLevel | 'all';

const FILTER_OPTIONS: { label: string; value: FilterLevel }[] = [
  { label: 'All', value: 'all' },
  { label: 'Critical', value: 'critical' },
  { label: 'High', value: 'high' },
  { label: 'Medium', value: 'medium' },
  { label: 'Low', value: 'low' },
];

export function Alerts() {
  const [filterLevel, setFilterLevel] = useState<FilterLevel>('all');
  const [activeOnly, setActiveOnly] = useState(false);

  const fetcher = useCallback(() => getAlerts(activeOnly), [activeOnly]);
  const { data: alerts, loading, error } = usePolling(fetcher, 10_000);

  return (
    <div>
      {error && <div className="error-state" style={{ marginBottom: 16 }}>{error}</div>}

      {/* Filter bar */}
      <div
        className="card"
        style={{
          marginBottom: 16,
          display: 'flex',
          alignItems: 'center',
          gap: 16,
          flexWrap: 'wrap',
        }}
      >
        <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
          {FILTER_OPTIONS.map((opt) => (
            <button
              key={opt.value}
              onClick={() => setFilterLevel(opt.value)}
              style={{
                padding: '6px 14px',
                borderRadius: 20,
                border: '1px solid',
                borderColor: filterLevel === opt.value ? 'var(--color-sidebar-bg)' : 'var(--color-border)',
                background: filterLevel === opt.value ? 'var(--color-sidebar-bg)' : 'var(--color-surface)',
                color: filterLevel === opt.value ? '#fff' : 'var(--color-text-primary)',
                fontSize: 13,
                fontWeight: filterLevel === opt.value ? 600 : 400,
                cursor: 'pointer',
              }}
            >
              {opt.label}
            </button>
          ))}
        </div>

        <label
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: 6,
            fontSize: 13,
            cursor: 'pointer',
            marginLeft: 'auto',
          }}
        >
          <input
            type="checkbox"
            checked={activeOnly}
            onChange={(e) => setActiveOnly(e.target.checked)}
            style={{ accentColor: 'var(--color-sidebar-bg)' }}
          />
          Active only
        </label>
      </div>

      <div className="card">
        {loading && !alerts ? (
          <div className="loading-state">Loading alerts…</div>
        ) : (
          <AlertList alerts={alerts ?? []} filterLevel={filterLevel} />
        )}
      </div>
    </div>
  );
}
