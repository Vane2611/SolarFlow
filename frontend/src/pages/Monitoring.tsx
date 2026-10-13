import { useCallback, useState } from 'react';
import { usePolling } from '../hooks/usePolling';
import { getReadingHistory } from '../api/client';
import { LiveChart } from '../components/monitoring/LiveChart';
import type { SensorReading } from '../types';

const PAGE_SIZE = 20;

export function Monitoring() {
  const [page, setPage] = useState(0);

  const fetcher = useCallback(() => getReadingHistory(200), []);
  const { data: readings, loading, error, lastUpdated } = usePolling(fetcher, 5_000);

  const allReadings: SensorReading[] = readings ?? [];
  const totalPages = Math.max(1, Math.ceil(allReadings.length / PAGE_SIZE));
  const pageSlice = allReadings.slice(page * PAGE_SIZE, (page + 1) * PAGE_SIZE);

  return (
    <div>
      {error && <div className="error-state" style={{ marginBottom: 16 }}>{error}</div>}

      <div className="card" style={{ marginBottom: 20 }}>
        <div className="card-title">Temperature &amp; Humidity — Last 200 Readings</div>
        {loading && allReadings.length === 0 ? (
          <div className="loading-state">Loading chart data…</div>
        ) : (
          <LiveChart readings={allReadings} />
        )}
        {lastUpdated && (
          <div style={{ fontSize: 11, color: 'var(--color-text-muted)', marginTop: 8 }}>
            Updated: {lastUpdated.toLocaleTimeString('en-GB')}
          </div>
        )}
      </div>

      {/* Reading table */}
      <div className="card">
        <div
          style={{
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
            marginBottom: 12,
          }}
        >
          <div className="card-title" style={{ margin: 0 }}>
            Sensor Readings
          </div>
          <span style={{ fontSize: 12, color: 'var(--color-text-muted)' }}>
            {allReadings.length} total
          </span>
        </div>

        <div style={{ overflowX: 'auto' }}>
          <table
            style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}
          >
            <thead>
              <tr style={{ background: 'var(--color-bg)' }}>
                {['Timestamp', 'Temperature', 'Humidity', 'Source', 'Status'].map((h) => (
                  <th
                    key={h}
                    style={{
                      padding: '8px 12px',
                      textAlign: 'left',
                      fontWeight: 600,
                      color: 'var(--color-text-secondary)',
                      borderBottom: '1px solid var(--color-border)',
                      whiteSpace: 'nowrap',
                    }}
                  >
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {pageSlice.map((r) => (
                <tr
                  key={r.id}
                  style={{ borderBottom: '1px solid var(--color-border)' }}
                >
                  <td style={{ padding: '8px 12px', whiteSpace: 'nowrap' }}>
                    {new Date(r.timestamp).toLocaleString('en-GB')}
                  </td>
                  <td
                    style={{
                      padding: '8px 12px',
                      fontWeight: 600,
                      color:
                        r.temperature >= 30
                          ? 'var(--color-danger)'
                          : r.temperature >= 28
                          ? 'var(--color-warning)'
                          : 'var(--color-success)',
                    }}
                  >
                    {r.temperature.toFixed(1)}°C
                  </td>
                  <td
                    style={{
                      padding: '8px 12px',
                      color: r.humidity > 85 ? 'var(--color-danger)' : undefined,
                    }}
                  >
                    {r.humidity.toFixed(1)}%
                  </td>
                  <td style={{ padding: '8px 12px' }}>
                    <span className={`badge badge-${r.data_source === 'simulated' ? 'simulated' : 'live'}`}>
                      {r.data_source}
                    </span>
                  </td>
                  <td style={{ padding: '8px 12px' }}>
                    <span
                      style={{
                        fontSize: 12,
                        color:
                          r.sensor_status === 'ok'
                            ? 'var(--color-success)'
                            : 'var(--color-danger)',
                      }}
                    >
                      {r.sensor_status}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        {/* Pagination */}
        {totalPages > 1 && (
          <div
            style={{
              display: 'flex',
              justifyContent: 'center',
              gap: 8,
              marginTop: 16,
            }}
          >
            <button
              onClick={() => setPage((p) => Math.max(0, p - 1))}
              disabled={page === 0}
              style={{
                padding: '6px 14px',
                borderRadius: 6,
                border: '1px solid var(--color-border)',
                background: 'var(--color-surface)',
                cursor: page === 0 ? 'not-allowed' : 'pointer',
                opacity: page === 0 ? 0.5 : 1,
              }}
            >
              Previous
            </button>
            <span style={{ padding: '6px 12px', fontSize: 13, color: 'var(--color-text-secondary)' }}>
              {page + 1} / {totalPages}
            </span>
            <button
              onClick={() => setPage((p) => Math.min(totalPages - 1, p + 1))}
              disabled={page >= totalPages - 1}
              style={{
                padding: '6px 14px',
                borderRadius: 6,
                border: '1px solid var(--color-border)',
                background: 'var(--color-surface)',
                cursor: page >= totalPages - 1 ? 'not-allowed' : 'pointer',
                opacity: page >= totalPages - 1 ? 0.5 : 1,
              }}
            >
              Next
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
