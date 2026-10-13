import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ReferenceLine,
  ResponsiveContainer,
  Legend,
} from 'recharts';
import type { SensorReading } from '../../types';

interface LiveChartProps {
  readings: SensorReading[];
}

interface ChartDatum {
  time: string;
  temperature: number;
  humidity: number;
  data_source: string;
}

function formatTime(iso: string): string {
  return new Date(iso).toLocaleTimeString('en-GB', {
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
  });
}

const TEMP_WARN = 30;
const TEMP_MAX = 32;
const HUMIDITY_MAX = 85;

export function LiveChart({ readings }: LiveChartProps) {
  if (readings.length === 0) {
    return <div className="empty-state">No readings available to chart</div>;
  }

  const data: ChartDatum[] = readings.map((r) => ({
    time: formatTime(r.timestamp),
    temperature: r.temperature,
    humidity: r.humidity,
    data_source: r.data_source,
  }));

  return (
    <div>
      <ResponsiveContainer width="100%" height={320}>
        <LineChart data={data} margin={{ top: 8, right: 16, left: 0, bottom: 8 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
          <XAxis
            dataKey="time"
            tick={{ fontSize: 11 }}
            tickLine={false}
            interval="preserveStartEnd"
          />
          {/* Left Y-axis — Temperature */}
          <YAxis
            yAxisId="temp"
            orientation="left"
            domain={['auto', 'auto']}
            tick={{ fontSize: 11 }}
            tickLine={false}
            label={{ value: '°C', angle: -90, position: 'insideLeft', offset: 10, style: { fontSize: 11 } }}
          />
          {/* Right Y-axis — Humidity */}
          <YAxis
            yAxisId="hum"
            orientation="right"
            domain={[0, 100]}
            tick={{ fontSize: 11 }}
            tickLine={false}
            label={{ value: '%', angle: 90, position: 'insideRight', offset: 10, style: { fontSize: 11 } }}
          />
          <Tooltip
            contentStyle={{ fontSize: 12 }}
            formatter={(value: number, name: string) => {
              if (name === 'Temperature') return [`${value.toFixed(1)}°C`, name];
              if (name === 'Humidity') return [`${value.toFixed(1)}%`, name];
              return [value, name];
            }}
          />
          <Legend wrapperStyle={{ fontSize: 12 }} />

          {/* Temperature threshold reference lines */}
          <ReferenceLine
            yAxisId="temp"
            y={TEMP_WARN}
            stroke="#f59e0b"
            strokeDasharray="6 3"
            label={{ value: `Warn ${TEMP_WARN}°C`, position: 'right', fontSize: 11, fill: '#f59e0b' }}
          />
          <ReferenceLine
            yAxisId="temp"
            y={TEMP_MAX}
            stroke="#dc2626"
            strokeDasharray="6 3"
            label={{ value: `Max ${TEMP_MAX}°C`, position: 'right', fontSize: 11, fill: '#dc2626' }}
          />

          {/* Humidity threshold reference line */}
          <ReferenceLine
            yAxisId="hum"
            y={HUMIDITY_MAX}
            stroke="#2563eb"
            strokeDasharray="6 3"
            label={{ value: `Hum ${HUMIDITY_MAX}%`, position: 'left', fontSize: 11, fill: '#2563eb' }}
          />

          <Line
            yAxisId="temp"
            type="monotone"
            dataKey="temperature"
            name="Temperature"
            stroke="#dc2626"
            strokeWidth={2}
            dot={false}
            activeDot={{ r: 4 }}
          />
          <Line
            yAxisId="hum"
            type="monotone"
            dataKey="humidity"
            name="Humidity"
            stroke="#2563eb"
            strokeWidth={2}
            dot={false}
            activeDot={{ r: 4 }}
          />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
