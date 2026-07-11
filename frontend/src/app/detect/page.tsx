"use client";

import { useState, useCallback } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  Search,
  AlertTriangle,
  Shield,
  Scale,
  Brain,
  Loader2,
  Clock,
  Cpu,
  FileDown,
  Link2,
  Users,
  ShieldAlert,
  Hash,
  ChevronDown,
  ChevronUp,
  Crosshair,
  Target,
  Network,
  Mic,
  MicOff,
} from "lucide-react";
import { analyzeText, analyzeImage, analyzeCounterfeit, getDossierUrl, getIntelligence } from "@/lib/api";
import type {
  DetectResponse,
  RiskLevel,
  KillChainStage,
  IntelligenceResponse,
} from "@/lib/types";
import { RISK_BG_CLASSES } from "@/lib/types";
import { useVoiceInput } from "@/hooks/use-voice-input";

// ---------- Kill Chain Stage Config ----------

const KILL_CHAIN_CONFIG: Record<
  string,
  { icon: string; color: string; glow: string }
> = {
  S1_CONTACT: { icon: "📡", color: "#3b82f6", glow: "rgba(59,130,246,0.3)" },
  S2_PRETEXT: { icon: "🎭", color: "#8b5cf6", glow: "rgba(139,92,246,0.3)" },
  S3_PRESSURE: { icon: "⚡", color: "#f97316", glow: "rgba(249,115,22,0.3)" },
  S4_ISOLATION: { icon: "🔒", color: "#ef4444", glow: "rgba(239,68,68,0.3)" },
  S5_EXTRACTION: {
    icon: "💰",
    color: "#dc2626",
    glow: "rgba(220,38,38,0.3)",
  },
  S6_PERSISTENCE: {
    icon: "🔄",
    color: "#9333ea",
    glow: "rgba(147,51,234,0.3)",
  },
};

// ---------- Confidence Gauge ----------

function ConfidenceGauge({ value }: { value: number }) {
  const percentage = Math.round(value * 100);
  const circumference = 2 * Math.PI * 45;
  const offset = circumference - value * circumference;

  const color =
    value >= 0.85
      ? "#ef4444"
      : value >= 0.65
        ? "#f97316"
        : value >= 0.4
          ? "#eab308"
          : "#22c55e";

  return (
    <div className="relative w-28 h-28 mx-auto flex-shrink-0">
      <svg viewBox="0 0 100 100" className="w-full h-full -rotate-90">
        <circle
          cx="50"
          cy="50"
          r="45"
          fill="none"
          stroke="rgba(255,255,255,0.06)"
          strokeWidth="6"
        />
        <circle
          cx="50"
          cy="50"
          r="45"
          fill="none"
          stroke={color}
          strokeWidth="6"
          strokeLinecap="round"
          strokeDasharray={circumference}
          strokeDashoffset={offset}
          style={{ filter: `drop-shadow(0 0 8px ${color}40)` }}
        />
      </svg>
      <div className="absolute inset-0 flex flex-col items-center justify-center">
        <span className="text-2xl font-bold text-white">{percentage}%</span>
        <span className="text-[10px] text-gray-400 mt-0.5">confidence</span>
      </div>
    </div>
  );
}

// ---------- Kill Chain Timeline ----------

