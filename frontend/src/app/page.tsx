"use client";

import { useState, useEffect } from "react";
import Link from "next/link";
import { motion } from "framer-motion";
import {
  Shield,
  Search,
  Network,
  Swords,
  AlertTriangle,
  TrendingUp,
  Activity,
  Eye,
  ArrowRight,
  BarChart3,
  Users,
  Zap,
  PieChart,
  Fingerprint,
  MapPin,
  Landmark,
  Phone,
  IndianRupee,
  ShieldAlert,
  Clock,
  CheckCircle2,
} from "lucide-react";
import { getDashboardMetrics, getThreatFeed, getAnalytics, getGeospatialData } from "@/lib/api";
import type { DashboardMetrics, ThreatFeedItem, DisruptionActionFeed } from "@/lib/types";
import type { AnalyticsData, GeospatialData } from "@/lib/api";
import { DonutChart, HorizontalBarChart, TopEntitiesTable } from "@/components/charts/dashboard-charts";
import { ThreatMap } from "@/components/maps/threat-map";
import { DashboardMetricsSkeleton, ChartSkeleton, ThreatFeedSkeleton } from "@/components/shared/skeletons";
import { ErrorBoundary } from "@/components/shared/error-boundary";

// Stagger animation variants — fast for snappy feel
const container = {
  hidden: { opacity: 0 },
  show: {
    opacity: 1,
    transition: { staggerChildren: 0.03 },
  },
};

const item = {
  hidden: { opacity: 0, y: 12 },
  show: { opacity: 1, y: 0, transition: { duration: 0.25, ease: "easeOut" as const } },
};

// ---------- Threat Level Banner ----------

const THREAT_CONFIG: Record<string, { color: string; bg: string; border: string; glow: string; label: string }> = {
  CRITICAL: { color: "#ef4444", bg: "rgba(239,68,68,0.08)", border: "rgba(239,68,68,0.3)", glow: "0 0 30px rgba(239,68,68,0.15)", label: "CRITICAL" },
  HIGH: { color: "#f97316", bg: "rgba(249,115,22,0.08)", border: "rgba(249,115,22,0.3)", glow: "0 0 30px rgba(249,115,22,0.15)", label: "HIGH" },
  ELEVATED: { color: "#eab308", bg: "rgba(234,179,8,0.08)", border: "rgba(234,179,8,0.3)", glow: "0 0 30px rgba(234,179,8,0.15)", label: "ELEVATED" },
  NORMAL: { color: "#22c55e", bg: "rgba(34,197,94,0.08)", border: "rgba(34,197,94,0.3)", glow: "0 0 30px rgba(34,197,94,0.15)", label: "NORMAL" },
};

function ThreatLevelBanner({ level, financialSaved }: { level: string; financialSaved: number }) {
  const cfg = THREAT_CONFIG[level] || THREAT_CONFIG.NORMAL;

  const formatINR = (amount: number): string => {
    if (amount >= 1_00_00_000) return `₹${(amount / 1_00_00_000).toFixed(1)} Cr`;
    if (amount >= 1_00_000) return `₹${(amount / 1_00_000).toFixed(1)} Lakh`;
    if (amount >= 1_000) return `₹${(amount / 1_000).toFixed(1)}K`;
    return `₹${amount.toFixed(0)}`;
  };

  return (
    <motion.div
      variants={item}
      className="rounded-xl p-4 flex items-center justify-between gap-6"
      style={{
        background: cfg.bg,
        border: `1px solid ${cfg.border}`,
        boxShadow: cfg.glow,
      }}
    >
      <div className="flex items-center gap-4">
        <div className="flex items-center gap-2">
          <ShieldAlert className="h-5 w-5" style={{ color: cfg.color }} />
          <span className="text-xs font-medium text-gray-400 uppercase tracking-wider">
            National Threat Level
          </span>
        </div>
        <div
          className="px-3 py-1 rounded-md text-sm font-bold tracking-wider"
          style={{
            color: cfg.color,
            background: `${cfg.color}15`,
            border: `1px solid ${cfg.color}40`,
          }}
        >
          {cfg.label}
        </div>
      </div>

      <div className="flex items-center gap-2">
        <IndianRupee className="h-4 w-4 text-emerald-400" />
        <span className="text-xs text-gray-400">Estimated Financial Loss Prevented</span>
        <span className="text-lg font-bold text-emerald-400">
          {formatINR(financialSaved)}
        </span>
      </div>
    </motion.div>
  );
}

