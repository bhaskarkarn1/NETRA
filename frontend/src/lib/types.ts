/**
 * NETRA — Shared TypeScript Types
 *
 * These types mirror the backend Pydantic schemas exactly.
 * All data flows through these types — no `any` types in the codebase.
 */

// =================== Detect ===================

export interface DetectRequest {
  text: string;
  input_type: "text" | "transcript" | "url";
}

export interface TacticDetected {
  name: string;
  description: string;
  confidence: number;
}

export interface LegalSection {
  code: string;
  law: string;
  section: string;
  title: string;
  punishment: string | null;
}

export interface KillChainStage {
  stage: string;
  stage_name: string;
  detected: boolean;
  evidence: string | null;
  severity: "critical" | "high" | "medium" | "low" | "none";
  confidence?: number;
  tactics?: string[];
}

export interface RelatedCase {
  id: string;
  scam_type: string | null;
  confidence: number;
  similarity_score: number;
  similarity_reason: string;
  input_preview: string;
  created_at: string;
}

export interface IntelligenceResponse {
  case_id: string;
  related_cases: RelatedCase[];
  entity_overlaps: Record<string, unknown>[];
  syndicate_indicators: string[];
  total_linked_cases: number;
}

export interface EntityInfo {
  entity_type: string;
  value: string;
  confidence: number;
  source: "regex" | "llm";
}

export interface GraphIntel {
  nodes_created: number;
  edges_created: number;
  nodes_linked: number;
  entities_extracted: EntityInfo[];
}

export interface Recommendation {
  action: string;
  target: string;
  expected_impact: number;
  urgency: "immediate" | "within_1h" | "within_24h";
  reasoning: string;
  action_type: "bank_freeze" | "telecom_block" | "file_fir" | "general";
}

export interface ConfidenceBreakdown {
  llm_confidence: number;
  evidence_quality: number;
  pattern_match: number;
  data_completeness: number;
  overall: number;
}

export interface DetectResponse {
  id: string;
  scam_type: string | null;
  confidence: number;
  risk_level: "critical" | "high" | "medium" | "low" | "unknown";
  ai_reasoning: string;
  tactics_detected: TacticDetected[];
  legal_sections: LegalSection[];
  kill_chain: KillChainStage[];
  victim_vulnerability_score: number;
  victim_vulnerability_factors: string[];
  evidence_hash: string;
  language: string;
  model_used: string;
  processing_time_ms: number;
  graph_intel: GraphIntel | null;
  recommendations: Recommendation[];
  confidence_breakdown: ConfidenceBreakdown | null;
}

export interface CaseSummary {
  id: string;
  scam_type: string | null;
  confidence: number;
  risk_level: string;
  input_preview: string;
  created_at: string;
}

// =================== Graph ===================

export interface GraphNode {
  id: string;
  node_type: string;  // Flexible — includes phone, bank_account, upi_id, victim, location, case, suspect, organization, email, url, amount, identity_doc, designation
  label: string;
  properties: Record<string, unknown>;
  risk_score: number | null;
  data_source: "seed" | "case_extracted" | "ncrb_reference";
  first_seen: string | null;
  last_seen: string | null;
}

export interface GraphEdge {
  id: string;
  source_id: string;
  target_id: string;
  edge_type: string;  // Flexible — includes called, transferred, reported, linked_to, located_at, used_in, mentioned_in, impersonated_in, demanded_in, claimed_in
  properties: Record<string, unknown>;
  weight: number;
}

export interface NetworkResponse {
  nodes: GraphNode[];
  edges: GraphEdge[];
  center_node_id: string;
  total_nodes: number;
  total_edges: number;
}

export interface SearchResult {
  id: string;
  node_type: string;
  label: string;
  risk_score: number | null;
  data_source: "seed" | "case_extracted" | "ncrb_reference";
}

// =================== Simulate ===================

export interface ScenarioInfo {
  name: string;
  category: string;
  description: string | null;
  prevalence: string | null;
}

export interface TurnAnalysis {
  tactic_detected: string | null;
  tactic_description: string | null;
  confidence: number;
  risk_level: "low" | "medium" | "high" | "critical";
  explanation: string;
}

export interface TurnResponse {
  turn_number: number;
  scammer_message: string;
  analysis: TurnAnalysis;
  simulation_status: "active" | "intervened" | "completed";
  intervention_triggered: boolean;
}

export interface SimulationStartResponse {
  simulation_id: string;
  scenario_type: string;
  scenario_description: string;
  first_turn: TurnResponse;
}

export interface DebriefResponse {
  simulation_id: string;
  scenario_type: string;
  total_turns: number;
  tactics_used: string[];
  tactics_detected: string[];
  intervention_turn: number | null;
  debrief_content: string;
  key_lessons: string[];
}

// =================== Dashboard ===================

export interface DisruptionActionFeed {
  id: string;
  action_type: "bank_freeze" | "telecom_block" | "alert_sent";
  target_entity: string;
  target_institution: string;
  status: string;
  confidence: number;
  created_at: string;
}

export interface DashboardMetrics {
  total_cases_analyzed: number;
  total_scams_detected: number;
  average_confidence: number;
  total_simulations_run: number;
  simulations_intervened: number;
  total_graph_nodes: number;
  total_graph_edges: number;
  most_common_scam_type: string | null;
  agent_calls_total: number;
  agent_fallback_count: number;
  // Command Center fields
  threat_level: "CRITICAL" | "HIGH" | "ELEVATED" | "NORMAL";
  estimated_financial_loss_prevented: number;
  active_disruption_actions: number;
  recent_disruptions: DisruptionActionFeed[];
}

export interface ThreatFeedItem {
  id: string;
  type: "case" | "simulation";
  title: string;
  detail: string;
  risk_level: string;
  timestamp: string;
}

// =================== UI State ===================

export type RiskLevel = "critical" | "high" | "medium" | "low" | "unknown";

export const RISK_COLORS: Record<RiskLevel, string> = {
  critical: "#ef4444",
  high: "#f97316",
  medium: "#eab308",
  low: "#22c55e",
  unknown: "#6b7280",
};

export const RISK_BG_CLASSES: Record<RiskLevel, string> = {
  critical: "bg-red-500/20 text-red-400 border-red-500/30",
  high: "bg-orange-500/20 text-orange-400 border-orange-500/30",
  medium: "bg-yellow-500/20 text-yellow-400 border-yellow-500/30",
  low: "bg-green-500/20 text-green-400 border-green-500/30",
  unknown: "bg-gray-500/20 text-gray-400 border-gray-500/30",
};

export const NODE_TYPE_COLORS: Record<string, string> = {
  phone: "#3b82f6",         // blue
  bank_account: "#f59e0b",  // amber
  upi_id: "#8b5cf6",        // violet
  victim: "#ef4444",        // red
  location: "#10b981",      // emerald
  case: "#06b6d4",          // cyan
  suspect: "#f43f5e",       // rose
  organization: "#6366f1",  // indigo
  email: "#14b8a6",         // teal
  url: "#a855f7",           // purple
  amount: "#eab308",        // yellow
  identity_doc: "#f97316",  // orange
  designation: "#ec4899",   // pink
  ifsc: "#f59e0b",          // amber (same as bank)
};

export const NODE_TYPE_ICONS: Record<string, string> = {
  phone: "📱",
  bank_account: "🏦",
  upi_id: "💳",
  victim: "👤",
  location: "📍",
  case: "📋",
  suspect: "🕵️",
  organization: "🏢",
  email: "📧",
  url: "🔗",
  amount: "💰",
  identity_doc: "🪪",
  designation: "🏷️",
  ifsc: "🏦",
};