function KillChainTimeline({ stages }: { stages: KillChainStage[] }) {
  const [expandedStage, setExpandedStage] = useState<string | null>(null);
  const detectedCount = stages.filter((s) => s.detected).length;

  return (
    <div className="space-y-3">
      <h3 className="text-sm font-semibold text-gray-300 flex items-center gap-2">
        <Crosshair className="h-4 w-4 text-cyan-400" />
        Scam Kill Chain™ ({detectedCount}/6 stages detected)
      </h3>

      {/* Timeline */}
      <div className="relative">
        {/* Connection line */}
        <div className="absolute left-5 top-6 bottom-6 w-0.5 bg-gradient-to-b from-blue-500/30 via-orange-500/30 to-red-500/30" />

        <div className="space-y-1">
          {stages.map((stage, i) => {
            const config = KILL_CHAIN_CONFIG[stage.stage] || {
              icon: "⬜",
              color: "#6b7280",
              glow: "transparent",
            };
            const isExpanded = expandedStage === stage.stage;

            return (
              <motion.div
                key={stage.stage}
                initial={{ opacity: 0, x: -10 }}
                animate={{ opacity: 1, x: 0 }}
                transition={{ delay: 0.08 * i }}
              >
                <button
                  onClick={() =>
                    setExpandedStage(isExpanded ? null : stage.stage)
                  }
                  className={`w-full flex items-center gap-3 p-2.5 rounded-lg transition-all text-left ${
                    stage.detected
                      ? "bg-white/[0.04] border border-white/[0.08] hover:bg-white/[0.06]"
                      : "opacity-40 hover:opacity-60"
                  }`}
                >
                  {/* Stage indicator */}
                  <div
                    className="relative z-10 w-10 h-10 rounded-xl flex items-center justify-center text-lg flex-shrink-0"
                    style={{
                      backgroundColor: stage.detected
                        ? `${config.color}20`
                        : "rgba(255,255,255,0.03)",
                      boxShadow: stage.detected
                        ? `0 0 12px ${config.glow}`
                        : "none",
                      border: stage.detected
                        ? `1px solid ${config.color}40`
                        : "1px solid rgba(255,255,255,0.06)",
                    }}
                  >
                    {config.icon}
                  </div>

                  {/* Stage info */}
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2">
                      <span className="text-xs font-bold text-gray-500">
                        {stage.stage.split("_")[0]}
                      </span>
                      <span
                        className={`text-sm font-medium ${stage.detected ? "text-gray-200" : "text-gray-600"}`}
                      >
                        {stage.stage_name}
                      </span>
                      {stage.detected && (
                        <span
                          className="text-[10px] px-1.5 py-0.5 rounded-full font-semibold"
                          style={{
                            backgroundColor: `${config.color}20`,
                            color: config.color,
                          }}
                        >
                          {stage.severity.toUpperCase()}
                        </span>
                      )}
                    </div>
                  </div>

                  {stage.detected && stage.evidence && (
                    <div className="text-gray-600">
                      {isExpanded ? (
                        <ChevronUp className="h-3.5 w-3.5" />
                      ) : (
                        <ChevronDown className="h-3.5 w-3.5" />
                      )}
                    </div>
                  )}
                </button>

                {/* Expanded evidence */}
                <AnimatePresence>
                  {isExpanded && stage.evidence && (
                    <motion.div
                      initial={{ height: 0, opacity: 0 }}
                      animate={{ height: "auto", opacity: 1 }}
                      exit={{ height: 0, opacity: 0 }}
                      className="overflow-hidden"
                    >
                      <div className="ml-[52px] py-2 px-4">
                        {/* Evidence quote */}
                        <div className="bg-white/[0.02] rounded-lg p-3 border border-white/[0.04] space-y-2">
                          <p className="text-xs text-gray-400 italic leading-relaxed">
                            &quot;{stage.evidence}&quot;
                          </p>
                          {/* Confidence bar */}
                          {stage.confidence != null && (
                            <div className="flex items-center gap-2 pt-1">
                              <span className="text-[10px] text-gray-600 w-16">Confidence</span>
                              <div className="flex-1 h-1.5 rounded-full bg-white/[0.04] overflow-hidden">
                                <motion.div
                                  initial={{ width: 0 }}
                                  animate={{ width: `${stage.confidence * 100}%` }}
                                  transition={{ duration: 0.6, delay: 0.1 }}
                                  className="h-full rounded-full"
                                  style={{ backgroundColor: config.color }}
                                />
                              </div>
                              <span className="text-[10px] font-mono" style={{ color: config.color }}>
                                {(stage.confidence * 100).toFixed(0)}%
                              </span>
                            </div>
                          )}
                          {/* Tactics */}
                          {stage.tactics && stage.tactics.length > 0 && (
                            <div className="flex flex-wrap gap-1 pt-1">
                              {stage.tactics.map((t: string, ti: number) => (
                                <span
                                  key={ti}
                                  className="text-[9px] px-1.5 py-0.5 rounded bg-white/[0.04] text-gray-500 border border-white/[0.04]"
                                >
                                  {t}
                                </span>
                              ))}
                            </div>
                          )}
                        </div>
                      </div>
                    </motion.div>
                  )}
                </AnimatePresence>
              </motion.div>
            );
          })}
        </div>
      </div>
    </div>
  );
}

// ---------- Victim Vulnerability Bar ----------