// ---------- Metric Card ----------

function MetricCard({
  label,
  value,
  icon: Icon,
  color,
  subtitle,
}: {
  label: string;
  value: string | number;
  icon: React.ElementType;
  color: string;
  subtitle?: string;
}) {
  return (
    <motion.div variants={item} className="glass-card glass-card-hover p-5">
      <div className="flex items-start justify-between">
        <div className="space-y-2">
          <p className="text-sm text-gray-400">{label}</p>
          <p className="text-3xl font-bold tracking-tight text-white">
            {value}
          </p>
          {subtitle && (
            <p className="text-xs text-gray-500">{subtitle}</p>
          )}
        </div>
        <div
          className="flex h-10 w-10 items-center justify-center rounded-lg"
          style={{ background: `${color}15`, border: `1px solid ${color}30` }}
        >
          <Icon className="h-5 w-5" style={{ color }} />
        </div>
      </div>
    </motion.div>
  );
}

// ---------- Feature Card ----------

function FeatureCard({
  href,
  title,
  description,
  icon: Icon,
  gradient,
  badge,
}: {
  href: string;
  title: string;
  description: string;
  icon: React.ElementType;
  gradient: string;
  badge?: string;
}) {
  return (
    <motion.div variants={item}>
      <Link href={href} className="block group">
        <div className="glass-card glass-card-hover p-6 h-full">
          <div className="flex items-start justify-between mb-4">
            <div
              className="flex h-12 w-12 items-center justify-center rounded-xl"
              style={{
                background: gradient,
                boxShadow: `0 8px 24px ${gradient.includes("cyan") ? "rgba(6,182,212,0.2)" : gradient.includes("violet") ? "rgba(139,92,246,0.2)" : "rgba(249,115,22,0.2)"}`,
              }}
            >
              <Icon className="h-6 w-6 text-white" />
            </div>
            {badge && (
              <span className="px-2 py-0.5 rounded-full text-[9px] font-semibold bg-cyan-500/15 text-cyan-400 border border-cyan-500/20">
                {badge}
              </span>
            )}
          </div>
          <h3 className="text-lg font-semibold text-white mb-2 group-hover:text-cyan-400 transition-colors">
            {title}
          </h3>
          <p className="text-sm text-gray-400 leading-relaxed mb-4">
            {description}
          </p>
          <div className="flex items-center gap-1 text-sm text-cyan-400 opacity-0 group-hover:opacity-100 transition-opacity">
            <span>Open</span>
            <ArrowRight className="h-4 w-4" />
          </div>
        </div>
      </Link>
    </motion.div>
  );
}

// ---------- Threat Feed ----------

