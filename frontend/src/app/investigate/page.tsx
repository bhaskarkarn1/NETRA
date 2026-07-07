"use client";

import { useState, useCallback } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  Network,
  Search,
  Loader2,
  X,
  Phone,
  Building,
  CreditCard,
  User,
  MapPin,
} from "lucide-react";
import { searchNodes, getNetwork } from "@/lib/api";
import type { SearchResult, NetworkResponse, GraphNode } from "@/lib/types";
import { NODE_TYPE_COLORS } from "@/lib/types";
import { FraudGraph } from "@/components/graph/fraud-graph";

const NODE_ICONS: Record<string, React.ElementType> = {
  phone: Phone,
  bank_account: Building,
  upi_id: CreditCard,
  victim: User,
  location: MapPin,
};

export default function InvestigatePage() {
  const [query, setQuery] = useState("");
  const [searchResults, setSearchResults] = useState<SearchResult[]>([]);
  const [networkData, setNetworkData] = useState<NetworkResponse | null>(null);
  const [selectedNode, setSelectedNode] = useState<GraphNode | null>(null);
  const [searching, setSearching] = useState(false);
  const [loadingGraph, setLoadingGraph] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSearch = async () => {
    if (!query.trim() || query.trim().length < 2) return;
    setSearching(true);
    setError(null);
    setSearchResults([]);

    try {
      const results = await searchNodes(query.trim());
      setSearchResults(results);
      if (results.length === 0) {
        setError("No entities found matching your search.");
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Search failed");
    } finally {
      setSearching(false);
    }
  };

  const handleSelectNode = async (nodeId: string) => {
    setLoadingGraph(true);
    setError(null);

    try {
      const network = await getNetwork(nodeId, 2);
      setNetworkData(network);
      setSearchResults([]); // Hide search results
      // Find and set center node
      const center = network.nodes.find((n) => n.id === network.center_node_id);
      if (center) setSelectedNode(center);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load network");
    } finally {
      setLoadingGraph(false);
    }
  };

  const handleNodeClick = useCallback((node: GraphNode) => {
    setSelectedNode(node);
  }, []);

  return (
    <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8 py-8">
      {/* Header */}
      <motion.div
        initial={{ opacity: 0, y: -10 }}
        animate={{ opacity: 1, y: 0 }}
        className="mb-6"
      >
        <div className="flex items-center gap-3 mb-2">
          <Network className="h-6 w-6 text-violet-400" />
          <h1 className="text-2xl font-bold text-white">Investigate</h1>
        </div>
        <p className="text-gray-400 text-sm max-w-2xl">
          Search by phone number, UPI ID, or bank account. Explore the connected
          fraud network through an interactive force-directed graph.
        </p>
      </motion.div>

      {/* Search Bar */}
      <motion.div
        initial={{ opacity: 0, y: 10 }}
        animate={{ opacity: 1, y: 0 }}
        className="glass-card p-4 mb-6"
      >
        <div className="flex gap-3">
          <div className="relative flex-1">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-gray-500" />
            <input
              type="text"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && handleSearch()}
              placeholder="Search by phone number, UPI ID, or bank account..."
              className="w-full pl-10 pr-4 py-2.5 bg-white/[0.03] border border-white/[0.06] rounded-xl text-sm text-gray-200 placeholder:text-gray-600 focus:outline-none focus:border-violet-500/40 focus:ring-1 focus:ring-violet-500/20 transition-all"
            />
          </div>
          <button
            onClick={handleSearch}
            disabled={searching || query.trim().length < 2}
            className="flex items-center gap-2 px-5 py-2.5 rounded-xl bg-gradient-to-r from-violet-500 to-purple-600 text-white text-sm font-medium hover:shadow-lg hover:shadow-violet-500/25 disabled:opacity-40 disabled:cursor-not-allowed transition-all"
          >
            {searching ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <Search className="h-4 w-4" />
            )}
            Search
          </button>
        </div>

        {/* Search Results Dropdown */}
        <AnimatePresence>
          {searchResults.length > 0 && (
            <motion.div
              initial={{ opacity: 0, height: 0 }}
              animate={{ opacity: 1, height: "auto" }}
              exit={{ opacity: 0, height: 0 }}
              className="mt-3 space-y-1.5"
            >
              {searchResults.map((result) => {
                const Icon = NODE_ICONS[result.node_type] || Network;
                return (
                  <button
                    key={result.id}
                    onClick={() => handleSelectNode(result.id)}
                    className="w-full flex items-center gap-3 p-3 rounded-lg bg-white/[0.02] border border-white/[0.04] hover:border-violet-500/30 hover:bg-white/[0.04] transition-all text-left"
                  >
                    <div
                      className="h-8 w-8 rounded-lg flex items-center justify-center"
                      style={{
                        background: `${NODE_TYPE_COLORS[result.node_type] || "#6b7280"}15`,
                        border: `1px solid ${NODE_TYPE_COLORS[result.node_type] || "#6b7280"}30`,
                      }}
                    >
                      <Icon className="h-4 w-4" style={{ color: NODE_TYPE_COLORS[result.node_type] }} />
                    </div>
                    <div className="flex-1">
                      <p className="text-sm font-medium text-gray-200">{result.label}</p>
                      <p className="text-xs text-gray-500 capitalize">{result.node_type.replace("_", " ")}</p>
                    </div>
                    {result.risk_score != null && (
                      <span className={`text-xs font-medium px-2 py-0.5 rounded-full ${
                        result.risk_score >= 0.7 ? "risk-critical" :
                        result.risk_score >= 0.4 ? "risk-high" : "risk-medium"
                      }`}>
                        Risk: {Math.round(result.risk_score * 100)}%
                      </span>
                    )}
                  </button>
                );
              })}
            </motion.div>
          )}
        </AnimatePresence>

        {error && (
          <p className="mt-3 text-sm text-red-400">{error}</p>
        )}
      </motion.div>

      {/* Graph + Detail Panel */}
      <div className="grid grid-cols-1 lg:grid-cols-4 gap-6">
        {/* Graph */}
        <div className="lg:col-span-3">
          <div className="glass-card overflow-hidden" style={{ height: "600px" }}>
            {loadingGraph ? (
              <div className="h-full flex items-center justify-center">
                <div className="text-center">
                  <Loader2 className="h-8 w-8 animate-spin text-violet-400 mx-auto mb-3" />
                  <p className="text-sm text-gray-400">Loading fraud network...</p>
                </div>
              </div>
            ) : networkData ? (
              <FraudGraph
                data={networkData}
                onNodeClick={handleNodeClick}
                selectedNodeId={selectedNode?.id || null}
              />
            ) : (
              <div className="h-full flex items-center justify-center">
                <div className="text-center">
                  <Network className="h-12 w-12 text-gray-700 mx-auto mb-3" />
                  <p className="text-gray-400 font-medium mb-1">No network loaded</p>
                  <p className="text-sm text-gray-600 max-w-xs mx-auto">
                    Search for a phone number, UPI ID, or bank account to explore
                    its connected fraud network.
                  </p>
                </div>
              </div>
            )}
          </div>
        </div>

        {/* Node Detail Panel */}
        <div className="lg:col-span-1">
          <AnimatePresence mode="wait">
            {selectedNode ? (
              <motion.div
                key={selectedNode.id}
                initial={{ opacity: 0, x: 20 }}
                animate={{ opacity: 1, x: 0 }}
                exit={{ opacity: 0, x: 20 }}
                className="glass-card p-5 space-y-4"
              >
                <div className="flex items-start justify-between">
                  <div>
                    <span className="text-xs text-gray-500 capitalize">
                      {selectedNode.node_type.replace("_", " ")}
                    </span>
                    <h3 className="text-lg font-semibold text-white mt-0.5">
                      {selectedNode.label}
                    </h3>
                  </div>
                  <button onClick={() => setSelectedNode(null)}>
                    <X className="h-4 w-4 text-gray-500 hover:text-gray-300" />
                  </button>
                </div>

                {selectedNode.risk_score != null && (
                  <div>
                    <span className="text-xs text-gray-500">Risk Score</span>
                    <div className="flex items-center gap-2 mt-1">
                      <div className="flex-1 h-2 bg-white/[0.06] rounded-full overflow-hidden">
                        <div
                          className="h-full rounded-full transition-all"
                          style={{
                            width: `${selectedNode.risk_score * 100}%`,
                            background: selectedNode.risk_score >= 0.7
                              ? "#ef4444"
                              : selectedNode.risk_score >= 0.4
                              ? "#f97316"
                              : "#22c55e",
                          }}
                        />
                      </div>
                      <span className="text-sm font-medium text-gray-300">
                        {Math.round(selectedNode.risk_score * 100)}%
                      </span>
                    </div>
                  </div>
                )}

                {/* Properties */}
                <div className="space-y-2">
                  <span className="text-xs text-gray-500">Properties</span>
                  <div className="space-y-1.5">
                    {Object.entries(selectedNode.properties).map(([key, value]) => (
                      <div key={key} className="flex justify-between text-xs p-2 rounded-lg bg-white/[0.02]">
                        <span className="text-gray-400">{key.replace(/_/g, " ")}</span>
                        <span className="text-gray-200 font-medium">
                          {typeof value === "boolean" ? (value ? "Yes" : "No") : String(value)}
                        </span>
                      </div>
                    ))}
                  </div>
                </div>

                {selectedNode.first_seen && (
                  <div className="pt-3 border-t border-white/[0.04] text-xs text-gray-500 space-y-1">
                    <p>First seen: {new Date(selectedNode.first_seen).toLocaleDateString()}</p>
                    {selectedNode.last_seen && (
                      <p>Last seen: {new Date(selectedNode.last_seen).toLocaleDateString()}</p>
                    )}
                  </div>
                )}

                {/* Expand button */}
                <button
                  onClick={() => handleSelectNode(selectedNode.id)}
                  className="w-full py-2 rounded-lg bg-violet-500/10 border border-violet-500/20 text-violet-400 text-xs font-medium hover:bg-violet-500/20 transition-all"
                >
                  Expand Network from this Node
                </button>
              </motion.div>
            ) : (
              <motion.div
                key="empty"
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                className="glass-card p-5 flex flex-col items-center justify-center text-center py-12"
              >
                <User className="h-8 w-8 text-gray-700 mb-3" />
                <p className="text-sm text-gray-400 mb-1">No node selected</p>
                <p className="text-xs text-gray-600">
                  Click on a node in the graph to see its details.
                </p>
              </motion.div>
            )}
          </AnimatePresence>

          {/* Legend */}
          {networkData && (
            <div className="glass-card p-4 mt-4">
              <span className="text-xs text-gray-500 font-medium">Legend</span>
              <div className="mt-2 space-y-1.5">
                {Object.entries(NODE_TYPE_COLORS).map(([type, color]) => (
                  <div key={type} className="flex items-center gap-2">
                    <div className="h-3 w-3 rounded-full" style={{ background: color }} />
                    <span className="text-xs text-gray-400 capitalize">{type.replace("_", " ")}</span>
                  </div>
                ))}
              </div>
              <div className="mt-3 pt-3 border-t border-white/[0.04] text-xs text-gray-500">
                <p>{networkData.total_nodes} nodes · {networkData.total_edges} edges</p>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
