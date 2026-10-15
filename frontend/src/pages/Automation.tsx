import { useCallback, useState } from 'react';
import { usePolling } from '../hooks/usePolling';
import { getControlMode, getLatestReading } from '../api/client';
import { ControlPanel } from '../components/automation/ControlPanel';
import type { ControlState, SensorReading } from '../types';

export function Automation() {
  // Local state so we can do an immediate re-fetch after mutations
  const [controlState, setControlState] = useState<ControlState | null>(null);

  const fetcher = useCallback(() => getControlMode(), []);
  const readingFetcher = useCallback(() => getLatestReading(), []);

  const { error, loading, lastUpdated } = usePolling(fetcher, 5_000, setControlState);
  const { data: latestReading } = usePolling<SensorReading>(readingFetcher, 5_000);

  // Immediate refresh — called by ControlPanel after every mutation
  const refresh = useCallback(async () => {
    try {
      const fresh = await getControlMode();
      setControlState(fresh);
    } catch {
      // polling will recover on next tick
    }
  }, []);

  return (
    <div>
      {error && <div className="error-state" style={{ marginBottom: 16 }}>{error}</div>}
      {lastUpdated && (
        <div style={{ fontSize: 12, color: 'var(--color-text-muted)', marginBottom: 16 }}>
          Last updated: {lastUpdated.toLocaleTimeString('en-GB')}
        </div>
      )}
      <ControlPanel
        controlState={controlState}
        loading={loading}
        onRefresh={refresh}
        latestReading={latestReading}
      />
    </div>
  );
}
