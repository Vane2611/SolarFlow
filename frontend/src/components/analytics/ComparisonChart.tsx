import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from 'recharts';
import type { AnalyticsSnapshot } from '../../types';

interface ComparisonChartProps {
  snapshots: AnalyticsSnapshot[];
}

interface MetricDatum {
  metric: string;
  reactive: number;
  predictive: number;
  unit: string;
}

function secondsToMinutes(s: number): number {
  return Math.round((s / 60) * 10) / 10;
}

export function ComparisonChart({ snapshots }: ComparisonChartProps) {
  const reactive = snapshots.find((s) => s.mode === 'reactive');
  const predictive = snapshots.find((s) => s.mode === 'predictive');

  if (!reactive && !predictive) {
    return (
      <div
        style={{
          padding: '32px',
          background: 'var(--color-bg)',
          borderRadius: 8,
          textAlign: 'center',
          color: 'var(--color-text-muted)',
          fontStyle: 'italic',
          fontSize: 14,
        }}
      >
        Insufficient data — run both modes to populate analytics comparison.
      </div>
    );
  }

  const data: MetricDatum[] = [
    {
      metric: 'Fan Runtime',
      reactive: secondsToMinutes(reactive?.fan_runtime_seconds ?? 0),
      predictive: secondsToMinutes(predictive?.fan_runtime_seconds ?? 0),
      unit: 'min',
    },
    {
      metric: 'Temp Exceedance',
      reactive: secondsToMinutes(reactive?.temp_exceedance_seconds ?? 0),
      predictive: secondsToMinutes(predictive?.temp_exceedance_seconds ?? 0),
      unit: 'min',
    },
    {
      metric: 'Humidity Exceedance',
      reactive: secondsToMinutes(reactive?.humidity_exceedance_seconds ?? 0),
      predictive: secondsToMinutes(predictive?.humidity_exceedance_seconds ?? 0),
      unit: 'min',
    },
    {
      metric: 'Avg Response Time',
      reactive: reactive?.avg_response_time_seconds ?? 0,
      predictive: predictive?.avg_response_time_seconds ?? 0,
      unit: 's',
    },
  ];

  return (
    <div>
      <ResponsiveContainer width="100%" height={320}>
        <BarChart data={data} margin={{ top: 8, right: 16, left: 0, bottom: 8 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
          <XAxis dataKey="metric" tick={{ fontSize: 12 }} tickLine={false} />
          <YAxis tick={{ fontSize: 11 }} tickLine={false} />
          <Tooltip
            contentStyle={{ fontSize: 12 }}
            formatter={(value: number, name: string, props: { payload?: MetricDatum }) => {
              const unit = props.payload?.unit ?? '';
              return [`${value} ${unit}`, name];
            }}
          />
          <Legend wrapperStyle={{ fontSize: 12 }} />
          <Bar dataKey="reactive" name="Reactive" fill="#dc2626" radius={[4, 4, 0, 0]} />
          <Bar dataKey="predictive" name="Predictive" fill="#1a4731" radius={[4, 4, 0, 0]} />
        </BarChart>
      </ResponsiveContainer>

      {/* Summary stats table */}
      <div style={{ marginTop: 20 }}>
        <table
          style={{
            width: '100%',
            borderCollapse: 'collapse',
            fontSize: 13,
          }}
        >
          <thead>
            <tr style={{ background: 'var(--color-bg)' }}>
              <th style={{ padding: '8px 12px', textAlign: 'left', borderBottom: '1px solid var(--color-border)', color: 'var(--color-text-secondary)', fontWeight: 600 }}>
                Metric
              </th>
              <th style={{ padding: '8px 12px', textAlign: 'right', borderBottom: '1px solid var(--color-border)', color: '#dc2626', fontWeight: 600 }}>
                Reactive
              </th>
              <th style={{ padding: '8px 12px', textAlign: 'right', borderBottom: '1px solid var(--color-border)', color: '#1a4731', fontWeight: 600 }}>
                Predictive
              </th>
            </tr>
          </thead>
          <tbody>
            <tr style={{ borderBottom: '1px solid var(--color-border)' }}>
              <td style={{ padding: '8px 12px' }}>Alerts triggered</td>
              <td style={{ padding: '8px 12px', textAlign: 'right' }}>{reactive?.num_alerts ?? '—'}</td>
              <td style={{ padding: '8px 12px', textAlign: 'right' }}>{predictive?.num_alerts ?? '—'}</td>
            </tr>
            <tr style={{ borderBottom: '1px solid var(--color-border)' }}>
              <td style={{ padding: '8px 12px' }}>Fan runtime (min)</td>
              <td style={{ padding: '8px 12px', textAlign: 'right' }}>
                {reactive ? secondsToMinutes(reactive.fan_runtime_seconds) : '—'}
              </td>
              <td style={{ padding: '8px 12px', textAlign: 'right' }}>
                {predictive ? secondsToMinutes(predictive.fan_runtime_seconds) : '—'}
              </td>
            </tr>
            <tr style={{ borderBottom: '1px solid var(--color-border)' }}>
              <td style={{ padding: '8px 12px' }}>Temp exceedance (min)</td>
              <td style={{ padding: '8px 12px', textAlign: 'right' }}>
                {reactive ? secondsToMinutes(reactive.temp_exceedance_seconds) : '—'}
              </td>
              <td style={{ padding: '8px 12px', textAlign: 'right' }}>
                {predictive ? secondsToMinutes(predictive.temp_exceedance_seconds) : '—'}
              </td>
            </tr>
            <tr>
              <td style={{ padding: '8px 12px' }}>Avg response time (s)</td>
              <td style={{ padding: '8px 12px', textAlign: 'right' }}>
                {reactive?.avg_response_time_seconds.toFixed(1) ?? '—'}
              </td>
              <td style={{ padding: '8px 12px', textAlign: 'right' }}>
                {predictive?.avg_response_time_seconds.toFixed(1) ?? '—'}
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  );
}