function ThreatFeedCard({ items }: { items: ThreatFeedItem[] }) {
  const getRiskClass = (level: string) => {
    const map: Record<string, string> = {
      critical: "risk-critical",
      high: "risk-high",
      medium: "risk-medium",
      low: "risk-low",
    };
    return map[level] || "risk-low";
  };

  return (
    <motion.div variants={item} className="glass-card p-5">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-sm font-semibold text-white flex items-center gap-2">
          <Activity className="h-4 w-4 text-cyan-400" />
          Live Threat Feed
        </h3>
        <div className="flex items-center gap-1.5">
          <div className="h-1.5 w-1.5 rounded-full bg-cyan-400 animate-pulse-glow" />
          <span className="text-xs text-gray-500">Real-time</span>
        </div>
      </div>

      <div className="space-y-3 max-h-[400px] overflow-y-auto pr-1">
        {items.length === 0 ? (
          <p className="text-sm text-gray-500 text-center py-8">
            No threat activity yet. Analyze a suspicious message to see it here.
          </p>
        ) : (
          items.map((threat, i) => (
            <motion.div
              key={threat.id}
              initial={{ opacity: 0, x: -10 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ delay: i * 0.05 }}
              className="flex items-start gap-3 p-3 rounded-lg bg-white/[0.02] border border-white/[0.04] hover:border-white/[0.08] transition-colors"
            >
              <div className="mt-0.5">
                {threat.type === "case" ? (
                  <AlertTriangle className="h-4 w-4 text-orange-400" />
                ) : (
                  <Swords className="h-4 w-4 text-violet-400" />
                )}
              </div>
              <div className="flex-1 min-w-0">
                <p className="text-sm font-medium text-gray-200 truncate">
                  {threat.title}
                </p>
                <p className="text-xs text-gray-500 mt-0.5 truncate">
                  {threat.detail}
                </p>
              </div>
              <span
                className={`px-2 py-0.5 rounded-full text-[10px] font-medium whitespace-nowrap ${getRiskClass(threat.risk_level)}`}
              >
                {threat.risk_level}
              </span>
            </motion.div>
          ))
        )}
      </div>
    </motion.div>
  );
}

// ---------- Infrastructure Actions Panel ----------

function InfrastructureActionsPanel({ actions }: { actions: DisruptionActionFeed[] }) {
  const getIcon = (type: string) => {
    if (type === "bank_freeze") return <Landmark className="h-3.5 w-3.5 text-amber-400" />;
    if (type === "telecom_block") return <Phone className="h-3.5 w-3.5 text-blue-400" />;
    return <ShieldAlert className="h-3.5 w-3.5 text-red-400" />;
  };

  const getLabel = (type: string) => {
    if (type === "bank_freeze") return "BANK FREEZE";
    if (type === "telecom_block") return "TELECOM BLOCK";
    return "ALERT SENT";
  };

  const getLabelColor = (type: string) => {
    if (type === "bank_freeze") return { bg: "rgba(245,158,11,0.1)", color: "#f59e0b", border: "rgba(245,158,11,0.2)" };
    if (type === "telecom_block") return { bg: "rgba(59,130,246,0.1)", color: "#3b82f6", border: "rgba(59,130,246,0.2)" };
    return { bg: "rgba(239,68,68,0.1)", color: "#ef4444", border: "rgba(239,68,68,0.2)" };
  };

  return (
    <motion.div variants={item} className="glass-card p-5">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-sm font-semibold text-white flex items-center gap-2">
          <Shield className="h-4 w-4 text-amber-400" />
          Infrastructure Actions
        </h3>
        <span className="text-[10px] px-2 py-0.5 rounded-full bg-amber-500/10 text-amber-400 border border-amber-500/20">
          Simulated
        </span>
      </div>

      <div className="space-y-2 max-h-[300px] overflow-y-auto pr-1">
        {actions.length === 0 ? (
          <div className="text-center py-6">
            <Shield className="h-8 w-8 text-gray-600 mx-auto mb-2" />
            <p className="text-xs text-gray-500">
              No automated actions yet. High-confidence scam detections trigger bank freeze and telecom block webhooks.
            </p>
          </div>
        ) : (
          actions.map((action, i) => {
            const lc = getLabelColor(action.action_type);
            return (
              <motion.div
                key={action.id}
                initial={{ opacity: 0, x: 10 }}
                animate={{ opacity: 1, x: 0 }}
                transition={{ delay: i * 0.04 }}
                className="flex items-center gap-3 p-2.5 rounded-lg bg-white/[0.02] border border-white/[0.04]"
              >
                {getIcon(action.action_type)}
                <div className="flex-1 min-w-0">
                  <p className="text-xs text-gray-300 truncate">
                    {action.target_institution}: <span className="text-white font-medium">{action.target_entity}</span>
                  </p>
                </div>
                <span
                  className="text-[9px] font-semibold px-1.5 py-0.5 rounded whitespace-nowrap"
                  style={{ background: lc.bg, color: lc.color, border: `1px solid ${lc.border}` }}
                >
                  {getLabel(action.action_type)}
                </span>
              </motion.div>
            );
          })
        )}
      </div>
    </motion.div>
  );
}

