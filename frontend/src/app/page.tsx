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
} from "lucide-react";
import { getDashboardMetrics, getThreatFeed, getAnalytics, getGeospatialData } from "@/lib/api";
import type { DashboardMetrics, ThreatFeedItem } from "@/lib/types";
import type { AnalyticsData, GeospatialData } from "@/lib/api";
import { DonutChart, HorizontalBarChart, TopEntitiesTable } from "@/components/charts/dashboard-charts";
import { ThreatMap } from "@/components/maps/threat-map";
import { DashboardMetricsSkeleton, ChartSkeleton, ThreatFeedSkeleton } from "@/components/shared/skeletons";
import { ErrorBoundary } from "@/components/shared/error-boundary";

// Stagger animation variants
const container = {
  hidden: { opacity: 0 },
  show: {
    opacity: 1,
    transition: { staggerChildren: 0.08 },
  },
};

const item = {
  hidden: { opacity: 0, y: 20 },
  show: { opacity: 1, y: 0, transition: { duration: 0.5, ease: "easeOut" as const } },
};

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

export default function DashboardPage() {
  const [metrics, setMetrics] = useState<DashboardMetrics | null>(null);
  const [threats, setThreats] = useState<ThreatFeedItem[]>([]);
  const [analytics, setAnalytics] = useState<AnalyticsData | null>(null);
  const [geoData, setGeoData] = useState<GeospatialData | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function fetchData() {
      try {
        const [m, t, a, g] = await Promise.all([
          getDashboardMetrics(),
          getThreatFeed(15),
          getAnalytics(),
          getGeospatialData(),
        ]);
        setMetrics(m);
        setThreats(t);
        setAnalytics(a);
        setGeoData(g);
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
        className="mb-10"
      >
        <div className="flex items-center gap-3 mb-2">
          <Eye className="h-6 w-6 text-cyan-400" />
          <h1 className="text-2xl font-bold text-white">
            Command Center
          </h1>
        </div>
        <p className="text-gray-400 text-sm max-w-2xl">
          Real-time intelligence overview. Detect scam threats, investigate
          fraud networks, and simulate attacks to build citizen resilience.
        </p>
      </motion.div>

      <motion.div
        variants={container}
        initial="hidden"
        animate="show"
        className="space-y-6"
      >
        {/* Metrics Row */}
        {loading ? (
          <DashboardMetricsSkeleton />
        ) : (
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
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
                ? `${metrics.simulations_intervened} interventions triggered`
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
                ? `${metrics.total_graph_edges} connections mapped`
                : undefined
            }
          />
        </div>
        )}

        {/* Analytics Charts Row */}
        {loading ? (
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            <ChartSkeleton height={160} />
            <ChartSkeleton height={160} />
            <ChartSkeleton height={160} />
          </div>
        ) : analytics && (
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
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

        {/* Geospatial Threat Map */}
        {geoData && geoData.points.length > 0 && (
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
            <ThreatMap points={geoData.points} height={380} />
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
        )}

        {/* Main Content Grid */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
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

        {/* Agent System Status */}
        <motion.div variants={item} className="glass-card p-5">
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-sm font-semibold text-white flex items-center gap-2">
              <Zap className="h-4 w-4 text-cyan-400" />
              Agent System Status
            </h3>
          </div>
          <div className="grid grid-cols-2 sm:grid-cols-5 gap-3">
            {[
              { name: "Detection Agent", status: "ready", model: "Gemini 2.5 Flash" },
              { name: "Entity Extraction", status: "ready", model: "Regex + LLM NER" },
              { name: "Graph Engine", status: "ready", model: "Auto-Population" },
              { name: "Vision OCR", status: "ready", model: "Gemini Multimodal" },
              { name: "Simulation Agent", status: "ready", model: "Adversarial AI" },
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
