import {
  BarChart, Bar,
  LineChart, Line,
  XAxis, YAxis,
  CartesianGrid, Tooltip,
  Legend, ResponsiveContainer,
  ReferenceLine,
} from 'recharts';
import type { AnalyticsSnapshot, ModeKPIs } from '../../types';

// ── Colour palette ─────────────────────────────────────────────────────────
const MODE_COLORS: Record<string, string> = {
  reactive: '#f59e0b',
  predictive: '#3b82f6',
  manual: '#8b5cf6',
};
const MODE_LABELS: Record<string, string> = {
  reactive: 'Reactive',
  predictive: 'Predictive',
  manual: 'Manual',
};

function fmt(n: number | null | undefined, decimals = 1): string {
  if (n == null) return '—';
  return n.toFixed(decimals);
}
function s2m(s: number): number {
  return Math.round((s / 60) * 10) / 10;
}

// ── Efficiency gauge (arc SVG) ─────────────────────────────────────────────
function EfficiencyGauge({ score, color }: { score: number; color: string }) {
  const r = 36;
  const cx = 50;
  const cy = 50;
  const circumference = Math.PI * r; // half-circle
  const strokeDash = (score / 100) * circumference;

  return (
    <svg width={100} height={60} viewBox="0 0 100 60" aria-label={`Efficiency ${score}%`}>
      {/* Background arc */}
      <path
        d={`M ${cx - r} ${cy} A ${r} ${r} 0 0 1 ${cx + r} ${cy}`}
        fill="none"
        stroke="#e2e8f0"
        strokeWidth={10}
        strokeLinecap="round"
      />
      {/* Score arc */}
      <path
        d={`M ${cx - r} ${cy} A ${r} ${r} 0 0 1 ${cx + r} ${cy}`}
        fill="none"
        stroke={color}
        strokeWidth={10}
        strokeLinecap="round"
        strokeDasharray={`${strokeDash} ${circumference}`}
        style={{ transition: 'stroke-dasharray 0.6s ease' }}
      />
      <text x={cx} y={cy - 4} textAnchor="middle" fontSize={15} fontWeight={700} fill={color}>
        {score}
      </text>
      <text x={cx} y={cy + 10} textAnchor="middle" fontSize={9} fill="#94a3b8">
        / 100
      </text>
    </svg>
  );
}

// ── KPI card ────────────────────────────────────────────────────────────────
interface KpiCardProps {
  kpi: ModeKPIs;
}
function KpiCard({ kpi }: KpiCardProps) {
  const color = MODE_COLORS[kpi.mode] ?? '#64748b';
  const label = MODE_LABELS[kpi.mode] ?? kpi.mode;

  return (
    <div
      style={{
        flex: '1 1 220px',
        border: `2px solid ${color}33`,
        borderTop: `4px solid ${color}`,
        borderRadius: 10,
        padding: '16px 20px',
        background: 'var(--color-surface)',
        display: 'flex',
        flexDirection: 'column',
        gap: 10,
        minWidth: 200,
      }}
    >
      {/* Mode header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <span style={{ fontWeight: 700, fontSize: 15, color }}>
          {label}
        </span>
        <span style={{ fontSize: 11, color: '#94a3b8', background: '#f1f5f9', padding: '2px 8px', borderRadius: 99 }}>
          {kpi.sample_count} samples
        </span>
      </div>

      {/* Efficiency gauge */}
      <div style={{ display: 'flex', justifyContent: 'center' }}>
        <EfficiencyGauge score={kpi.efficiency_score} color={color} />
      </div>
      <div style={{ textAlign: 'center', fontSize: 11, color: '#64748b', marginTop: -6 }}>
        Efficiency Score
      </div>

      {/* Metrics grid */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '8px 12px', marginTop: 4 }}>
        <Metric label="Fan runtime" value={`${fmt(kpi.total_fan_runtime_minutes)} min`} />
        <Metric label="Temp exceedance" value={`${fmt(kpi.total_temp_exceedance_minutes)} min`} hot={kpi.total_temp_exceedance_minutes > 5} />
        <Metric label="Humidity exc." value={`${fmt(kpi.total_humidity_exceedance_minutes)} min`} />
        <Metric label="Avg response" value={kpi.avg_response_time_seconds != null ? `${fmt(kpi.avg_response_time_seconds)} s` : '—'} />
      </div>
    </div>
  );
}