// ---------- Mission Queue ----------

function MissionQueue({ metrics }: { metrics: DashboardMetrics | null }) {
  if (!metrics) return null;

  const missions: Array<{ label: string; done: boolean; urgency: string }> = [];

  // Generate dynamic mission queue based on real data
  if (metrics.total_scams_detected > 0) {
    const hasHighRisk = metrics.threat_level === "CRITICAL" || metrics.threat_level === "HIGH";
    if (hasHighRisk) {
      missions.push({ label: "Review high-risk cases", done: false, urgency: "high" });
    }
    if (metrics.active_disruption_actions > 0) {
      missions.push({ label: `${metrics.active_disruption_actions} disruption actions pending`, done: false, urgency: "high" });
    }
    missions.push({ label: "Generate NCRB alert for latest case", done: false, urgency: "medium" });
    if (metrics.total_graph_nodes > 5) {
      missions.push({ label: "Run risk propagation on network", done: false, urgency: "medium" });
    }
  }
  if (metrics.total_cases_analyzed === 0) {
    missions.push({ label: "Analyze first suspicious message", done: false, urgency: "low" });
    missions.push({ label: "Run adversarial simulation", done: false, urgency: "low" });
  }

  const urgencyColor: Record<string, string> = {
    high: "#ef4444",
    medium: "#f59e0b",
    low: "#06b6d4",
  };

  return (
    <motion.div variants={item} className="glass-card p-5">
      <div className="flex items-center gap-2 mb-4">
        <Clock className="h-4 w-4 text-cyan-400" />
        <h3 className="text-sm font-semibold text-white">Mission Queue</h3>
      </div>
      <div className="space-y-2">
        {missions.length === 0 ? (
          <div className="flex items-center gap-2 py-4 justify-center">
            <CheckCircle2 className="h-4 w-4 text-emerald-400" />
            <span className="text-xs text-gray-400">All missions complete</span>
          </div>
        ) : (
          missions.map((m, i) => (
            <div key={i} className="flex items-center gap-3 p-2.5 rounded-lg bg-white/[0.02] border border-white/[0.04]">
              <div
                className="h-2 w-2 rounded-full flex-shrink-0"
                style={{ background: urgencyColor[m.urgency] || "#06b6d4" }}
              />
              <span className="text-xs text-gray-300 flex-1">{m.label}</span>
              <span
                className="text-[9px] uppercase font-medium px-1.5 py-0.5 rounded"
                style={{
                  color: urgencyColor[m.urgency],
                  background: `${urgencyColor[m.urgency]}10`,
                }}
              >
                {m.urgency}
              </span>
            </div>
          ))
        )}
      </div>
    </motion.div>
  );
}

// ---------- Main Page ----------

