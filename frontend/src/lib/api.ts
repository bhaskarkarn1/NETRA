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
  DisruptionActionFeed,
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

export interface PropagationResult {
  iterations: number;
  nodes_updated: number;
  max_risk_delta: number;
  high_risk_nodes: Array<{
    id: string;
    label: string;
    type: string;
    original_risk: number;
    propagated_risk: number;
    delta: number;
  }>;
}

export async function propagateRisk(iterations = 5, decay = 0.6): Promise<PropagationResult> {
  return request<PropagationResult>(
    `/api/graph/propagate-risk?iterations=${iterations}&decay=${decay}`,
    { method: "POST" }
  );
}

export interface CommunityData {
  community_id: number;
  size: number;
  members: Array<{ id: string; label: string; type: string; risk_score: number }>;
  risk_score: number;
  is_syndicate: boolean;
}

export interface CommunitiesResponse {
  total_communities: number;
  syndicates_detected: number;
  communities: CommunityData[];
}

export async function getCommunities(): Promise<CommunitiesResponse> {
  return request<CommunitiesResponse>("/api/graph/communities");
}

export interface InterventionImpact {
  target_node_id: string;
  target_label: string;
  target_type: string;
  downstream_affected: number;
  estimated_risk_reduction: number;
  connected_cases: Array<{ id: string; label: string; type: string; risk_score: number }>;
  affected_entities: Array<{ id: string; label: string; type: string; risk_score: number }>;
  intervention_priority: string;
}

export async function getIntervention(nodeId: string): Promise<InterventionImpact> {
  return request<InterventionImpact>(`/api/graph/intervention/${nodeId}`);
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

// =================== Geospatial API ===================

export interface GeoPoint {
  lat: number;
  lng: number;
  label: string;
  state: string;
  is_hotspot: boolean;
  risk_score: number;
  case_count: number;
  scam_types: string[];
}

export interface GeospatialData {
  points: GeoPoint[];
  total_locations: number;
  hotspot_count: number;
}

export async function getGeospatialData(): Promise<GeospatialData> {
  return request<GeospatialData>("/api/dashboard/geospatial");
}

// =================== Alert API ===================

export interface AlertData {
  case_id: string;
  alert_type: string;
  generated_text: string;
  sections: Array<{ title: string; content: string }>;
  recommended_actions: string[];
  severity: string;
  generated_at: string;
}

export async function getCaseAlert(caseId: string, alertType = "I4C_ALERT"): Promise<AlertData> {
  return request<AlertData>(`/api/detect/${caseId}/alert?alert_type=${alertType}`);
}

// =================== Config API ===================

export async function getMapboxToken(): Promise<string> {
  const data = await request<{ token: string }>("/api/config/mapbox-token");
  return data.token;
}

// =================== Disruption API ===================

export interface DisruptionResponse {
  id: string;
  action_type: string;
  target_entity: string;
  target_institution: string;
  status: string;
  confidence: number;
  payload: Record<string, unknown>;
  reasoning: string;
  created_at: string;
}

export async function triggerBankFreeze(data: {
  case_id?: string;
  target_entity: string;
  entity_type: string;
  confidence: number;
}): Promise<DisruptionResponse> {
  return request<DisruptionResponse>("/api/disrupt/bank-freeze", {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export async function triggerTelecomBlock(data: {
  case_id?: string;
  target_entity: string;
  confidence: number;
}): Promise<DisruptionResponse> {
  return request<DisruptionResponse>("/api/disrupt/telecom-block", {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export async function getDisruptionActions(
  limit = 20
): Promise<DisruptionActionFeed[]> {
  return request<DisruptionActionFeed[]>(
    `/api/disrupt/actions?limit=${limit}`
  );
}

