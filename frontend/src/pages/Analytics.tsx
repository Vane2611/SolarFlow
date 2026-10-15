import { useCallback, useState } from 'react';
import { usePolling } from '../hooks/usePolling';
import { getAnalyticsSummary } from '../api/client';
import { ComparisonChart } from '../components/analytics/ComparisonChart';
import { Clock, RefreshCw, Info } from 'lucide-react';

const HOUR_OPTIONS = [
  { label: 'Last 6 h', value: 6 },
  { label: 'Last 12 h', value: 12 },
  { label: 'Last 24 h', value: 24 },
  { label: 'Last 48 h', value: 48 },
  { label: 'Last 72 h', value: 72 },
];

export function Analytics() {
  const [hours, setHours] = useState(24);

  const fetcher = useCallback(() => getAnalyticsSummary(hours), [hours]);
  const { data: summary, loading, error, lastUpdated } = usePolling(fetcher, 15_000);

  const totalSamples = summary?.modes.reduce((s, m) => s + m.sample_count, 0) ?? 0;
  const bestMode = summary?.modes.length
    ? [...summary.modes].sort((a, b) => b.efficiency_score - a.efficiency_score)[0]
    : null;

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>

      {error && (
        <div className="error-state">{error}</div>
      )}

      {/* ── Page header bar ── */}
      <div
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          flexWrap: 'wrap',
          gap: 12,
        }}
      >
        <div>
          <h2 style={{ fontSize: 20, fontWeight: 700, margin: 0 }}>
            Performance Analytics
          </h2>
          <p style={{ fontSize: 13, color: 'var(--color-text-muted)', margin: '4px 0 0' }}>
            Comparing reactive vs predictive control over the selected window
          </p>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          {/* Period selector */}
          <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
            <Clock size={14} color="var(--color-text-muted)" />
            <select
              value={hours}
              onChange={(e) => setHours(Number(e.target.value))}
              style={{
                padding: '6px 10px',
                borderRadius: 6,
                border: '1px solid var(--color-border)',
                fontSize: 13,
                background: 'var(--color-surface)',
                color: 'var(--color-text-primary)',
              }}
            >
              {HOUR_OPTIONS.map((o) => (
                <option key={o.value} value={o.value}>
                  {o.label}
                </option>
              ))}
            </select>
          </div>

          {/* Last updated */}
          {lastUpdated && (
            <span style={{ fontSize: 12, color: 'var(--color-text-muted)', display: 'flex', alignItems: 'center', gap: 4 }}>
              <RefreshCw size={11} />
              {lastUpdated.toLocaleTimeString('en-GB')}
            </span>
          )}
        </div>
      </div>

      {/* ── Summary stat pills ── */}
      {summary && (
        <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap' }}>
          <StatPill label="Window" value={`${summary.window_hours} h`} />
          <StatPill label="Modes tracked" value={String(summary.modes.length)} />
          <StatPill label="Total samples" value={String(totalSamples)} />
          {bestMode && (
            <StatPill
              label="Best performer"
              value={bestMode.mode.charAt(0).toUpperCase() + bestMode.mode.slice(1)}
              highlight
            />
          )}
        </div>
      )}

      {/* ── Main chart card ── */}
      <div className="card">
        {loading && !summary ? (
          <div className="loading-state" style={{ padding: '40px 0' }}>
            Loading analytics…
          </div>
        ) : (
          <ComparisonChart
            modes={summary?.modes ?? []}
            timeSeries={summary?.time_series ?? []}
          />
        )}
      </div>

      {/* ── Interpretation callout ── */}
      <div
        style={{
          display: 'flex',
          gap: 10,
          padding: '14px 16px',
          background: '#eff6ff',
          border: '1px solid #bfdbfe',
          borderRadius: 8,
          fontSize: 13,
          color: '#1e40af',
          lineHeight: 1.6,
        }}
      >
        <Info size={16} style={{ flexShrink: 0, marginTop: 2 }} />
        <div>
          <strong>How to read this:</strong> Lower temperature exceedance and faster response time
          = higher efficiency score. Predictive mode may use <em>more</em> fan runtime but should
          show <em>less</em> time above the 32 °C limit. Fan runtime alone is not a quality metric.
          Switch modes in the <strong>Automation</strong> page and return here after a few minutes
          to see the comparison populate.
        </div>
      </div>
    </div>
  );
}

function StatPill({
  label,
  value,
  highlight,
}: {
  label: string;
  value: string;
  highlight?: boolean;
}) {
  return (
    <div
      style={{
        padding: '8px 16px',
        borderRadius: 99,
        background: highlight ? '#dcfce7' : 'var(--color-surface)',
        border: `1px solid ${highlight ? '#86efac' : 'var(--color-border)'}`,
        display: 'flex',
        alignItems: 'center',
        gap: 8,
      }}
    >
      <span style={{ fontSize: 11, color: highlight ? '#166534' : 'var(--color-text-muted)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
        {label}
      </span>
      <span style={{ fontSize: 14, fontWeight: 700, color: highlight ? '#16a34a' : 'var(--color-text-primary)' }}>
        {value}
      </span>
    </div>
  );
}
