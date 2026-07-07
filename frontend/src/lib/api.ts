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

// =================== Config API ===================

export async function getMapboxToken(): Promise<string> {
  const data = await request<{ token: string }>("/api/config/mapbox-token");
  return data.token;
}
