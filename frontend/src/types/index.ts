// TypeScript interfaces matching backend Pydantic schemas

export interface SensorReading {
  id: number;
  timestamp: string;
  greenhouse_id: string;
  temperature: number;
  humidity: number;
  data_source: 'real' | 'simulated';
  sensor_status: 'ok' | 'error' | 'stale';
}

export interface ForecastPoint {
  horizon_minutes: number;
  predicted_temperature: number;
  predicted_humidity: number;
  confidence: number;
}

export interface ModelMetrics {
  horizon_minutes: number;
  temp_mae: number;
  temp_rmse: number;
  humidity_mae: number;
  humidity_rmse: number;
}

export interface ForecastRecord {
  id: number;
  timestamp: string;
  greenhouse_id: string;
  model_version: string;
  data_is_synthetic: boolean;
  forecasts: ForecastPoint[];
  metrics: ModelMetrics[];
}

export type RiskLevel = 'low' | 'medium' | 'high' | 'critical';
export type AlertType =
  | 'overheating'
  | 'high_humidity'
  | 'sensor_failure'
  | 'stale_data'
  | 'predicted_overheating'
  | 'predicted_high_humidity';

export interface Alert {
  id: number;
  timestamp: string;
  greenhouse_id: string;
  alert_type: AlertType;
  risk_level: RiskLevel;
  message: string;
  resolved_at: string | null;
  is_active: boolean;
}

export type ControlMode = 'reactive' | 'predictive' | 'manual';
export type FanState = 'on' | 'off';
export type ManualAction = 'fan_on' | 'fan_off' | 'noop';

export interface ControlState {
  mode: ControlMode;
  fan_state: FanState;
  last_action: string;
  last_action_reason: string;
  manual_override_active: boolean;
  manual_override_expires_at: string | null;
  updated_at: string;
}

export interface ControlModeRequest {
  mode: ControlMode;
}

export interface ManualOverrideRequest {
  action: ManualAction;
  duration_seconds?: number;
}

export interface AnalyticsSnapshot {
  id: number;
  greenhouse_id: string;
  captured_at: string;
  mode: ControlMode;
  fan_runtime_seconds: number;
  temp_exceedance_seconds: number;
  humidity_exceedance_seconds: number;
  avg_response_time_seconds: number | null;
}

export interface HealthResponse {
  status: 'ok' | 'degraded' | 'error';
  version: string;
  simulation_mode: boolean;
  db_ok: boolean;
  scheduler_ok: boolean;
}

export interface PredictionsResponse {
  latest: ForecastRecord | null;
  data_is_synthetic: boolean;
  model_version: string;
}

export interface DeviceStatus {
  greenhouse_id: string;
  connection_status: 'connected' | 'disconnected' | 'simulated';
  simulation_mode: boolean;
  serial_port: string | null;
  last_reading_at: string | null;
  last_error: string | null;
  firmware_version: string | null;
  uptime_seconds: number | null;
}
