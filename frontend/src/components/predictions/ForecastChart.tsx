import {
  ComposedChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ReferenceLine,
  ResponsiveContainer,
  Legend,
  Scatter,
} from 'recharts';
import type { ForecastRecord, SensorReading } from '../../types';

interface ForecastChartProps {
  history: SensorReading[];
  forecast: ForecastRecord | null;
  dataIsSynthetic: boolean;
}

interface ChartPoint {
  label: string;
  actualTemp?: number;
  actualHum?: number;
  forecastTemp?: number;
  forecastHum?: number;
  isForecast: boolean;
}

const TEMP_MAX = 32;
const HUMIDITY_MAX = 85;

export function ForecastChart({ history, forecast, dataIsSynthetic }: ForecastChartProps) {
  // Build combined timeline: last 30 historical points + forecast points
  const recent = history.slice(-30);

  const histPoints: ChartPoint[] = recent.map((r) => ({
    label: new Date(r.timestamp).toLocaleTimeString('en-GB', {
      hour: '2-digit',
      minute: '2-digit',
    }),
    actualTemp: r.temperature,
    actualHum: r.humidity,
    isForecast: false,
  }));

  const forecastPoints: ChartPoint[] = (forecast?.forecasts ?? []).map((f) => ({
    label: `+${f.horizon_minutes}m`,
    forecastTemp: f.predicted_temperature,
    forecastHum: f.predicted_humidity,
    isForecast: true,
  }));

  const data: ChartPoint[] = [...histPoints, ...forecastPoints];

  const metrics = forecast?.metrics ?? [];

  return (
    <div>
      {dataIsSynthetic && (
        <div style={{ marginBottom: 12 }}>
          <span className="badge badge-unvalidated">SYNTHETIC / UNVALIDATED</span>
          <span style={{ fontSize: 11, color: 'var(--color-text-muted)', marginLeft: 8 }}>
            Model accuracy has not been validated on real sensor data.
          </span>
        </div>
      )}

      <ResponsiveContainer width="100%" height={320}>
        <ComposedChart data={data} margin={{ top: 8, right: 16, left: 0, bottom: 8 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
          <XAxis dataKey="label" tick={{ fontSize: 11 }} tickLine={false} />
          <YAxis
            yAxisId="temp"
            orientation="left"
            domain={['auto', 'auto']}
            tick={{ fontSize: 11 }}
            tickLine={false}
            label={{ value: '°C', angle: -90, position: 'insideLeft', offset: 10, style: { fontSize: 11 } }}
          />
          <YAxis
            yAxisId="hum"
            orientation="right"
            domain={[0, 100]}
            tick={{ fontSize: 11 }}
            tickLine={false}
            label={{ value: '%', angle: 90, position: 'insideRight', offset: 10, style: { fontSize: 11 } }}
          />
          <Tooltip contentStyle={{ fontSize: 12 }} />
          <Legend wrapperStyle={{ fontSize: 12 }} />

          {/* Temperature threshold reference lines */}
          <ReferenceLine
            yAxisId="temp"
            y={TEMP_MAX}
            stroke="#dc2626"
            strokeDasharray="6 3"
            label={{ value: `Max ${TEMP_MAX}°C`, position: 'right', fontSize: 11, fill: '#dc2626' }}
          />

          {/* Humidity threshold */}
          <ReferenceLine
            yAxisId="hum"
            y={HUMIDITY_MAX}
            stroke="#2563eb"
            strokeDasharray="6 3"
            label={{ value: `Max ${HUMIDITY_MAX}%`, position: 'left', fontSize: 11, fill: '#2563eb' }}
          />

          {/* Actual lines */}
          <Line
            yAxisId="temp"
            type="monotone"
            dataKey="actualTemp"
            name="Actual Temp"
            stroke="#dc2626"
            strokeWidth={2}
            dot={false}
            connectNulls={false}
          />
          <Line
            yAxisId="hum"
            type="monotone"
            dataKey="actualHum"
            name="Actual Humidity"
            stroke="#2563eb"
            strokeWidth={2}
            dot={false}
            connectNulls={false}
          />

          {/* Forecast scatter points */}
          <Scatter
            yAxisId="temp"
            dataKey="forecastTemp"
            name="Forecast Temp"
            fill="#f97316"
            shape="diamond"
          />
          <Scatter
            yAxisId="hum"
            dataKey="forecastHum"
            name="Forecast Humidity"
            fill="#7c3aed"
            shape="diamond"
          />
        </ComposedChart>
      </ResponsiveContainer>

      {/* Metrics table */}
      {metrics.length > 0 && (
        <div style={{ marginTop: 20 }}>
          <div className="card-title">Model Performance (per horizon)</div>
          <table
            style={{
              width: '100%',
              borderCollapse: 'collapse',
              fontSize: 12,
              marginTop: 8,
            }}
          >
            <thead>
              <tr style={{ background: 'var(--color-bg)' }}>
                {(['Horizon', 'Temp MAE', 'Temp RMSE', 'Hum MAE', 'Hum RMSE'] as const).map((h) => (
                  <th
                    key={h}
                    style={{
                      padding: '6px 10px',
                      textAlign: 'left',
                      fontWeight: 600,
                      color: 'var(--color-text-secondary)',
                      borderBottom: '1px solid var(--color-border)',
                    }}
                  >
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {metrics.map((m) => (
                <tr key={m.horizon_minutes} style={{ borderBottom: '1px solid var(--color-border)' }}>
                  <td style={{ padding: '6px 10px' }}>+{m.horizon_minutes} min</td>
                  <td style={{ padding: '6px 10px' }}>{m.temp_mae.toFixed(2)}°C</td>
                  <td style={{ padding: '6px 10px' }}>{m.temp_rmse.toFixed(2)}°C</td>
                  <td style={{ padding: '6px 10px' }}>{m.humidity_mae.toFixed(2)}%</td>
                  <td style={{ padding: '6px 10px' }}>{m.humidity_rmse.toFixed(2)}%</td>
                </tr>
              ))}
            </tbody>
          </table>
          {dataIsSynthetic && (
            <div style={{ fontSize: 11, color: 'var(--color-text-muted)', marginTop: 6 }}>
              * Metrics computed on synthetic data — not validated on real sensor readings.
            </div>
          )}
        </div>
      )}
    </div>
  );
}
