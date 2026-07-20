"use client";

import { useState, useEffect } from "react";
import { motion } from "framer-motion";
import {
  getLatestEvaluation,
  runEvaluation,
  getIntelligencePageRank,
  getIntelligenceCommunities,
  getIntelligenceGraphStats,
  type EvaluationResult,
  type PageRankEntity,
  type IntelCommunity,
  type IntelGraphStats,
} from "@/lib/api";

// ---------- Metric Card ----------
function MetricCard({
  label,
  value,
  subtitle,
  color,
}: {
  label: string;
  value: string;
  subtitle?: string;
  color: string;
}) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      className="rounded-xl border border-white/10 p-5"
      style={{ background: `linear-gradient(135deg, ${color}15, transparent)` }}
    >
      <p className="text-xs uppercase tracking-wider text-white/50 mb-1">
        {label}
      </p>
      <p className="text-3xl font-bold" style={{ color }}>
        {value}
      </p>
      {subtitle && (
        <p className="text-xs text-white/40 mt-1">{subtitle}</p>
      )}
    </motion.div>
  );
}

// ---------- Confusion Matrix ----------
function ConfusionMatrix({
  matrix,
}: {
  matrix: Record<string, Record<string, number>>;
}) {
  const labels = Object.keys(matrix);

  return (
    <div className="rounded-xl border border-white/10 p-5 bg-white/[0.02]">
      <h3 className="text-sm font-semibold text-white/70 mb-4">
        Confusion Matrix
      </h3>
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr>
              <th className="text-left text-white/40 p-2"></th>
              {labels.map((l) => (
                <th
                  key={l}
                  className="text-center text-white/60 p-2 capitalize"
                >
                  Pred: {l}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {labels.map((actual) => (
              <tr key={actual}>
                <td className="text-white/60 p-2 capitalize font-medium">
                  Act: {actual}
                </td>
                {labels.map((pred) => {
                  const val = matrix[actual]?.[pred] ?? 0;
                  const isCorrect = actual === pred;
                  return (
                    <td key={pred} className="text-center p-2">
                      <span
                        className={`inline-block rounded-lg px-3 py-1.5 font-bold text-lg ${
                          isCorrect
                            ? "bg-emerald-500/20 text-emerald-400"
                            : val > 0
                            ? "bg-red-500/20 text-red-400"
                            : "bg-white/5 text-white/20"
                        }`}
                      >
                        {val}
                      </span>
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

// ---------- Per-Category Chart ----------
function CategoryBreakdown({
  perCategory,
}: {
  perCategory: Record<
    string,
    { precision: number; recall: number; f1: number; accuracy: number; total: number }
  >;
}) {
  const categories = Object.entries(perCategory).sort(
    (a, b) => b[1].f1 - a[1].f1
  );

  return (
    <div className="rounded-xl border border-white/10 p-5 bg-white/[0.02]">
      <h3 className="text-sm font-semibold text-white/70 mb-4">
        Per-Category Accuracy
      </h3>
      <div className="space-y-3">
        {categories.map(([cat, stats]) => (
          <div key={cat}>
            <div className="flex justify-between text-xs mb-1">
              <span className="text-white/60 capitalize">
                {cat.replace(/_/g, " ")}
              </span>
              <span className="text-white/80 font-mono">
                {(stats.accuracy * 100).toFixed(0)}% ({stats.total} cases)
              </span>
            </div>
            <div className="h-2 bg-white/5 rounded-full overflow-hidden">
              <motion.div
                initial={{ width: 0 }}
                animate={{ width: `${stats.accuracy * 100}%` }}
                transition={{ duration: 0.8, ease: "easeOut" }}
                className="h-full rounded-full"
                style={{
                  background:
                    stats.accuracy >= 0.9
                      ? "#10b981"
                      : stats.accuracy >= 0.7
                      ? "#f59e0b"
                      : "#ef4444",
                }}
              />
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

// ---------- Baseline Comparison ----------
function BaselineComparison({ eval: ev }: { eval: EvaluationResult }) {
  if (!ev.baseline_f1) return null;

  const metrics = [
    { label: "F1 Score", netra: ev.f1_score, baseline: ev.baseline_f1 },
    {
      label: "Precision",
      netra: ev.precision,
      baseline: ev.baseline_precision ?? 0,
    },
    { label: "Recall", netra: ev.recall, baseline: ev.baseline_recall ?? 0 },
  ];

  return (
    <div className="rounded-xl border border-white/10 p-5 bg-white/[0.02]">
      <h3 className="text-sm font-semibold text-white/70 mb-2">
        NETRA (LLM) vs. Baseline (TF-IDF + Logistic Regression)
      </h3>
      {ev.improvement_pct && (
        <p className="text-emerald-400 text-sm mb-4">
          ▲ NETRA outperforms baseline by{" "}
          <span className="font-bold text-lg">
            {ev.improvement_pct.toFixed(1)}%
          </span>
        </p>
      )}
      <div className="space-y-4">
        {metrics.map((m) => (
          <div key={m.label}>
            <p className="text-xs text-white/50 mb-2">{m.label}</p>
            <div className="flex items-center gap-3">
              <div className="flex-1">
                <div className="flex justify-between text-xs mb-1">
                  <span className="text-cyan-400">NETRA</span>
                  <span className="text-cyan-400 font-mono">
                    {(m.netra * 100).toFixed(1)}%
                  </span>
                </div>
                <div className="h-3 bg-white/5 rounded-full overflow-hidden">
                  <motion.div
                    initial={{ width: 0 }}
                    animate={{ width: `${m.netra * 100}%` }}
                    transition={{ duration: 1 }}
                    className="h-full rounded-full bg-gradient-to-r from-cyan-500 to-blue-500"
                  />
                </div>
              </div>
              <div className="flex-1">
                <div className="flex justify-between text-xs mb-1">
                  <span className="text-orange-400">Baseline</span>
                  <span className="text-orange-400 font-mono">
                    {(m.baseline * 100).toFixed(1)}%
                  </span>
                </div>
                <div className="h-3 bg-white/5 rounded-full overflow-hidden">
                  <motion.div
                    initial={{ width: 0 }}
                    animate={{ width: `${m.baseline * 100}%` }}
                    transition={{ duration: 1 }}
                    className="h-full rounded-full bg-gradient-to-r from-orange-500 to-red-500"
                  />
                </div>
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

// ---------- Graph Intelligence Section ----------
function GraphIntelligence({
  stats,
  pagerank,
  communities,
}: {
  stats: IntelGraphStats | null;
  pagerank: PageRankEntity[];
  communities: IntelCommunity[];
}) {
  return (
    <div className="space-y-6">
      <h2 className="text-xl font-bold text-white/90 flex items-center gap-2">
        <span className="text-2xl">🕸️</span> Graph Intelligence
      </h2>
      {stats && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          <MetricCard label="Nodes" value={String(stats.total_nodes)} color="#8b5cf6" />
          <MetricCard label="Edges" value={String(stats.total_edges)} color="#6366f1" />
          <MetricCard label="Components" value={String(stats.connected_components)} color="#a855f7" />
          <MetricCard label="Syndicates" value={String(stats.communities_detected)} color="#ec4899" />
        </div>
      )}

      {pagerank.length > 0 && (
        <div className="rounded-xl border border-white/10 p-5 bg-white/[0.02]">
          <h3 className="text-sm font-semibold text-white/70 mb-3">
            PageRank — Top Entities (Kingpin Nodes)
          </h3>
          <div className="space-y-2">
            {pagerank.slice(0, 8).map((e, i) => (
              <div
                key={e.node_id}
                className="flex items-center gap-3 text-sm"
              >
                <span className="text-white/30 font-mono w-6">#{i + 1}</span>
                <span className="text-xs px-2 py-0.5 rounded bg-white/10 text-white/50 capitalize w-20 text-center">
                  {e.node_type}
                </span>
                <span className="text-white/80 flex-1 truncate">
                  {e.label}
                </span>
                <span className="text-cyan-400 font-mono text-xs">
                  PR: {e.score.toFixed(4)}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}

      {communities.length > 0 && (
        <div className="rounded-xl border border-white/10 p-5 bg-white/[0.02]">
          <h3 className="text-sm font-semibold text-white/70 mb-3">
            Louvain Communities — Detected Syndicates
          </h3>
          <div className="grid gap-3 md:grid-cols-2">
            {communities.slice(0, 4).map((c) => (
              <div
                key={c.community_id}
                className="rounded-lg border border-white/10 p-4 bg-white/[0.02]"
              >
                <div className="flex items-center justify-between mb-2">
                  <span className="text-sm font-semibold text-white/70">
                    Syndicate #{c.community_id + 1}
                  </span>
                  <span className="text-xs px-2 py-0.5 rounded bg-red-500/20 text-red-400">
                    {c.size} members
                  </span>
                </div>
                <p className="text-xs text-white/40 mb-1">
                  Density: {(c.density * 100).toFixed(1)}%
                </p>
                <p className="text-xs text-white/60">
                  Key:{" "}
                  {c.key_entities
                    .slice(0, 3)
                    .join(", ")}
                </p>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

// ---------- Main Page ----------
export default function EvaluationPage() {
  const [evalData, setEvalData] = useState<EvaluationResult | null>(null);
  const [graphStats, setGraphStats] = useState<IntelGraphStats | null>(null);
  const [pagerank, setPagerank] = useState<PageRankEntity[]>([]);
  const [communities, setCommunities] = useState<IntelCommunity[]>([]);
  const [loading, setLoading] = useState(true);
  const [running, setRunning] = useState(false);

  useEffect(() => {
    async function fetchData() {
      try {
        const [ev, gs, pr, com] = await Promise.allSettled([
          getLatestEvaluation(),
          getIntelligenceGraphStats(),
          getIntelligencePageRank(10),
          getIntelligenceCommunities(),
        ]);

        if (ev.status === "fulfilled" && !("status" in ev.value && ev.value.status === "no_evaluation_run")) {
          setEvalData(ev.value);
        }
        if (gs.status === "fulfilled") setGraphStats(gs.value);
        if (pr.status === "fulfilled") setPagerank(pr.value.entities || []);
        if (com.status === "fulfilled") setCommunities(com.value.communities || []);
      } catch (err) {
        console.error("Failed to fetch evaluation data:", err);
      } finally {
        setLoading(false);
      }
    }
    fetchData();
  }, []);

  async function handleRunEvaluation() {
    setRunning(true);
    try {
      const result = await runEvaluation();
      setEvalData(result);
    } catch (err) {
      console.error("Evaluation run issue:", err);
      // Silently handle — no error messages shown to user
    } finally {
      setRunning(false);
    }
  }

  return (
    <div className="min-h-screen bg-[#0a0a0f] text-white px-6 py-8">
      <div className="max-w-7xl mx-auto space-y-8">
        {/* Header */}
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-3xl font-bold bg-gradient-to-r from-cyan-400 to-blue-500 bg-clip-text text-transparent">
              Evaluation & Intelligence
            </h1>
            <p className="text-white/50 mt-1 text-sm">
              Quantified proof that NETRA works — F1, precision, recall, baseline comparison, and graph intelligence
            </p>
          </div>
          <div className="flex gap-3">
            <a
              href="/"
              className="px-4 py-2 rounded-lg border border-white/10 text-white/60 hover:text-white text-sm transition"
            >
              ← Dashboard
            </a>
            <button
              onClick={handleRunEvaluation}
              disabled={running}
              className="px-5 py-2 rounded-lg bg-gradient-to-r from-cyan-500 to-blue-600 text-white font-medium text-sm
                hover:from-cyan-400 hover:to-blue-500 transition disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {running ? "⏳ Running..." : "▶ Run Evaluation"}
            </button>
          </div>
        </div>

        {loading ? (
          <div className="flex items-center justify-center py-20">
            <div className="animate-spin h-8 w-8 border-2 border-cyan-400 border-t-transparent rounded-full" />
          </div>
        ) : !evalData ? (
          <div className="text-center py-20">
            <p className="text-6xl mb-4">📊</p>
            <p className="text-white/60 text-lg">
              No evaluation results yet
            </p>
            <p className="text-white/40 text-sm mt-2">
              Click &quot;Run Evaluation&quot; to benchmark NETRA against 60 test cases
              and train a classical ML baseline for comparison.
            </p>
          </div>
        ) : (
          <div className="space-y-8">
            {/* Core Metrics */}
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              <MetricCard
                label="F1 Score"
                value={`${(evalData.f1_score * 100).toFixed(1)}%`}
                subtitle="Harmonic mean of P & R"
                color="#06b6d4"
              />
              <MetricCard
                label="Precision"
                value={`${(evalData.precision * 100).toFixed(1)}%`}
                subtitle="True positives / predicted"
                color="#10b981"
              />
              <MetricCard
                label="Recall"
                value={`${(evalData.recall * 100).toFixed(1)}%`}
                subtitle="True positives / actual"
                color="#f59e0b"
              />
              <MetricCard
                label="Accuracy"
                value={`${(evalData.accuracy * 100).toFixed(1)}%`}
                subtitle={`${evalData.total_cases} test cases`}
                color="#8b5cf6"
              />
            </div>

            {/* Baseline Comparison */}
            <BaselineComparison eval={evalData} />

            {/* Confusion Matrix + Category Breakdown */}
            <div className="grid md:grid-cols-2 gap-6">
              <ConfusionMatrix matrix={evalData.confusion_matrix} />
              <CategoryBreakdown perCategory={evalData.per_category} />
            </div>

            {/* Meta */}
            <div className="rounded-xl border border-white/10 p-4 bg-white/[0.02] text-sm text-white/40">
              <div className="flex flex-wrap gap-6">
                <span>Model: <span className="text-white/70">{evalData.llm_model || "—"}</span></span>
                <span>Duration: <span className="text-white/70">{evalData.duration_seconds}s</span></span>
                <span>Baseline: <span className="text-white/70">{evalData.baseline_model || "—"}</span></span>
                {evalData.run_date && (
                  <span>Run: <span className="text-white/70">{new Date(evalData.run_date).toLocaleString()}</span></span>
                )}
              </div>
            </div>
          </div>
        )}

        {/* Graph Intelligence Section */}
        <GraphIntelligence
          stats={graphStats}
          pagerank={pagerank}
          communities={communities}
        />
      </div>
    </div>
  );
}
