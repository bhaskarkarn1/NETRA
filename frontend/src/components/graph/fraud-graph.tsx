"use client";

import { useRef, useEffect, useCallback } from "react";
import * as d3 from "d3";
import type { NetworkResponse, GraphNode, GraphEdge } from "@/lib/types";
import { NODE_TYPE_COLORS, NODE_TYPE_ICONS } from "@/lib/types";

interface FraudGraphProps {
  data: NetworkResponse;
  onNodeClick: (node: GraphNode) => void;
  selectedNodeId: string | null;
}

interface D3Node extends d3.SimulationNodeDatum {
  id: string;
  data: GraphNode;
}

interface D3Link extends d3.SimulationLinkDatum<D3Node> {
  id: string;
  data: GraphEdge;
}

export function FraudGraph({ data, onNodeClick, selectedNodeId }: FraudGraphProps) {
  const svgRef = useRef<SVGSVGElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);

  const buildGraph = useCallback(() => {
    if (!svgRef.current || !containerRef.current) return;

    const container = containerRef.current;
    const width = container.clientWidth;
    const height = container.clientHeight;

    // Clear previous
    d3.select(svgRef.current).selectAll("*").remove();

    const svg = d3.select(svgRef.current)
      .attr("width", width)
      .attr("height", height);

    // Defs for gradients and filters
    const defs = svg.append("defs");

    // Glow filter
    const filter = defs.append("filter").attr("id", "glow");
    filter.append("feGaussianBlur").attr("stdDeviation", 3).attr("result", "coloredBlur");
    const merge = filter.append("feMerge");
    merge.append("feMergeNode").attr("in", "coloredBlur");
    merge.append("feMergeNode").attr("in", "SourceGraphic");

    // Arrow marker for directed edges
    defs.append("marker")
      .attr("id", "arrowhead")
      .attr("viewBox", "0 -5 10 10")
      .attr("refX", 25)
      .attr("refY", 0)
      .attr("markerWidth", 6)
      .attr("markerHeight", 6)
      .attr("orient", "auto")
      .append("path")
      .attr("d", "M0,-5L10,0L0,5")
      .attr("fill", "rgba(255,255,255,0.2)");

    // Zoom group
    const g = svg.append("g");

    const zoom = d3.zoom<SVGSVGElement, unknown>()
      .scaleExtent([0.2, 4])
      .on("zoom", (event) => {
        g.attr("transform", event.transform);
      });

    svg.call(zoom);

    // Create node/link data
    const nodes: D3Node[] = data.nodes.map((n) => ({
      id: n.id,
      data: n,
      x: width / 2 + (Math.random() - 0.5) * 100,
      y: height / 2 + (Math.random() - 0.5) * 100,
    }));

    const nodeMap = new Map(nodes.map((n) => [n.id, n]));

    const links: D3Link[] = data.edges
      .filter((e) => nodeMap.has(e.source_id) && nodeMap.has(e.target_id))
      .map((e) => ({
        id: e.id,
        source: nodeMap.get(e.source_id)!,
        target: nodeMap.get(e.target_id)!,
        data: e,
      }));

    // Force simulation
    const simulation = d3.forceSimulation<D3Node>(nodes)
      .force("link", d3.forceLink<D3Node, D3Link>(links).id((d) => d.id).distance(120).strength(0.4))
      .force("charge", d3.forceManyBody().strength(-400))
      .force("center", d3.forceCenter(width / 2, height / 2))
      .force("collision", d3.forceCollide().radius(35));

    // Draw edges
    const link = g.append("g")
      .selectAll("line")
      .data(links)
      .join("line")
      .attr("stroke", (d) => {
        if (d.data.edge_type === "transferred") return "rgba(239, 68, 68, 0.4)";
        if (d.data.edge_type === "called") return "rgba(59, 130, 246, 0.3)";
        return "rgba(255, 255, 255, 0.1)";
      })
      .attr("stroke-width", (d) => Math.min(d.data.weight * 1.2, 5))
      .attr("marker-end", "url(#arrowhead)")
      .attr("class", "graph-edge-draw")
      .style("opacity", 0);

    // Animate edges in
    link.transition()
      .delay((_, i) => 300 + i * 50)
      .duration(600)
      .style("opacity", 1);

    // Money flow animated overlay for transfer edges
    const flowLinks = g.append("g")
      .selectAll("line")
      .data(links.filter((l) => l.data.edge_type === "transferred"))
      .join("line")
      .attr("stroke", "rgba(239, 68, 68, 0.6)")
      .attr("stroke-width", 2)
      .attr("class", "graph-edge-flow")
      .style("opacity", 0);

    flowLinks.transition()
      .delay((_, i) => 800 + i * 100)
      .duration(400)
      .style("opacity", 0.5);

    // Edge labels
    const edgeLabels = g.append("g")
      .selectAll("text")
      .data(links)
      .join("text")
      .attr("font-size", 9)
      .attr("fill", "rgba(255,255,255,0.3)")
      .attr("text-anchor", "middle")
      .text((d) => {
        if (d.data.edge_type === "transferred") {
          const amount = d.data.properties.total_amount_inr as number;
          return amount ? `₹${(amount / 100000).toFixed(1)}L` : "";
        }
        if (d.data.edge_type === "called") {
          const count = d.data.properties.count as number;
          return count ? `${count} calls` : "";
        }
        return d.data.edge_type;
      });

    // Draw nodes
    const node = g.append("g")
      .selectAll("g")
      .data(nodes)
      .join("g")
      .attr("cursor", "pointer")
      .style("opacity", 0)
      .on("click", (_, d) => onNodeClick(d.data));

    // Animate nodes in with stagger
    node.transition()
      .delay((_, i) => i * 60)
      .duration(400)
      .style("opacity", 1);

    // Node circle
    node.append("circle")
      .attr("r", (d) => {
        if (d.id === data.center_node_id) return 22;
        if (d.data.node_type === "victim") return 14;
        return 18;
      })
      .attr("fill", (d) => `${NODE_TYPE_COLORS[d.data.node_type] || "#6b7280"}20`)
      .attr("stroke", (d) => NODE_TYPE_COLORS[d.data.node_type] || "#6b7280")
      .attr("stroke-width", (d) => d.id === data.center_node_id ? 3 : 1.5)
      .attr("filter", (d) => d.id === data.center_node_id ? "url(#glow)" : "none");

    // Node icon (emoji)
    node.append("text")
      .attr("text-anchor", "middle")
      .attr("dominant-baseline", "central")
      .attr("font-size", (d) => d.id === data.center_node_id ? 14 : 11)
      .text((d) => NODE_TYPE_ICONS[d.data.node_type] || "●");

    // Node label
    node.append("text")
      .attr("dy", (d) => d.id === data.center_node_id ? 34 : 28)
      .attr("text-anchor", "middle")
      .attr("font-size", 10)
      .attr("fill", "rgba(255,255,255,0.6)")
      .attr("font-weight", (d) => d.id === data.center_node_id ? "600" : "400")
      .text((d) => {
        const label = d.data.label;
        return label.length > 20 ? label.substring(0, 18) + "…" : label;
      });

    // Risk score badge for high-risk nodes
    node.filter((d) => d.data.risk_score != null && d.data.risk_score >= 0.7)
      .append("circle")
      .attr("cx", 14)
      .attr("cy", -14)
      .attr("r", 8)
      .attr("fill", "#ef4444")
      .attr("stroke", "#09090b")
      .attr("stroke-width", 2);

    node.filter((d) => d.data.risk_score != null && d.data.risk_score >= 0.7)
      .append("text")
      .attr("x", 14)
      .attr("y", -14)
      .attr("text-anchor", "middle")
      .attr("dominant-baseline", "central")
      .attr("font-size", 7)
      .attr("fill", "white")
      .attr("font-weight", "bold")
      .text("!");

    // Drag behavior
    const drag = d3.drag<SVGGElement, D3Node>()
      .on("start", (event, d) => {
        if (!event.active) simulation.alphaTarget(0.3).restart();
        d.fx = d.x;
        d.fy = d.y;
      })
      .on("drag", (event, d) => {
        d.fx = event.x;
        d.fy = event.y;
      })
      .on("end", (event, d) => {
        if (!event.active) simulation.alphaTarget(0);
        d.fx = null;
        d.fy = null;
      });

    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    node.call(drag as any);

    // Tick
    simulation.on("tick", () => {
      link
        .attr("x1", (d) => (d.source as D3Node).x!)
        .attr("y1", (d) => (d.source as D3Node).y!)
        .attr("x2", (d) => (d.target as D3Node).x!)
        .attr("y2", (d) => (d.target as D3Node).y!);

      flowLinks
        .attr("x1", (d) => (d.source as D3Node).x!)
        .attr("y1", (d) => (d.source as D3Node).y!)
        .attr("x2", (d) => (d.target as D3Node).x!)
        .attr("y2", (d) => (d.target as D3Node).y!);

      edgeLabels
        .attr("x", (d) => ((d.source as D3Node).x! + (d.target as D3Node).x!) / 2)
        .attr("y", (d) => ((d.source as D3Node).y! + (d.target as D3Node).y!) / 2);

      node.attr("transform", (d) => `translate(${d.x},${d.y})`);
    });

    // Initial zoom to fit
    setTimeout(() => {
      const bounds = (g.node() as SVGGElement)?.getBBox();
      if (bounds) {
        const dx = bounds.width;
        const dy = bounds.height;
        const x = bounds.x + dx / 2;
        const y = bounds.y + dy / 2;
        const scale = 0.8 / Math.max(dx / width, dy / height);
        const translate: [number, number] = [width / 2 - scale * x, height / 2 - scale * y];

        svg.transition()
          .duration(750)
          .call(
            zoom.transform,
            d3.zoomIdentity.translate(translate[0], translate[1]).scale(scale)
          );
      }
    }, 1500);

    return () => {
      simulation.stop();
    };
  }, [data, onNodeClick]);

  useEffect(() => {
    buildGraph();
  }, [buildGraph]);

  // Handle resize
  useEffect(() => {
    const handleResize = () => buildGraph();
    window.addEventListener("resize", handleResize);
    return () => window.removeEventListener("resize", handleResize);
  }, [buildGraph]);

  return (
    <div ref={containerRef} className="w-full h-full relative bg-[#0a0a0c]">
      <svg ref={svgRef} className="w-full h-full" />
      {/* Overlay info */}
      <div className="absolute bottom-4 left-4 text-xs text-gray-600">
        Scroll to zoom · Drag nodes · Click for details
      </div>
    </div>
  );
}
