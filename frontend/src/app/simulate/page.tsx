"use client";

import { useState, useEffect, useRef } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  Swords,
  Send,
  Loader2,
  AlertTriangle,
  ShieldAlert,
  BookOpen,
  ChevronRight,
  Shield,
  Brain,
  Info,
} from "lucide-react";
import {
  getScenarios,
  startSimulation,
  respondToSimulation,
  getDebrief,
} from "@/lib/api";
import type {
  ScenarioInfo,
  TurnResponse,
  TurnAnalysis,
  DebriefResponse,
} from "@/lib/types";

type SimPhase = "select" | "active" | "debrief";

interface ChatMessage {
  role: "scammer" | "user" | "system";
  content: string;
  analysis?: TurnAnalysis;
  turnNumber: number;
}

function ScenarioCard({
  scenario,
  onSelect,
  index,
}: {
  scenario: ScenarioInfo;
  onSelect: () => void;
  index: number;
}) {
  const colorMap: Record<string, string> = {
    impersonation: "#ef4444",
    phishing: "#f97316",
    investment_fraud: "#eab308",
    extortion: "#a855f7",
    blackmail: "#ec4899",
    advance_fee_fraud: "#06b6d4",
  };
  const color = colorMap[scenario.category] || "#6b7280";

  return (
    <motion.button
      initial={{ opacity: 0, y: 15 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: index * 0.08 }}
      onClick={onSelect}
      className="glass-card glass-card-hover p-5 text-left w-full group"
    >
      <div className="flex items-start justify-between mb-3">
        <span
          className="text-[10px] font-semibold px-2 py-0.5 rounded-full uppercase"
          style={{ background: `${color}15`, color, border: `1px solid ${color}30` }}
        >
          {scenario.category.replace(/_/g, " ")}
        </span>
        {scenario.prevalence && (
          <span className="text-[10px] text-gray-500">{scenario.prevalence}</span>
        )}
      </div>
      <h3 className="text-base font-semibold text-white mb-2 group-hover:text-orange-400 transition-colors">
        {scenario.name}
      </h3>
      <p className="text-xs text-gray-400 leading-relaxed line-clamp-3">
        {scenario.description}
      </p>
      <div className="mt-3 flex items-center gap-1 text-xs text-orange-400 opacity-0 group-hover:opacity-100 transition-opacity">
        <span>Start Simulation</span>
        <ChevronRight className="h-3 w-3" />
      </div>
    </motion.button>
  );
}

function AnalysisPanel({ analysis, turnNumber }: { analysis: TurnAnalysis; turnNumber: number }) {
  const riskColors: Record<string, string> = {
    low: "#22c55e",
    medium: "#eab308",
    high: "#f97316",
    critical: "#ef4444",
  };
  const color = riskColors[analysis.risk_level] || "#6b7280";

  return (
    <motion.div
      initial={{ opacity: 0, x: 16 }}
      animate={{ opacity: 1, x: 0 }}
      className="p-3 rounded-lg border bg-white/[0.02]"
      style={{ borderColor: `${color}30` }}
    >
      <div className="flex items-center justify-between mb-2">
        <span className="text-[10px] text-gray-500">Turn {turnNumber}</span>
        <span
          className="text-[10px] font-semibold px-2 py-0.5 rounded-full"
          style={{ background: `${color}15`, color, border: `1px solid ${color}30` }}
        >
          {analysis.risk_level.toUpperCase()}
        </span>
      </div>
      {analysis.tactic_detected && (
        <div className="flex items-center gap-1.5 mb-1.5">
          <AlertTriangle className="h-3 w-3" style={{ color }} />
          <span className="text-xs font-medium text-gray-200">
            {analysis.tactic_detected}
          </span>
        </div>
      )}
      {analysis.tactic_description && (
        <p className="text-xs text-gray-400 mb-1.5">{analysis.tactic_description}</p>
      )}
      <p className="text-xs text-gray-500">{analysis.explanation}</p>
      <div className="mt-2 flex items-center gap-2">
        <span className="text-[10px] text-gray-600">Confidence:</span>
        <div className="flex-1 h-1.5 bg-white/[0.06] rounded-full overflow-hidden">
          <motion.div
            initial={{ width: 0 }}
            animate={{ width: `${analysis.confidence * 100}%` }}
            transition={{ duration: 0.6 }}
            className="h-full rounded-full"
            style={{ background: color }}
          />
        </div>
        <span className="text-[10px] font-medium" style={{ color }}>
          {Math.round(analysis.confidence * 100)}%
        </span>
      </div>
    </motion.div>
  );
}

