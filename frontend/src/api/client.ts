import type {
  Alert,
  AdvisoryResponse,
  AnalyticsSnapshot,
  AnalyticsSummaryResponse,
  ControlModeRequest,
  ControlState,
  DeviceStatus,
  HealthResponse,
  ManualOverrideRequest,
  PredictionsResponse,
  SensorReading,
} from '../types';

const BASE_URL: string =
  (import.meta.env['VITE_API_URL'] as string | undefined) ?? 'http://localhost:8000';

async function apiFetch<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE_URL}${path}`, {
    headers: { 'Content-Type': 'application/json' },
    ...options,
  });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(`API ${path} → ${res.status}: ${text}`);
  }
  return res.json() as Promise<T>;
}

export function getHealth(): Promise<HealthResponse> {
  return apiFetch<HealthResponse>('/api/health');
}

export function getLatestReading(): Promise<SensorReading> {
  return apiFetch<SensorReading>('/api/readings/latest');
}

export function getReadingHistory(limit = 100): Promise<SensorReading[]> {
  return apiFetch<SensorReading[]>(`/api/readings/history?limit=${limit}`);
}

export function getPredictions(): Promise<PredictionsResponse> {
  return apiFetch<PredictionsResponse>('/api/predictions');
}

export function getAlerts(activeOnly = false): Promise<Alert[]> {
  return apiFetch<Alert[]>(`/api/alerts?active_only=${activeOnly}`);
}

export function getDeviceStatus(): Promise<DeviceStatus> {
  return apiFetch<DeviceStatus>('/api/devices/status');
}

export function getControlMode(): Promise<ControlState> {
  return apiFetch<ControlState>('/api/control/mode');
}

export function setControlMode(req: ControlModeRequest): Promise<ControlState> {
  return apiFetch<ControlState>('/api/control/mode', {
    method: 'POST',
    body: JSON.stringify(req),
  });
}

export function sendManualOverride(req: ManualOverrideRequest): Promise<ControlState> {
  return apiFetch<ControlState>('/api/control/manual-override', {
    method: 'POST',
    body: JSON.stringify(req),
  });
}

export function getAnalyticsComparison(hours = 24): Promise<AnalyticsSnapshot[]> {
  return apiFetch<AnalyticsSnapshot[]>(`/api/analytics/comparison?hours=${hours}`);
}

export function getAnalyticsSummary(hours = 24): Promise<AnalyticsSummaryResponse> {
  return apiFetch<AnalyticsSummaryResponse>(`/api/analytics/summary?hours=${hours}`);
}

export function getAdvisory(): Promise<AdvisoryResponse> {
  return apiFetch<AdvisoryResponse>('/api/advisory');
}