function Metric({ label, value, hot }: { label: string; value: string; hot?: boolean }) {
  return (
    <div>
      <div style={{ fontSize: 10, color: '#94a3b8', textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: 2 }}>
        {label}
      </div>
      <div style={{ fontSize: 14, fontWeight: 700, color: hot ? '#dc2626' : 'var(--color-text-primary)' }}>
        {value}
      </div>
    </div>
  );
}

// ── Bar chart: side-by-side mode comparison ─────────────────────────────────
interface ComparisonBarChartProps {
  modes: ModeKPIs[];
}
function ComparisonBarChart({ modes }: ComparisonBarChartProps) {
  const data = [
    {
      metric: 'Fan Runtime (min)',
      ...Object.fromEntries(modes.map((m) => [m.mode, m.total_fan_runtime_minutes])),
    },
    {
      metric: 'Temp Exc. (min)',
      ...Object.fromEntries(modes.map((m) => [m.mode, m.total_temp_exceedance_minutes])),
    },
    {
      metric: 'Humidity Exc. (min)',
      ...Object.fromEntries(modes.map((m) => [m.mode, m.total_humidity_exceedance_minutes])),
    },
    {
      metric: 'Avg Response (s)',
      ...Object.fromEntries(modes.map((m) => [m.mode, m.avg_response_time_seconds ?? 0])),
    },
  ];

  return (
    <ResponsiveContainer width="100%" height={260}>
      <BarChart data={data} margin={{ top: 8, right: 16, left: 0, bottom: 8 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
        <XAxis dataKey="metric" tick={{ fontSize: 11 }} tickLine={false} />
        <YAxis tick={{ fontSize: 11 }} tickLine={false} />
        <Tooltip contentStyle={{ fontSize: 12 }} />
        <Legend wrapperStyle={{ fontSize: 12 }} />
        {modes.map((m) => (
          <Bar
            key={m.mode}
            dataKey={m.mode}
            name={MODE_LABELS[m.mode] ?? m.mode}
            fill={MODE_COLORS[m.mode] ?? '#64748b'}
            radius={[4, 4, 0, 0]}
          />
        ))}
      </BarChart>
    </ResponsiveContainer>
  );
}

// ── Time-series line chart ───────────────────────────────────────────────────
interface TimeSeriesChartProps {
  series: AnalyticsSnapshot[];
  metric: 'fan_runtime_seconds' | 'temp_exceedance_seconds' | 'humidity_exceedance_seconds';
  label: string;
  yUnit: string;
}
function TimeSeriesChart({ series, metric, label, yUnit }: TimeSeriesChartProps) {
  // Bucket into one point per minute — take last snapshot per (minute, mode)
  const buckets: Record<string, Record<string, number>> = {};
  for (const row of series) {
    const minute = row.captured_at.slice(0, 16); // "YYYY-MM-DDTHH:MM"
    const val = s2m(row[metric]);
    if (!buckets[minute]) buckets[minute] = {};
    buckets[minute][row.mode] = val;
  }

  const modes = Array.from(new Set(series.map((r) => r.mode)));
  const chartData = Object.entries(buckets)
    .sort(([a], [b]) => a.localeCompare(b))
    .map(([time, vals]) => ({
      time: time.slice(11), // "HH:MM"
      ...vals,
    }));

  if (chartData.length === 0) return null;

  // Thin out if too many points (> 60 → keep every Nth)
  const MAX_POINTS = 60;
  const step = Math.ceil(chartData.length / MAX_POINTS);
  const thinned = step > 1 ? chartData.filter((_, i) => i % step === 0) : chartData;

  return (
    <div>
      <div style={{ fontSize: 13, fontWeight: 600, color: 'var(--color-text-secondary)', marginBottom: 8 }}>
        {label} over time ({yUnit})
      </div>
      <ResponsiveContainer width="100%" height={180}>
        <LineChart data={thinned} margin={{ top: 4, right: 16, left: 0, bottom: 4 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
          <XAxis dataKey="time" tick={{ fontSize: 10 }} tickLine={false} interval="preserveStartEnd" />
          <YAxis tick={{ fontSize: 10 }} tickLine={false} />
          <Tooltip contentStyle={{ fontSize: 11 }} />
          <Legend wrapperStyle={{ fontSize: 11 }} />
          {modes.map((mode) => (
            <Line
              key={mode}
              type="monotone"
              dataKey={mode}
              name={MODE_LABELS[mode] ?? mode}
              stroke={MODE_COLORS[mode] ?? '#64748b'}
              dot={false}
              strokeWidth={2}
            />
          ))}
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}

// ── Efficiency score bar chart ───────────────────────────────────────────────
function EfficiencyChart({ modes }: { modes: ModeKPIs[] }) {
  const data = modes.map((m) => ({
    mode: MODE_LABELS[m.mode] ?? m.mode,
    score: m.efficiency_score,
    fill: MODE_COLORS[m.mode] ?? '#64748b',
  }));

  return (
    <ResponsiveContainer width="100%" height={160}>
      <BarChart data={data} layout="vertical" margin={{ top: 4, right: 40, left: 10, bottom: 4 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" horizontal={false} />
        <XAxis type="number" domain={[0, 100]} tick={{ fontSize: 11 }} tickLine={false} />
        <YAxis type="category" dataKey="mode" tick={{ fontSize: 13, fontWeight: 600 }} tickLine={false} width={80} />
        <Tooltip
          contentStyle={{ fontSize: 12 }}
          formatter={(v: number) => [`${v} / 100`, 'Efficiency']}
        />
        <ReferenceLine x={80} stroke="#16a34a" strokeDasharray="4 4" label={{ value: 'Good', fontSize: 10, fill: '#16a34a', position: 'top' }} />
        {data.map((d) => (
          <Bar key={d.mode} dataKey="score" fill={d.fill} radius={[0, 4, 4, 0]} barSize={28} />
        ))}
      </BarChart>
    </ResponsiveContainer>
  );
}

// ── Root export ─────────────────────────────────────────────────────────────
export interface ComparisonChartProps {
  modes: ModeKPIs[];
  timeSeries: AnalyticsSnapshot[];
}

export function ComparisonChart({ modes, timeSeries }: ComparisonChartProps) {
  if (modes.length === 0) {
    return (
      <div
        style={{
          padding: '40px 24px',
          textAlign: 'center',
          color: 'var(--color-text-muted)',
          fontStyle: 'italic',
          fontSize: 14,
          background: 'var(--color-bg)',
          borderRadius: 8,
        }}
      >
        No analytics data yet — the system needs a few minutes of readings in each mode.
        <br />
        <span style={{ fontSize: 12, marginTop: 6, display: 'block' }}>
          Switch between Reactive and Predictive modes in the Automation page to populate this view.
        </span>
      </div>
    );
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 28 }}>

      {/* KPI cards row */}
      <div style={{ display: 'flex', gap: 16, flexWrap: 'wrap' }}>
        {modes.map((m) => <KpiCard key={m.mode} kpi={m} />)}
      </div>

      {/* Efficiency score chart */}
      {modes.length > 1 && (
        <div>
          <div style={{ fontSize: 14, fontWeight: 700, color: 'var(--color-text-primary)', marginBottom: 10 }}>
            Efficiency Score Comparison
          </div>
          <EfficiencyChart modes={modes} />
          <div style={{ fontSize: 11, color: '#94a3b8', marginTop: 4 }}>
            Score = 100 − temp-exceedance penalty (0–50 pts) − response-time penalty (0–50 pts). Higher is better.
          </div>
        </div>
      )}

      {/* Side-by-side bar comparison */}
      <div>
        <div style={{ fontSize: 14, fontWeight: 700, color: 'var(--color-text-primary)', marginBottom: 10 }}>
          Cumulative Metric Comparison
        </div>
        <ComparisonBarChart modes={modes} />
      </div>

      {/* Time-series charts */}
      {timeSeries.length > 1 && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
          <div style={{ fontSize: 14, fontWeight: 700, color: 'var(--color-text-primary)' }}>
            Trends Over Time
          </div>
          <TimeSeriesChart
            series={timeSeries}
            metric="fan_runtime_seconds"
            label="Fan Runtime"
            yUnit="min"
          />
          <TimeSeriesChart
            series={timeSeries}
            metric="temp_exceedance_seconds"
            label="Temperature Exceedance"
            yUnit="min"
          />
          <TimeSeriesChart
            series={timeSeries}
            metric="humidity_exceedance_seconds"
            label="Humidity Exceedance"
            yUnit="min"
          />
        </div>
      )}
    </div>
  );
}
