/**
 * NETRA — API Client
 *
 * Centralized API client for all backend communication.
 * Every API call goes through this module — no direct fetch() calls elsewhere.
 */

import type {
  DetectRequest,
  DetectResponse,
  CaseSummary,
  NetworkResponse,
  SearchResult,
  ScenarioInfo,
  SimulationStartResponse,
  TurnResponse,
  DebriefResponse,
  DashboardMetrics,
  ThreatFeedItem,
  IntelligenceResponse,
} from "./types";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

class ApiError extends Error {
  status: number;
  detail: string;

  constructor(status: number, detail: string) {
    super(`API Error ${status}: ${detail}`);
    this.status = status;
    this.detail = detail;
  }
}

async function request<T>(
  endpoint: string,
  options: RequestInit = {}
): Promise<T> {
  const url = `${API_BASE}${endpoint}`;

  const response = await fetch(url, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...options.headers,
    },
  });

  if (!response.ok) {
    let detail = `HTTP ${response.status}`;
    try {
      const errorData = await response.json();
      detail = errorData.detail || detail;
    } catch {
      // ignore parse errors
    }
    throw new ApiError(response.status, detail);
  }

  return response.json();
}

// =================== Detect API ===================

export async function analyzeText(data: DetectRequest): Promise<DetectResponse> {
  return request<DetectResponse>("/api/detect", {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export async function analyzeImage(
  imageBase64: string,
  mimeType: string = "image/jpeg"
): Promise<{
  extracted_text: string;
  detection_result: DetectResponse | null;
  ocr_confidence: number;
  image_description: string;
}> {
  return request("/api/detect/image", {
    method: "POST",
    body: JSON.stringify({
      image_base64: imageBase64,
      mime_type: mimeType,
      input_type: "screenshot",
    }),
  });
}

export async function analyzeCounterfeit(
  imageBase64: string,
  mimeType: string = "image/jpeg",
  denomination?: string
): Promise<{
  verdict: string;
  confidence: number;
  denomination_detected: string | null;
  security_features: Array<{
    feature_name: string;
    status: string;
    confidence: number;
    description: string;
  }>;
  overall_assessment: string;
  rbi_guidelines: string;
  evidence_hash: string;
  model_used: string;
  processing_time_ms: number;
}> {
  return request("/api/detect/counterfeit", {
    method: "POST",
    body: JSON.stringify({
      image_base64: imageBase64,
      mime_type: mimeType,
      denomination: denomination || null,
    }),
  });
}

export async function getCase(caseId: string): Promise<DetectResponse> {
  return request<DetectResponse>(`/api/detect/${caseId}`);
}

export async function getRecentCases(limit = 20): Promise<CaseSummary[]> {
  return request<CaseSummary[]>(`/api/detect/recent/list?limit=${limit}`);
}

export function getDossierUrl(caseId: string): string {
  return `${API_BASE}/api/detect/${caseId}/dossier`;
}

export async function getIntelligence(caseId: string): Promise<IntelligenceResponse> {
  return request<IntelligenceResponse>(`/api/detect/${caseId}/intelligence`);
}

// =================== Graph API ===================

export async function searchNodes(query: string): Promise<SearchResult[]> {
  return request<SearchResult[]>(`/api/graph/search?query=${encodeURIComponent(query)}`, {
    method: "POST",
  });
}

export async function getNetwork(
  nodeId: string,
  depth = 2
): Promise<NetworkResponse> {
  return request<NetworkResponse>(
    `/api/graph/network/${nodeId}?depth=${depth}`
  );
}

export async function getNodeDetail(nodeId: string): Promise<SearchResult> {
  return request<SearchResult>(`/api/graph/node/${nodeId}`);
}

export async function getRecentEntities(limit = 20): Promise<SearchResult[]> {
  return request<SearchResult[]>(`/api/graph/recent?limit=${limit}`);
}

export async function getGraphStats(): Promise<{
  total_nodes: number;
  total_edges: number;
  node_type_counts: Record<string, number>;
  high_risk_entities: number;
  syndicate_clusters: number;
}> {
  return request(`/api/graph/stats`);
}

// =================== Simulate API ===================

export async function getScenarios(): Promise<ScenarioInfo[]> {
  return request<ScenarioInfo[]>("/api/simulate/scenarios");
}

export async function startSimulation(
  scenarioType: string,
  sessionId?: string
): Promise<SimulationStartResponse> {
  return request<SimulationStartResponse>("/api/simulate/start", {
    method: "POST",
    body: JSON.stringify({
      scenario_type: scenarioType,
      user_session_id: sessionId,
    }),
  });
}

export async function respondToSimulation(
  simulationId: string,
  message: string
): Promise<TurnResponse> {
  return request<TurnResponse>(`/api/simulate/${simulationId}/respond`, {
    method: "POST",
    body: JSON.stringify({ message }),
  });
}

export async function getDebrief(
  simulationId: string
): Promise<DebriefResponse> {
  return request<DebriefResponse>(`/api/simulate/${simulationId}/debrief`);
}

// =================== Dashboard API ===================

export async function getDashboardMetrics(): Promise<DashboardMetrics> {
  return request<DashboardMetrics>("/api/dashboard/metrics");
}

export async function getThreatFeed(limit = 20): Promise<ThreatFeedItem[]> {
  return request<ThreatFeedItem[]>(`/api/dashboard/threat-feed?limit=${limit}`);
}

export interface ChartDataPoint {
  label: string;
  value: number;
  color: string | null;
}

export interface DailyTrend {
  date: string;
  cases: number;
  scams: number;
}

export interface AnalyticsData {
  scam_type_distribution: ChartDataPoint[];
  risk_level_breakdown: ChartDataPoint[];
  daily_trend: DailyTrend[];
  entity_type_breakdown: ChartDataPoint[];
  top_entities: Array<{ label: string; type: string; risk_score: number }>;
}

export async function getAnalytics(): Promise<AnalyticsData> {
  return request<AnalyticsData>("/api/dashboard/analytics");
}

// =================== Config API ===================

export async function getMapboxToken(): Promise<string> {
  const data = await request<{ token: string }>("/api/config/mapbox-token");
  return data.token;
}