export default function DashboardPage() {
  const [metrics, setMetrics] = useState<DashboardMetrics | null>(null);
  const [threats, setThreats] = useState<ThreatFeedItem[]>([]);
  const [analytics, setAnalytics] = useState<AnalyticsData | null>(null);
  const [geoData, setGeoData] = useState<GeospatialData | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function fetchData() {
      try {
        // Use allSettled so ONE failing endpoint doesn't break the whole dashboard
        const [mResult, tResult, aResult, gResult] = await Promise.allSettled([
          getDashboardMetrics(),
          getThreatFeed(15),
          getAnalytics(),
          getGeospatialData(),
        ]);
        if (mResult.status === "fulfilled") setMetrics(mResult.value);
        if (tResult.status === "fulfilled") setThreats(tResult.value);
        if (aResult.status === "fulfilled") setAnalytics(aResult.value);
        if (gResult.status === "fulfilled") setGeoData(gResult.value);

        // Log any failures for debugging
        [mResult, tResult, aResult, gResult].forEach((r, i) => {
          if (r.status === "rejected") {
            const names = ["metrics", "threats", "analytics", "geospatial"];
            console.warn(`Dashboard ${names[i]} fetch failed:`, r.reason);
          }
        });
      } catch (err) {
        console.error("Failed to load dashboard:", err);
      } finally {
        setLoading(false);
      }
    }
    fetchData();
  }, []);

  return (
    <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8 py-8">
      {/* Hero */}
      <motion.div
        initial={{ opacity: 0, y: -10 }}
        animate={{ opacity: 1, y: 0 }}
        className="mb-6"
      >
        <div className="flex items-center gap-3 mb-2">
          <Eye className="h-6 w-6 text-cyan-400" />
          <h1 className="text-2xl font-bold text-white">
            Cyber Command Center
          </h1>
        </div>
        <p className="text-gray-400 text-sm max-w-2xl">
          National cyber intelligence overview. Monitor threats, coordinate disruptions, and protect citizens in real-time.
        </p>
      </motion.div>

      <motion.div
        variants={container}
        initial="hidden"
        animate="show"
        className="space-y-5"
      >
        {/* Threat Level Banner */}
        {!loading && metrics && (
          <ThreatLevelBanner
            level={metrics.threat_level}
            financialSaved={metrics.estimated_financial_loss_prevented}
          />
        )}

        {/* Metrics Row */}
        {loading ? (
          <DashboardMetricsSkeleton />
        ) : (
        <div className="grid grid-cols-2 lg:grid-cols-5 gap-4">
          <MetricCard
            label="Cases Analyzed"
            value={metrics?.total_cases_analyzed ?? "—"}
            icon={BarChart3}
            color="#06b6d4"
            subtitle={
              metrics
                ? `${metrics.total_scams_detected} scams detected`
                : undefined
            }
          />
          <MetricCard
            label="Avg Confidence"
            value={
              metrics ? `${(metrics.average_confidence * 100).toFixed(1)}%` : "—"
            }
            icon={TrendingUp}
            color="#3b82f6"
            subtitle="Detection accuracy"
          />
          <MetricCard
            label="Simulations Run"
            value={metrics?.total_simulations_run ?? "—"}
            icon={Swords}
            color="#8b5cf6"
            subtitle={
              metrics
                ? `${metrics.simulations_intervened} interventions`
                : undefined
            }
          />
          <MetricCard
            label="Network Entities"
            value={metrics?.total_graph_nodes ?? "—"}
            icon={Users}
            color="#f59e0b"
            subtitle={
              metrics
                ? `${metrics.total_graph_edges} connections`
                : undefined
            }
          />
          <MetricCard
            label="Disruptions"
            value={metrics?.active_disruption_actions ?? "—"}
            icon={Shield}
            color="#ef4444"
            subtitle="Automated actions"
          />
        </div>
        )}

        {/* Two-Column: Map + Infrastructure Actions */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-5">
          {/* Geospatial Threat Map */}
          <div className="lg:col-span-2">
            {geoData && geoData.points.length > 0 ? (
              <motion.div variants={item} className="glass-card p-5">
                <div className="flex items-center justify-between mb-4">
                  <h3 className="text-sm font-semibold text-white flex items-center gap-2">
                    <MapPin className="h-4 w-4 text-orange-400" />
                    Geospatial Threat Intelligence
                  </h3>
                  <div className="flex items-center gap-3 text-xs text-gray-500">
                    <span>{geoData.total_locations} locations</span>
                    <span className="text-red-400">{geoData.hotspot_count} hotspots</span>
                  </div>
                </div>
                <ThreatMap points={geoData.points} height={340} />
                <div className="flex items-center gap-4 mt-3 pt-3 border-t border-white/[0.04] text-xs text-gray-500">
                  <div className="flex items-center gap-1.5">
                    <div className="h-2 w-2 rounded-full bg-red-500" />
                    <span>Hotspot</span>
                  </div>
                  <div className="flex items-center gap-1.5">
                    <div className="h-2 w-2 rounded-full bg-orange-500" />
                    <span>High Risk</span>
                  </div>
                  <div className="flex items-center gap-1.5">
                    <div className="h-2 w-2 rounded-full bg-cyan-500" />
                    <span>Detected</span>
                  </div>
                  <span className="ml-auto">Data: NETRA Graph + NCRB Hotspot Registry</span>
                </div>
              </motion.div>
            ) : (
              <motion.div variants={item} className="glass-card p-5 flex items-center justify-center" style={{ minHeight: 340 }}>
                <div className="text-center">
                  <MapPin className="h-8 w-8 text-gray-600 mx-auto mb-2" />
                  <p className="text-xs text-gray-500">Analyze cases to populate the threat map</p>
                </div>
              </motion.div>
            )}
          </div>

          {/* Infrastructure Actions + Mission Queue */}
          <div className="space-y-5">
            <InfrastructureActionsPanel
              actions={metrics?.recent_disruptions || []}
            />
            <MissionQueue metrics={metrics} />
          </div>
        </div>

        {/* Analytics Charts Row */}
        {loading ? (
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-5">
            <ChartSkeleton height={160} />
            <ChartSkeleton height={160} />
            <ChartSkeleton height={160} />
          </div>
        ) : analytics && (
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-5">
            {/* Scam Type Distribution */}
            <motion.div variants={item} className="glass-card p-5">
              <div className="flex items-center gap-2 mb-4">
                <PieChart className="h-4 w-4 text-cyan-400" />
                <h3 className="text-sm font-semibold text-white">
                  Scam Type Distribution
                </h3>
              </div>
              {analytics.scam_type_distribution.length > 0 ? (
                <DonutChart
                  data={analytics.scam_type_distribution}
                  title="Scam Types"
                  size={180}
                />
              ) : (
                <p className="text-xs text-gray-600 text-center py-8">
                  Analyze cases to populate chart
                </p>
              )}
            </motion.div>

            {/* Entity Type Breakdown */}
            <motion.div variants={item} className="glass-card p-5">
              <div className="flex items-center gap-2 mb-4">
                <Fingerprint className="h-4 w-4 text-violet-400" />
                <h3 className="text-sm font-semibold text-white">
                  Entity Breakdown
                </h3>
              </div>
              {analytics.entity_type_breakdown.length > 0 ? (
                <HorizontalBarChart
                  data={analytics.entity_type_breakdown}
                  title="Entities"
                />
              ) : (
                <p className="text-xs text-gray-600 text-center py-8">
                  Entities populate as cases are analyzed
                </p>
              )}
            </motion.div>

            {/* Top Risk Entities */}
            <motion.div variants={item} className="glass-card p-5">
              <div className="flex items-center gap-2 mb-4">
                <AlertTriangle className="h-4 w-4 text-red-400" />
                <h3 className="text-sm font-semibold text-white">
                  High-Risk Entities
                </h3>
              </div>
              <TopEntitiesTable entities={analytics.top_entities} />
            </motion.div>
          </div>
        )}

        {/* Main Content Grid: Features + Threat Feed */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-5">
          {/* Feature Cards */}
          <div className="lg:col-span-2 grid grid-cols-1 sm:grid-cols-3 gap-4">
            <FeatureCard
              href="/detect"
              title="Detect"
              description="Paste text, upload screenshots, or scan banknotes. Multi-modal AI analysis with Kill Chain decomposition."
              icon={Search}
              gradient="linear-gradient(135deg, #06b6d4, #0891b2)"
              badge="Multi-Modal"
            />
            <FeatureCard
              href="/investigate"
              title="Investigate"
              description="Explore auto-populated fraud networks. Entity extraction feeds the graph in real-time."
              icon={Network}
              gradient="linear-gradient(135deg, #8b5cf6, #7c3aed)"
              badge="Auto-Graph"
            />
            <FeatureCard
              href="/simulate"
              title="Simulate"
              description="AI-powered adversarial simulations. Build psychological immunity against digital threats."
              icon={Swords}
              gradient="linear-gradient(135deg, #f97316, #ea580c)"
              badge="Adversarial AI"
            />
          </div>

          {/* Threat Feed */}
          <div className="lg:col-span-1">
            <ThreatFeedCard items={threats} />
          </div>
        </div>

        {/* SETIE — Intelligence Overview */}
        <motion.div variants={item} className="glass-card p-5">
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-sm font-semibold text-white flex items-center gap-2">
              <BarChart3 className="h-4 w-4 text-cyan-400" />
              Threat Intelligence Engine (SETIE)
            </h3>
            <Link
              href="/evaluation"
              className="text-xs text-cyan-400 hover:text-cyan-300 flex items-center gap-1 transition"
            >
              Full Report <ArrowRight className="h-3 w-3" />
            </Link>
          </div>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            <div className="rounded-lg bg-cyan-500/5 border border-cyan-500/10 p-3">
              <p className="text-[10px] uppercase tracking-wider text-white/40">Detection Model</p>
              <p className="text-sm font-bold text-cyan-400 mt-1">Gemini + Kill Chain</p>
            </div>
            <div className="rounded-lg bg-emerald-500/5 border border-emerald-500/10 p-3">
              <p className="text-[10px] uppercase tracking-wider text-white/40">Cross-Case Intel</p>
              <p className="text-sm font-bold text-emerald-400 mt-1">Embedding Similarity</p>
            </div>
            <div className="rounded-lg bg-purple-500/5 border border-purple-500/10 p-3">
              <p className="text-[10px] uppercase tracking-wider text-white/40">Graph Algorithms</p>
              <p className="text-sm font-bold text-purple-400 mt-1">PageRank + Louvain</p>
            </div>
            <div className="rounded-lg bg-orange-500/5 border border-orange-500/10 p-3">
              <p className="text-[10px] uppercase tracking-wider text-white/40">Pattern Discovery</p>
              <p className="text-sm font-bold text-orange-400 mt-1">DBSCAN Clustering</p>
            </div>
          </div>
        </motion.div>

        {/* Agent System Status */}
        <motion.div variants={item} className="glass-card p-5">
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-sm font-semibold text-white flex items-center gap-2">
              <Zap className="h-4 w-4 text-cyan-400" />
              Agent System Status
            </h3>
          </div>
          <div className="grid grid-cols-2 sm:grid-cols-6 gap-3">
            {[
              { name: "Detection Agent", status: "ready", model: "Gemini 2.5 Flash" },
              { name: "Entity Extraction", status: "ready", model: "Regex + LLM NER" },
              { name: "Graph Engine", status: "ready", model: "Auto-Population" },
              { name: "Vision OCR", status: "ready", model: "Gemini Multimodal" },
              { name: "Simulation Agent", status: "ready", model: "Adversarial AI" },
              { name: "Disruption Engine", status: "ready", model: "Webhook Sim" },
            ].map((agent) => (
              <div
                key={agent.name}
                className="rounded-lg bg-white/[0.02] border border-white/[0.04] p-3"
              >
                <div className="flex items-center gap-2 mb-1">
                  <div className="h-1.5 w-1.5 rounded-full bg-emerald-400" />
                  <span className="text-xs font-medium text-gray-300">
                    {agent.name}
                  </span>
                </div>
                <p className="text-[10px] text-gray-500 ml-3.5">
                  {agent.model}
                </p>
              </div>
            ))}
          </div>
          {metrics && metrics.agent_calls_total > 0 && (
            <div className="mt-3 pt-3 border-t border-white/[0.04] flex items-center gap-4 text-xs text-gray-500">
              <span>
                Total agent calls:{" "}
                <span className="text-gray-300">{metrics.agent_calls_total}</span>
              </span>
              <span>
                Fallbacks used:{" "}
                <span className="text-gray-300">{metrics.agent_fallback_count}</span>
              </span>
            </div>
          )}
        </motion.div>
      </motion.div>
    </div>
  );
}