export default function SimulatePage() {
  const [phase, setPhase] = useState<SimPhase>("select");
  const [scenarios, setScenarios] = useState<ScenarioInfo[]>([]);
  const [simulationId, setSimulationId] = useState<string | null>(null);
  const [scenarioType, setScenarioType] = useState<string>("");
  const [scenarioDesc, setScenarioDesc] = useState<string>("");
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [analyses, setAnalyses] = useState<TurnAnalysis[]>([]);
  const [userInput, setUserInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [debrief, setDebrief] = useState<DebriefResponse | null>(null);
  const [interventionTriggered, setInterventionTriggered] = useState(false);

  const chatEndRef = useRef<HTMLDivElement>(null);
  const analysisEndRef = useRef<HTMLDivElement>(null);

  // Load scenarios from API
  useEffect(() => {
    async function load() {
      try {
        const data = await getScenarios();
        setScenarios(data);
      } catch (err) {
        console.error("Failed to load scenarios:", err);
      }
    }
    load();
  }, []);

  // Auto-scroll chat and analysis
  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  useEffect(() => {
    analysisEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [analyses]);

  const handleStartSimulation = async (scenario: ScenarioInfo) => {
    setLoading(true);
    try {
      const response = await startSimulation(scenario.name);
      setSimulationId(response.simulation_id);
      setScenarioType(response.scenario_type);
      setScenarioDesc(response.scenario_description);
      setMessages([
        {
          role: "scammer",
          content: response.first_turn.scammer_message,
          analysis: response.first_turn.analysis,
          turnNumber: 1,
        },
      ]);
      setAnalyses([response.first_turn.analysis]);
      setPhase("active");
    } catch (err) {
      console.error("Failed to start simulation:", err);
    } finally {
      setLoading(false);
    }
  };

  const handleSendMessage = async () => {
    if (!userInput.trim() || !simulationId || loading) return;

    const userMsg: ChatMessage = {
      role: "user",
      content: userInput.trim(),
      turnNumber: messages.length + 1,
    };
    setMessages((prev) => [...prev, userMsg]);
    setUserInput("");
    setLoading(true);

    try {
      const response = await respondToSimulation(simulationId, userMsg.content);

      const scammerMsg: ChatMessage = {
        role: "scammer",
        content: response.scammer_message,
        analysis: response.analysis,
        turnNumber: response.turn_number,
      };

      setMessages((prev) => [...prev, scammerMsg]);
      setAnalyses((prev) => [...prev, response.analysis]);

      if (response.intervention_triggered) {
        setInterventionTriggered(true);
        // Auto-load debrief
        setTimeout(async () => {
          try {
            const debriefData = await getDebrief(simulationId);
            setDebrief(debriefData);
            setPhase("debrief");
          } catch {
            setPhase("debrief");
          }
        }, 2000);
      }

      if (response.simulation_status === "completed") {
        const debriefData = await getDebrief(simulationId);
        setDebrief(debriefData);
        setPhase("debrief");
      }
    } catch (err) {
      console.error("Failed to send message:", err);
    } finally {
      setLoading(false);
    }
  };

  const handleReset = () => {
    setPhase("select");
    setSimulationId(null);
    setMessages([]);
    setAnalyses([]);
    setDebrief(null);
    setInterventionTriggered(false);
  };

  return (
    <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8 py-8">
      {/* Header */}
      <motion.div initial={{ opacity: 0, y: -10 }} animate={{ opacity: 1, y: 0 }} className="mb-6">
        <div className="flex items-center gap-3 mb-2">
          <Swords className="h-6 w-6 text-orange-400" />
          <h1 className="text-2xl font-bold text-white">Scam Simulation Lab</h1>
        </div>
        <p className="text-gray-400 text-sm max-w-2xl">
          Experience a realistic AI-generated scam in a safe environment.
          Watch NETRA decode every psychological tactic in real-time.
          Build immunity through experience.
        </p>
      </motion.div>

      {/* Phase: Select Scenario */}
      {phase === "select" && (
        <div>
          <div className="flex items-center gap-2 mb-4">
            <Info className="h-4 w-4 text-cyan-400" />
            <span className="text-sm text-gray-400">
              Choose a scam scenario to simulate. All scenarios are based on real documented cases.
            </span>
          </div>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
            {scenarios.map((s, i) => (
              <ScenarioCard
                key={s.name}
                scenario={s}
                onSelect={() => handleStartSimulation(s)}
                index={i}
              />
            ))}
          </div>
          {loading && (
            <div className="flex items-center justify-center py-8">
              <Loader2 className="h-6 w-6 animate-spin text-orange-400" />
              <span className="ml-2 text-sm text-gray-400">Starting simulation...</span>
            </div>
          )}
        </div>
      )}

      {/* Phase: Active Simulation (Split Screen) */}
      {phase === "active" && (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6" style={{ height: "calc(100vh - 220px)" }}>
          {/* LEFT: Chat */}
          <div className="glass-card flex flex-col overflow-hidden">
            <div className="px-4 py-3 border-b border-white/[0.06] flex items-center justify-between">
              <div className="flex items-center gap-2">
                <div className="h-2 w-2 rounded-full bg-red-500 animate-pulse" />
                <span className="text-xs font-medium text-gray-300">
                  Scam Simulation — {scenarioType}
                </span>
              </div>
              <span className="text-[10px] text-gray-600">SIMULATED · NOT REAL</span>
            </div>

            {/* Messages */}
            <div className="flex-1 overflow-y-auto p-4 space-y-3">
              {messages.map((msg, i) => (
                <motion.div
                  key={i}
                  initial={{ opacity: 0, y: 8 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ duration: 0.3 }}
                  className={`flex ${msg.role === "user" ? "justify-end" : "justify-start"}`}
                >
                  <div
                    className={`max-w-[85%] rounded-2xl px-4 py-2.5 text-sm ${
                      msg.role === "user"
                        ? "bg-cyan-500/20 text-cyan-100 rounded-br-sm"
                        : "bg-white/[0.06] text-gray-200 rounded-bl-sm"
                    }`}
                  >
                    {msg.role === "scammer" && (
                      <span className="text-[10px] text-red-400 font-medium block mb-1">
                        🔴 Scammer
                      </span>
                    )}
                    <p className="leading-relaxed whitespace-pre-wrap">{msg.content}</p>
                  </div>
                </motion.div>
              ))}

              {loading && (
                <div className="flex justify-start">
                  <div className="bg-white/[0.06] rounded-2xl rounded-bl-sm px-4 py-3">
                    <div className="flex gap-1">
                      <div className="h-2 w-2 rounded-full bg-gray-500 typing-dot" />
                      <div className="h-2 w-2 rounded-full bg-gray-500 typing-dot" />
                      <div className="h-2 w-2 rounded-full bg-gray-500 typing-dot" />
                    </div>
                  </div>
                </div>
              )}

              <div ref={chatEndRef} />
            </div>

            {/* Intervention Banner */}
            <AnimatePresence>
              {interventionTriggered && (
                <motion.div
                  initial={{ height: 0, opacity: 0 }}
                  animate={{ height: "auto", opacity: 1 }}
                  className="px-4 py-3 bg-red-500/10 border-t border-red-500/30"
                >
                  <div className="flex items-center gap-2">
                    <ShieldAlert className="h-5 w-5 text-red-400" />
                    <span className="text-sm font-semibold text-red-400">
                      🛑 NETRA INTERVENTION — Scam Pattern Confirmed
                    </span>
                  </div>
                  <p className="text-xs text-gray-400 mt-1">
                    High-confidence scam detected. Loading debrief...
                  </p>
                </motion.div>
              )}
            </AnimatePresence>

            {/* Input */}
            {!interventionTriggered && (
              <div className="p-3 border-t border-white/[0.06]">
                <div className="flex gap-2">
                  <input
                    type="text"
                    value={userInput}
                    onChange={(e) => setUserInput(e.target.value)}
                    onKeyDown={(e) => e.key === "Enter" && handleSendMessage()}
                    placeholder="Type your response to the scammer..."
                    className="flex-1 px-4 py-2.5 bg-white/[0.03] border border-white/[0.06] rounded-xl text-sm text-gray-200 placeholder:text-gray-600 focus:outline-none focus:border-cyan-500/30"
                    disabled={loading}
                  />
                  <button
                    onClick={handleSendMessage}
                    disabled={loading || !userInput.trim()}
                    className="px-4 py-2.5 rounded-xl bg-gradient-to-r from-orange-500 to-red-600 text-white disabled:opacity-40 transition-all"
                  >
                    <Send className="h-4 w-4" />
                  </button>
                </div>
              </div>
            )}
          </div>

          {/* RIGHT: NETRA Analysis */}
          <div className="glass-card flex flex-col overflow-hidden">
            <div className="px-4 py-3 border-b border-white/[0.06] flex items-center gap-2">
              <Shield className="h-4 w-4 text-cyan-400" />
              <span className="text-xs font-medium text-gray-300">
                NETRA Real-time Analysis
              </span>
            </div>

            <div className="flex-1 overflow-y-auto p-4 space-y-3">
              {analyses.length === 0 ? (
                <div className="text-center py-12">
                  <Brain className="h-8 w-8 text-gray-700 mx-auto mb-3" />
                  <p className="text-sm text-gray-500">Analyzing conversation...</p>
                </div>
              ) : (
                analyses.map((a, i) => (
                  <AnalysisPanel key={i} analysis={a} turnNumber={i + 1} />
                ))
              )}
              <div ref={analysisEndRef} />
            </div>
          </div>
        </div>
      )}

      {/* Phase: Debrief */}
      {phase === "debrief" && (
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          className="max-w-3xl mx-auto"
        >
          <div className="glass-card p-8 space-y-6">
            <div className="text-center mb-6">
              <div className="inline-flex h-16 w-16 items-center justify-center rounded-2xl bg-gradient-to-br from-cyan-500 to-blue-600 mb-4">
                <BookOpen className="h-8 w-8 text-white" />
              </div>
              <h2 className="text-2xl font-bold text-white">Simulation Debrief</h2>
              <p className="text-sm text-gray-400 mt-1">
                {scenarioType} — {debrief?.total_turns || messages.length} turns
              </p>
            </div>

            {debrief && (
              <>
                <div className="p-4 rounded-xl bg-white/[0.03] border border-white/[0.04]">
                  <p className="text-sm text-gray-300 leading-relaxed">
                    {debrief.debrief_content}
                  </p>
                </div>

                {/* Tactics Summary */}
                {debrief.tactics_detected.length > 0 && (
                  <div>
                    <h3 className="text-sm font-semibold text-gray-300 mb-3 flex items-center gap-2">
                      <AlertTriangle className="h-4 w-4 text-orange-400" />
                      Tactics Detected
                    </h3>
                    <div className="flex flex-wrap gap-2">
                      {debrief.tactics_detected.map((t) => (
                        <span
                          key={t}
                          className="px-3 py-1.5 rounded-lg bg-orange-500/10 text-orange-400 text-xs font-medium border border-orange-500/20"
                        >
                          {t}
                        </span>
                      ))}
                    </div>
                  </div>
                )}

                {/* Key Lessons */}
                {debrief.key_lessons.length > 0 && (
                  <div>
                    <h3 className="text-sm font-semibold text-gray-300 mb-3 flex items-center gap-2">
                      <Brain className="h-4 w-4 text-cyan-400" />
                      Key Lessons
                    </h3>
                    <div className="space-y-2">
                      {debrief.key_lessons.map((lesson, i) => (
                        <div
                          key={i}
                          className="flex items-start gap-3 p-3 rounded-lg bg-cyan-500/5 border border-cyan-500/10"
                        >
                          <span className="flex h-5 w-5 items-center justify-center rounded-full bg-cyan-500/20 text-[10px] font-bold text-cyan-400 mt-0.5 shrink-0">
                            {i + 1}
                          </span>
                          <p className="text-sm text-gray-300">{lesson}</p>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {debrief.intervention_turn && (
                  <div className="p-4 rounded-xl bg-red-500/5 border border-red-500/15">
                    <p className="text-xs text-red-400">
                      ⚠️ NETRA triggered intervention at turn {debrief.intervention_turn}.
                      In a real scenario, you would have been alerted before any financial loss.
                    </p>
                  </div>
                )}
              </>
            )}

            {!debrief && (
              <div className="text-center py-8">
                <Loader2 className="h-6 w-6 animate-spin text-cyan-400 mx-auto" />
                <p className="text-sm text-gray-400 mt-2">Generating debrief...</p>
              </div>
            )}

            <div className="pt-4 border-t border-white/[0.04] flex justify-center">
              <button
                onClick={handleReset}
                className="px-6 py-2.5 rounded-xl bg-gradient-to-r from-cyan-500 to-blue-600 text-white text-sm font-medium hover:shadow-lg hover:shadow-cyan-500/25 transition-all"
              >
                Try Another Scenario
              </button>
            </div>
          </div>
        </motion.div>
      )}
    </div>
  );
}
