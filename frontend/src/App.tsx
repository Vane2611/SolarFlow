import { BrowserRouter, Routes, Route, Navigate, useLocation } from 'react-router-dom';
import { Sidebar } from './components/layout/Sidebar';
import { Header } from './components/layout/Header';
import { Overview } from './pages/Overview';
import { Monitoring } from './pages/Monitoring';
import { Predictions } from './pages/Predictions';
import { Alerts } from './pages/Alerts';
import { Automation } from './pages/Automation';
import { Analytics } from './pages/Analytics';
import { DeviceHealthPage } from './pages/DeviceHealth';
import { usePolling } from './hooks/usePolling';
import { getHealth, getDeviceStatus } from './api/client';
import { useCallback } from 'react';

const PAGE_TITLES: Record<string, string> = {
  '/': 'Overview',
  '/monitoring': 'Live Monitoring',
  '/predictions': 'Predictions',
  '/alerts': 'Alerts',
  '/automation': 'Automation',
  '/analytics': 'Analytics',
  '/devices': 'Device Health',
};

function AppLayout() {
  const location = useLocation();
  const title = PAGE_TITLES[location.pathname] ?? 'SolarFlow';

  const healthFetcher = useCallback(() => getHealth(), []);
  const deviceFetcher = useCallback(() => getDeviceStatus(), []);

  const { data: health, error: healthError, lastUpdated } = usePolling(healthFetcher, 10_000);
  const { data: device } = usePolling(deviceFetcher, 15_000);

  return (
    <div className="app-shell">
      <Sidebar />
      <div className="main-content">
        <Header
          title={title}
          lastUpdated={lastUpdated}
          simulationMode={health?.simulation_mode ?? device?.simulation_mode ?? false}
          connectionStatus={device?.connection_status ?? null}
          error={healthError}
        />
        <main className="page-content">
          <Routes>
            <Route path="/" element={<Overview />} />
            <Route path="/monitoring" element={<Monitoring />} />
            <Route path="/predictions" element={<Predictions />} />
            <Route path="/alerts" element={<Alerts />} />
            <Route path="/automation" element={<Automation />} />
            <Route path="/analytics" element={<Analytics />} />
            <Route path="/devices" element={<DeviceHealthPage />} />
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </main>
      </div>
    </div>
  );
}

function App() {
  return (
    <BrowserRouter>
      <AppLayout />
    </BrowserRouter>
  );
}

export default App;