function VulnerabilityBar({
  score,
  factors,
}: {
  score: number;
  factors: string[];
}) {
  const percentage = Math.round(score * 100);
  const color =
    score >= 0.7 ? "#ef4444" : score >= 0.4 ? "#f97316" : "#22c55e";

  return (
    <div className="space-y-2">
      <h3 className="text-sm font-semibold text-gray-300 flex items-center gap-2">
        <ShieldAlert className="h-4 w-4 text-orange-400" />
        Victim Vulnerability Assessment
      </h3>
      <div className="p-3 rounded-lg bg-white/[0.02] border border-white/[0.04]">
        <div className="flex items-center justify-between mb-2">
          <span className="text-xs text-gray-400">Vulnerability Score</span>
          <span className="text-sm font-bold" style={{ color }}>
            {percentage}%
          </span>
        </div>
        <div className="w-full h-2 rounded-full bg-white/[0.06]">
          <motion.div
            initial={{ width: 0 }}
            animate={{ width: `${percentage}%` }}
            transition={{ duration: 1, ease: "easeOut" }}
            className="h-full rounded-full"
            style={{
              background: `linear-gradient(90deg, ${color}80, ${color})`,
              boxShadow: `0 0 8px ${color}40`,
            }}
          />
        </div>
        {factors.length > 0 && (
          <div className="mt-2 flex flex-wrap gap-1">
            {factors.map((factor, i) => (
              <span
                key={i}
                className="text-[10px] px-2 py-0.5 rounded-full bg-white/[0.04] text-gray-400 border border-white/[0.06]"
              >
                {factor}
              </span>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

// ---------- Intelligence Panel ----------

function IntelligencePanel({ caseId }: { caseId: string }) {
  const [data, setData] = useState<IntelligenceResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [expanded, setExpanded] = useState(false);

  const handleLoad = async () => {
    if (data) {
      setExpanded(!expanded);
      return;
    }
    setLoading(true);
    try {
      const result = await getIntelligence(caseId);
      setData(result);
      setExpanded(true);
    } catch {
      // No related cases is fine
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="space-y-2">
      <button
        onClick={handleLoad}
        className="w-full flex items-center justify-between p-3 rounded-lg bg-white/[0.02] border border-white/[0.04] hover:bg-white/[0.04] transition-all"
      >
        <div className="flex items-center gap-2">
          <Link2 className="h-4 w-4 text-violet-400" />
          <span className="text-sm font-semibold text-gray-300">
            Cross-Case Intelligence
          </span>
          {data && (
            <span className="text-[10px] px-1.5 py-0.5 rounded-full bg-violet-500/20 text-violet-400 font-semibold">
              {data.total_linked_cases} linked
            </span>
          )}
        </div>
        {loading ? (
          <Loader2 className="h-3.5 w-3.5 text-gray-500 animate-spin" />
        ) : (
          <ChevronDown
            className={`h-3.5 w-3.5 text-gray-500 transition-transform ${expanded ? "rotate-180" : ""}`}
          />
        )}
      </button>

      <AnimatePresence>
        {expanded && data && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: "auto", opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            className="overflow-hidden"
          >
            <div className="space-y-2 pl-2">
              {/* Syndicate indicators */}
              {data.syndicate_indicators.length > 0 && (
                <div className="p-2.5 rounded-lg bg-red-500/5 border border-red-500/10">
                  <div className="flex items-center gap-1.5 mb-1">
                    <Users className="h-3.5 w-3.5 text-red-400" />
                    <span className="text-xs font-semibold text-red-400">
                      Syndicate Indicators
                    </span>
                  </div>
                  {data.syndicate_indicators.map((indicator, i) => (
                    <p key={i} className="text-xs text-gray-400">
                      • {indicator}
                    </p>
                  ))}
                </div>
              )}

              {/* Related cases */}
              {data.related_cases.map((rc, i) => (
                <div
                  key={rc.id}
                  className="p-2.5 rounded-lg bg-white/[0.02] border border-white/[0.04]"
                >
                  <div className="flex items-center justify-between mb-1">
                    <span className="text-xs font-medium text-gray-300">
                      {rc.scam_type || "Unknown"}
                    </span>
                    <span className="text-[10px] px-1.5 py-0.5 rounded-full bg-violet-500/20 text-violet-400 font-bold">
                      {Math.round(rc.similarity_score * 100)}% match
                    </span>
                  </div>
                  <p className="text-[10px] text-gray-500 mb-1">
                    {rc.similarity_reason}
                  </p>
                  <p className="text-[10px] text-gray-600 truncate">
                    {rc.input_preview}
                  </p>
                </div>
              ))}

              {data.related_cases.length === 0 && (
                <p className="text-xs text-gray-600 p-2">
                  No related cases found yet. Analyze more messages to build the
                  intelligence network.
                </p>
              )}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}

// ---------- Tactic Card ----------

function TacticCard({
  name,
  description,
  confidence,
  index,
}: {
  name: string;
  description: string;
  confidence: number;
  index: number;
}) {
  return (
    <motion.div
      initial={{ opacity: 0, x: -10 }}
      animate={{ opacity: 1, x: 0 }}
      transition={{ delay: 0.1 * index }}
      className="flex items-start gap-3 p-3 rounded-lg bg-white/[0.02] border border-white/[0.04]"
    >
      <div className="mt-0.5">
        <Brain className="h-4 w-4 text-violet-400" />
      </div>
      <div className="flex-1">
        <div className="flex items-center justify-between">
          <span className="text-sm font-medium text-gray-200">{name}</span>
          <span className="text-xs text-gray-500">
            {Math.round(confidence * 100)}%
          </span>
        </div>
        <p className="text-xs text-gray-400 mt-1">{description}</p>
      </div>
    </motion.div>
  );
}

// ---------- Legal Card ----------

function LegalCard({
  law,
  section,
  title,
  punishment,
  index,
}: {
  code: string;
  law: string;
  section: string;
  title: string;
  punishment: string | null;
  index: number;
}) {
  return (
    <motion.div
      initial={{ opacity: 0, x: -10 }}
      animate={{ opacity: 1, x: 0 }}
      transition={{ delay: 0.1 * index }}
      className="p-3 rounded-lg bg-white/[0.02] border border-white/[0.04]"
    >
      <div className="flex items-center gap-2 mb-1">
        <Scale className="h-3.5 w-3.5 text-cyan-400" />
        <span className="text-xs font-semibold text-cyan-400">
          {law} § {section}
        </span>
      </div>
      <p className="text-sm font-medium text-gray-200">{title}</p>
      {punishment && (
        <p className="text-xs text-gray-500 mt-1">Punishment: {punishment}</p>
      )}
    </motion.div>
  );
}

// ---------- Main Page ----------

export default function DetectPage() {
  const [input, setInput] = useState("");
  const [inputType, setInputType] = useState<"text" | "transcript" | "url">(
    "text",
  );
  const [result, setResult] = useState<DetectResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [mode, setMode] = useState<"text" | "screenshot" | "counterfeit">("text");
  const [imagePreview, setImagePreview] = useState<string | null>(null);
  const [imageBase64, setImageBase64] = useState<string | null>(null);
  const [imageMime, setImageMime] = useState<string>("image/jpeg");
  const [counterfeitResult, setCounterfeitResult] = useState<Awaited<ReturnType<typeof analyzeCounterfeit>> | null>(null);
  const [extractedText, setExtractedText] = useState<string | null>(null);

  // Voice input
  const handleVoiceTranscript = useCallback((text: string) => {
    setInput((prev) => prev ? prev + " " + text : text);
  }, []);
  const { isListening, isSupported: voiceSupported, interimTranscript, toggleListening } = useVoiceInput(handleVoiceTranscript);

  const handleAnalyze = async () => {
    if (!input.trim() || input.trim().length < 5) return;

    setLoading(true);
    setError(null);
    setResult(null);

    try {
      const response = await analyzeText({
        text: input.trim(),
        input_type: inputType,
      });
      setResult(response);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Analysis failed");
    } finally {
      setLoading(false);
    }
  };

  const handleImageUpload = (file: File) => {
    if (file.size > 10 * 1024 * 1024) {
      setError("Image too large (max 10MB)");
      return;
    }
    const reader = new FileReader();
    reader.onload = (e) => {
      const dataUrl = e.target?.result as string;
      setImagePreview(dataUrl);
      // Extract base64 from data URL
      const base64 = dataUrl.split(",")[1];
      setImageBase64(base64);
      setImageMime(file.type || "image/jpeg");
      setError(null);
    };
    reader.readAsDataURL(file);
  };

  const handleImageAnalyze = async () => {
    if (!imageBase64) return;
    setLoading(true);
    setError(null);
    setResult(null);
    setExtractedText(null);

    try {
      const response = await analyzeImage(imageBase64, imageMime);
      setExtractedText(response.extracted_text || response.image_description);
      if (response.detection_result) {
        setResult(response.detection_result);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Image analysis failed");
    } finally {
      setLoading(false);
    }
  };

  const handleCounterfeitAnalyze = async () => {
    if (!imageBase64) return;
    setLoading(true);
    setError(null);
    setCounterfeitResult(null);

    try {
      const response = await analyzeCounterfeit(imageBase64, imageMime);
      setCounterfeitResult(response);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Counterfeit analysis failed");
    } finally {
      setLoading(false);
    }
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    const file = e.dataTransfer.files[0];
    if (file && file.type.startsWith("image/")) {
      handleImageUpload(file);
    }
  };

  return (
    <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8 py-8">
      {/* Header */}
      <motion.div
        initial={{ opacity: 0, y: -10 }}
        animate={{ opacity: 1, y: 0 }}
        className="mb-8"
      >
        <div className="flex items-center gap-3 mb-2">
          <Search className="h-6 w-6 text-cyan-400" />
          <h1 className="text-2xl font-bold text-white">Detect</h1>
        </div>
        <p className="text-gray-400 text-sm max-w-2xl">
          Paste a suspicious message, upload a screenshot, or scan a banknote.
          NETRA decomposes it through a 6-stage Kill Chain, detects manipulation
          tactics, maps legal sections, and generates forensic evidence.
        </p>
      </motion.div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Input Panel */}
        <motion.div
          initial={{ opacity: 0, x: -20 }}
          animate={{ opacity: 1, x: 0 }}
          className="glass-card p-6 space-y-4"
        >
          {/* Mode selector */}
          <div className="flex gap-2">
            {([
              { key: "text" as const, label: "📝 Message", desc: "Paste text" },
              { key: "screenshot" as const, label: "📸 Screenshot", desc: "Upload image" },
              { key: "counterfeit" as const, label: "💵 Counterfeit", desc: "Scan note" },
            ]).map(({ key, label }) => (
              <button
                key={key}
                onClick={() => { setMode(key); setError(null); setResult(null); setCounterfeitResult(null); setExtractedText(null); }}
                className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-all ${
                  mode === key
                    ? "bg-cyan-500/20 text-cyan-400 border border-cyan-500/30"
                    : "bg-white/[0.04] text-gray-400 border border-white/[0.06] hover:bg-white/[0.08]"
                }`}
              >
                {label}
              </button>
            ))}
          </div>

          {/* TEXT MODE */}
          {mode === "text" && (
            <>
              {/* Input type sub-selector */}
              <div className="flex gap-2">
                {(["text", "transcript", "url"] as const).map((type) => (
                  <button
                    key={type}
                    onClick={() => setInputType(type)}
                    className={`px-3 py-1 rounded-lg text-[11px] font-medium transition-all ${
                      inputType === type
                        ? "bg-white/[0.08] text-gray-200 border border-white/[0.12]"
                        : "bg-white/[0.02] text-gray-500 border border-white/[0.04] hover:bg-white/[0.06]"
                    }`}
                  >
                    {type === "text" ? "Message" : type === "transcript" ? "Call Transcript" : "URL"}
                  </button>
                ))}
              </div>

              <textarea
                value={input}
                onChange={(e) => setInput(e.target.value)}
                placeholder={
                  inputType === "text"
                    ? "Paste suspicious WhatsApp/SMS message here..."
                    : inputType === "transcript"
                      ? "Paste the call transcript here..."
                      : "Paste the suspicious URL here..."
                }
                className="w-full h-56 bg-white/[0.03] border border-white/[0.06] rounded-xl p-4 text-sm text-gray-200 placeholder:text-gray-600 resize-none focus:outline-none focus:border-cyan-500/40 focus:ring-1 focus:ring-cyan-500/20 transition-all font-[family-name:var(--font-mono)]"
              />

              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <span className="text-xs text-gray-600">
                    {input.length} characters
                  </span>
                  {voiceSupported && (
                    <button
                      onClick={toggleListening}
                      className={`flex items-center gap-1.5 px-2.5 py-1 rounded-lg text-xs font-medium transition-all ${
                        isListening
                          ? "bg-red-500/20 text-red-400 border border-red-500/30 animate-pulse"
                          : "bg-white/[0.04] text-gray-400 border border-white/[0.06] hover:bg-white/[0.08]"
                      }`}
                      title={isListening ? "Stop listening" : "Start voice input"}
                    >
                      {isListening ? (
                        <><MicOff className="h-3 w-3" /> Stop</>
                      ) : (
                        <><Mic className="h-3 w-3" /> Voice</>
                      )}
                    </button>
                  )}
                </div>
                <button
                  onClick={handleAnalyze}
                  disabled={loading || input.trim().length < 5}
                  className="flex items-center gap-2 px-5 py-2.5 rounded-xl bg-gradient-to-r from-cyan-500 to-blue-600 text-white text-sm font-medium hover:shadow-lg hover:shadow-cyan-500/25 disabled:opacity-40 disabled:cursor-not-allowed transition-all"
                >
                  {loading ? (
                    <>
                      <Loader2 className="h-4 w-4 animate-spin" />
                      Analyzing...
                    </>
                  ) : (
                    <>
                      <Shield className="h-4 w-4" />
                      Analyze
                    </>
                  )}
                </button>
              </div>

              {/* Interim voice transcript */}
              {isListening && interimTranscript && (
                <div className="p-2 rounded-lg bg-red-500/5 border border-red-500/10">
                  <p className="text-xs text-red-300 italic">
                    🎙️ {interimTranscript}
                  </p>
                </div>
              )}
            </>
          )}

          {/* SCREENSHOT / COUNTERFEIT MODE */}
          {(mode === "screenshot" || mode === "counterfeit") && (
            <>
              {/* Drop zone */}
              <div
                onDrop={handleDrop}
                onDragOver={(e) => e.preventDefault()}
                className="relative w-full h-56 border-2 border-dashed border-white/[0.08] rounded-xl flex flex-col items-center justify-center cursor-pointer hover:border-cyan-500/30 transition-all overflow-hidden"
                onClick={() => document.getElementById("image-upload")?.click()}
              >
                {imagePreview ? (
                  <img
                    src={imagePreview}
                    alt="Preview"
                    className="w-full h-full object-contain rounded-lg"
                  />
                ) : (
                  <div className="text-center p-6">
                    <div className="text-3xl mb-2">
                      {mode === "screenshot" ? "📸" : "💵"}
                    </div>
                    <p className="text-sm text-gray-400 mb-1">
                      {mode === "screenshot"
                        ? "Drop a screenshot or click to upload"
                        : "Drop a banknote photo or click to upload"}
                    </p>
                    <p className="text-xs text-gray-600">
                      {mode === "screenshot"
                        ? "WhatsApp, SMS, email, social media screenshots"
                        : "₹100, ₹200, ₹500, ₹2000 notes — both sides if possible"}
                    </p>
                  </div>
                )}
                <input
                  id="image-upload"
                  type="file"
                  accept="image/*"
                  className="hidden"
                  onChange={(e) => {
                    const file = e.target.files?.[0];
                    if (file) handleImageUpload(file);
                  }}
                />
              </div>

              {imagePreview && (
                <div className="flex items-center justify-between">
                  <button
                    onClick={() => { setImagePreview(null); setImageBase64(null); }}
                    className="text-xs text-gray-500 hover:text-gray-300 transition-colors"
                  >
                    Clear image
                  </button>
                  <button
                    onClick={mode === "screenshot" ? handleImageAnalyze : handleCounterfeitAnalyze}
                    disabled={loading || !imageBase64}
                    className="flex items-center gap-2 px-5 py-2.5 rounded-xl bg-gradient-to-r from-cyan-500 to-blue-600 text-white text-sm font-medium hover:shadow-lg hover:shadow-cyan-500/25 disabled:opacity-40 disabled:cursor-not-allowed transition-all"
                  >
                    {loading ? (
                      <>
                        <Loader2 className="h-4 w-4 animate-spin" />
                        {mode === "screenshot" ? "Extracting text..." : "Analyzing note..."}
                      </>
                    ) : (
                      <>
                        <Shield className="h-4 w-4" />
                        {mode === "screenshot" ? "Extract & Analyze" : "Verify Authenticity"}
                      </>
                    )}
                  </button>
                </div>
              )}

              {/* Extracted text display (screenshot mode) */}
              {extractedText && mode === "screenshot" && (
                <div className="p-3 rounded-lg bg-white/[0.02] border border-white/[0.04]">
                  <p className="text-xs text-gray-500 mb-1">Extracted Text:</p>
                  <p className="text-sm text-gray-300 font-mono whitespace-pre-wrap max-h-32 overflow-y-auto">
                    {extractedText}
                  </p>
                </div>
              )}
            </>
          )}

          {error && (
            <div className="p-3 rounded-lg bg-red-500/10 border border-red-500/20 text-sm text-red-400">
              {error}
            </div>
          )}

          {/* Counterfeit Result Panel */}
          {counterfeitResult && mode === "counterfeit" && (
            <motion.div
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              className="space-y-3"
            >
              {/* Verdict */}
              <div className={`p-4 rounded-xl border ${
                counterfeitResult.verdict === "genuine"
                  ? "bg-green-500/10 border-green-500/20"
                  : counterfeitResult.verdict === "counterfeit"
                    ? "bg-red-500/10 border-red-500/20"
                    : counterfeitResult.verdict === "suspect"
                      ? "bg-orange-500/10 border-orange-500/20"
                      : "bg-gray-500/10 border-gray-500/20"
              }`}>
                <div className="flex items-center justify-between mb-2">
                  <span className={`text-lg font-bold uppercase ${
                    counterfeitResult.verdict === "genuine" ? "text-green-400" :
                    counterfeitResult.verdict === "counterfeit" ? "text-red-400" :
                    counterfeitResult.verdict === "suspect" ? "text-orange-400" :
                    "text-gray-400"
                  }`}>
                    {counterfeitResult.verdict === "genuine" ? "✅ " : counterfeitResult.verdict === "counterfeit" ? "🚨 " : "⚠️ "}
                    {counterfeitResult.verdict}
                  </span>
                  <span className="text-sm text-gray-400">
                    {Math.round(counterfeitResult.confidence * 100)}% confidence
                  </span>
                </div>
                {counterfeitResult.denomination_detected && (
                  <p className="text-sm text-gray-300 mb-2">
                    Denomination: {counterfeitResult.denomination_detected}
                  </p>
                )}
                <p className="text-sm text-gray-400">{counterfeitResult.overall_assessment}</p>
              </div>

              {/* Security Features */}
              <div className="space-y-1.5">
                <h4 className="text-xs font-semibold text-gray-400">Security Features</h4>
                {counterfeitResult.security_features.map((feature, i) => (
                  <div
                    key={i}
                    className="flex items-center justify-between p-2 rounded-lg bg-white/[0.02] border border-white/[0.04]"
                  >
                    <span className="text-xs text-gray-300">{feature.feature_name}</span>
                    <span className={`text-xs font-medium px-2 py-0.5 rounded-full ${
                      feature.status === "pass" ? "bg-green-500/15 text-green-400" :
                      feature.status === "fail" ? "bg-red-500/15 text-red-400" :
                      feature.status === "uncertain" ? "bg-yellow-500/15 text-yellow-400" :
                      "bg-gray-500/15 text-gray-400"
                    }`}>
                      {feature.status}
                    </span>
                  </div>
                ))}
              </div>

              {/* RBI Guidelines */}
              <div className="p-3 rounded-lg bg-blue-500/5 border border-blue-500/15">
                <p className="text-xs font-semibold text-blue-400 mb-1">📋 RBI Guidelines</p>
                <p className="text-xs text-gray-400">{counterfeitResult.rbi_guidelines}</p>
              </div>

              {/* Evidence */}
              <div className="text-[10px] text-gray-600 font-mono">
                Hash: {counterfeitResult.evidence_hash} · {counterfeitResult.processing_time_ms}ms
              </div>
            </motion.div>
          )}
        </motion.div>

        {/* Results Panel */}
        <AnimatePresence mode="wait">
          {result ? (
            <motion.div
              key="result"
              initial={{ opacity: 0, x: 20 }}
              animate={{ opacity: 1, x: 0 }}
              exit={{ opacity: 0, x: 20 }}
              className="glass-card p-6 space-y-5 max-h-[calc(100vh-200px)] overflow-y-auto"
            >
              {/* Scam Type + Risk + Confidence */}
              <div className="flex items-start justify-between">
                <div>
                  <span
                    className={`inline-block px-3 py-1 rounded-full text-xs font-semibold ${
                      RISK_BG_CLASSES[
                        (result.risk_level as RiskLevel) || "unknown"
                      ]
                    }`}
                  >
                    {result.risk_level.toUpperCase()}
                  </span>
                  <h2 className="text-xl font-bold text-white mt-3">
                    {result.scam_type || "Not a Scam"}
                  </h2>
                  <p className="text-xs text-gray-500 mt-1">
                    Language: {result.language} · Model: {result.model_used}
                  </p>
                </div>
                <ConfidenceGauge value={result.confidence} />
              </div>

              {/* AI Reasoning */}
              <div className="space-y-2">
                <h3 className="text-sm font-semibold text-gray-300 flex items-center gap-2">
                  <Brain className="h-4 w-4 text-cyan-400" />
                  AI Reasoning
                </h3>
                <p className="text-sm text-gray-400 leading-relaxed bg-white/[0.02] rounded-lg p-3 border border-white/[0.04]">
                  {result.ai_reasoning}
                </p>
              </div>

              {/* ★ KILL CHAIN TIMELINE */}
              {result.kill_chain && result.kill_chain.length > 0 && (
                <KillChainTimeline stages={result.kill_chain} />
              )}

              {/* ★ VICTIM VULNERABILITY */}
              {result.victim_vulnerability_score > 0 && (
                <VulnerabilityBar
                  score={result.victim_vulnerability_score}
                  factors={result.victim_vulnerability_factors || []}
                />
              )}

              {/* Tactics Detected */}
              {result.tactics_detected.length > 0 && (
                <div className="space-y-2">
                  <h3 className="text-sm font-semibold text-gray-300 flex items-center gap-2">
                    <AlertTriangle className="h-4 w-4 text-orange-400" />
                    Psychological Tactics ({result.tactics_detected.length})
                  </h3>
                  <div className="space-y-2">
                    {result.tactics_detected.map((tactic, i) => (
                      <TacticCard key={i} {...tactic} index={i} />
                    ))}
                  </div>
                </div>
              )}

              {/* Legal Sections */}
              {result.legal_sections.length > 0 && (
                <div className="space-y-2">
                  <h3 className="text-sm font-semibold text-gray-300 flex items-center gap-2">
                    <Scale className="h-4 w-4 text-cyan-400" />
                    Applicable Legal Sections ({result.legal_sections.length})
                  </h3>
                  <div className="space-y-2">
                    {result.legal_sections.map((section, i) => (
                      <LegalCard key={section.code} {...section} index={i} />
                    ))}
                  </div>
                </div>
              )}

              {/* ★ CROSS-CASE INTELLIGENCE */}
              <IntelligencePanel caseId={result.id} />

              {/* Evidence Hash */}
              {result.evidence_hash && (
                <div className="p-3 rounded-lg bg-white/[0.02] border border-white/[0.04]">
                  <div className="flex items-center gap-2 mb-1">
                    <Hash className="h-3.5 w-3.5 text-emerald-400" />
                    <span className="text-xs font-semibold text-emerald-400">
                      Evidence Hash (SHA-256)
                    </span>
                  </div>
                  <p className="text-[10px] text-gray-500 font-mono break-all">
                    {result.evidence_hash}
                  </p>
                </div>
              )}

              {/* ★ EXTRACTED ENTITIES & GRAPH INTELLIGENCE */}
              {result.graph_intel && result.graph_intel.entities_extracted.length > 0 && (
                <div className="space-y-2">
                  <h3 className="text-sm font-semibold text-gray-300 flex items-center gap-2">
                    <Network className="h-4 w-4 text-violet-400" />
                    Extracted Entities ({result.graph_intel.entities_extracted.length})
                  </h3>
                  <div className="p-3 rounded-lg bg-white/[0.02] border border-white/[0.04] space-y-3">
                    {/* Graph summary badge */}
                    <div className="flex items-center gap-3 text-xs">
                      <span className="px-2 py-1 rounded-full bg-violet-500/15 text-violet-400 border border-violet-500/20">
                        {result.graph_intel.nodes_created} nodes created
                      </span>
                      <span className="px-2 py-1 rounded-full bg-cyan-500/15 text-cyan-400 border border-cyan-500/20">
                        {result.graph_intel.edges_created} edges created
                      </span>
                      {result.graph_intel.nodes_linked > 0 && (
                        <span className="px-2 py-1 rounded-full bg-orange-500/15 text-orange-400 border border-orange-500/20">
                          {result.graph_intel.nodes_linked} linked to existing
                        </span>
                      )}
                    </div>

                    {/* Entity list */}
                    <div className="flex flex-wrap gap-2">
                      {result.graph_intel.entities_extracted.map((entity, i) => {
                        const typeColors: Record<string, string> = {
                          phone: "bg-blue-500/15 text-blue-400 border-blue-500/20",
                          upi_id: "bg-violet-500/15 text-violet-400 border-violet-500/20",
                          bank_account: "bg-amber-500/15 text-amber-400 border-amber-500/20",
                          email: "bg-teal-500/15 text-teal-400 border-teal-500/20",
                          url: "bg-purple-500/15 text-purple-400 border-purple-500/20",
                          person: "bg-rose-500/15 text-rose-400 border-rose-500/20",
                          organization: "bg-indigo-500/15 text-indigo-400 border-indigo-500/20",
                          location: "bg-emerald-500/15 text-emerald-400 border-emerald-500/20",
                          amount: "bg-yellow-500/15 text-yellow-400 border-yellow-500/20",
                          designation: "bg-pink-500/15 text-pink-400 border-pink-500/20",
                        };
                        const typeIcons: Record<string, string> = {
                          phone: "📱", upi_id: "💳", bank_account: "🏦",
                          email: "📧", url: "🔗", person: "🕵️",
                          organization: "🏢", location: "📍", amount: "💰",
                          designation: "🏷️", ifsc: "🏦", aadhaar: "🪪", pan: "🪪",
                        };
                        const colorClass = typeColors[entity.entity_type] || "bg-gray-500/15 text-gray-400 border-gray-500/20";
                        const icon = typeIcons[entity.entity_type] || "📌";
                        return (
                          <motion.span
                            key={i}
                            initial={{ opacity: 0, scale: 0.8 }}
                            animate={{ opacity: 1, scale: 1 }}
                            transition={{ delay: i * 0.05 }}
                            className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-lg text-xs border ${colorClass}`}
                          >
                            <span>{icon}</span>
                            <span className="font-mono">{entity.value}</span>
                            <span className="opacity-50 text-[9px]">
                              {entity.source === "llm" ? "AI" : ""}
                            </span>
                          </motion.span>
                        );
                      })}
                    </div>

                    {/* View in Graph link */}
                    <a
                      href="/investigate"
                      className="inline-flex items-center gap-1.5 text-xs text-violet-400 hover:text-violet-300 transition-colors mt-1"
                    >
                      <Network className="h-3 w-3" />
                      View in Fraud Network Graph →
                    </a>
                  </div>
                </div>
              )}

              {/* Action Bar: Dossier Download + Processing Info */}
              <div className="pt-3 border-t border-white/[0.04] flex items-center justify-between">
                <div className="flex items-center gap-4 text-xs text-gray-500">
                  <span className="flex items-center gap-1">
                    <Clock className="h-3 w-3" />
                    {result.processing_time_ms}ms
                  </span>
                  <span className="flex items-center gap-1">
                    <Cpu className="h-3 w-3" />
                    {result.model_used}
                  </span>
                </div>

                {/* ★ FORENSIC DOSSIER DOWNLOAD */}
                <a
                  href={getDossierUrl(result.id)}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="flex items-center gap-2 px-4 py-2 rounded-lg bg-gradient-to-r from-emerald-600 to-cyan-600 text-white text-xs font-medium hover:shadow-lg hover:shadow-emerald-500/25 transition-all"
                >
                  <FileDown className="h-3.5 w-3.5" />
                  Forensic Dossier
                </a>
              </div>
            </motion.div>
          ) : (
            <motion.div
              key="empty"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              className="glass-card p-6 flex flex-col items-center justify-center text-center min-h-[400px]"
            >
              <div className="w-16 h-16 rounded-2xl bg-white/[0.04] flex items-center justify-center mb-4">
                <Shield className="h-8 w-8 text-gray-600" />
              </div>
              <h3 className="text-gray-400 font-medium mb-1">
                No analysis yet
              </h3>
              <p className="text-sm text-gray-600 max-w-xs">
                Paste a suspicious message on the left and click Analyze to
                see NETRA&apos;s Kill Chain decomposition, tactic detection,
                legal mapping, and forensic dossier generation.
              </p>
            </motion.div>
          )}
        </AnimatePresence>
      </div>
    </div>
  );
}
