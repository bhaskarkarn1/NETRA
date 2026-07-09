"use client";

import { useEffect, useRef } from "react";
import * as d3 from "d3";
import type { ChartDataPoint } from "@/lib/api";

// =================== Donut Chart ===================

export function DonutChart({
  data,
  title,
  size = 200,
}: {
  data: ChartDataPoint[];
  title: string;
  size?: number;
}) {
  const svgRef = useRef<SVGSVGElement>(null);

  useEffect(() => {
    if (!svgRef.current || data.length === 0) return;

    const svg = d3.select(svgRef.current);
    svg.selectAll("*").remove();

    const width = size;
    const height = size;
    const radius = Math.min(width, height) / 2 - 10;
    const innerRadius = radius * 0.55;

    const g = svg
      .attr("width", width)
      .attr("height", height)
      .append("g")
      .attr("transform", `translate(${width / 2},${height / 2})`);

    const pie = d3
      .pie<ChartDataPoint>()
      .value((d) => d.value)
      .sort(null)
      .padAngle(0.03);

    const arc = d3
      .arc<d3.PieArcDatum<ChartDataPoint>>()
      .innerRadius(innerRadius)
      .outerRadius(radius)
      .cornerRadius(4);

    const arcs = g
      .selectAll("path")
      .data(pie(data))
      .join("path")
      .attr("fill", (d) => d.data.color || "#6b7280")
      .attr("opacity", 0.85)
      .attr("stroke", "rgba(0,0,0,0.3)")
      .attr("stroke-width", 1);

    // Animate
    arcs
      .transition()
      .duration(800)
      .attrTween("d", function (d) {
        const interpolate = d3.interpolate({ startAngle: 0, endAngle: 0 }, d);
        return function (t) {
          return arc(interpolate(t)) || "";
        };
      });

    // Hover
    arcs
      .on("mouseenter", function () {
        d3.select(this).transition().duration(200).attr("opacity", 1);
      })
      .on("mouseleave", function () {
        d3.select(this).transition().duration(200).attr("opacity", 0.85);
      });

    // Center total
    const total = data.reduce((s, d) => s + d.value, 0);
    g.append("text")
      .attr("text-anchor", "middle")
      .attr("dy", "-0.2em")
      .attr("fill", "#fff")
      .attr("font-size", "1.5rem")
      .attr("font-weight", "bold")
      .text(total);

    g.append("text")
      .attr("text-anchor", "middle")
      .attr("dy", "1.2em")
      .attr("fill", "#9ca3af")
      .attr("font-size", "0.65rem")
      .text("total");
  }, [data, size]);

  return (
    <div className="flex flex-col items-center">
      <svg ref={svgRef} />
      <div className="mt-2 flex flex-wrap justify-center gap-x-3 gap-y-1">
        {data.map((d) => (
          <div key={d.label} className="flex items-center gap-1.5">
            <div
              className="h-2 w-2 rounded-full"
              style={{ background: d.color || "#6b7280" }}
            />
            <span className="text-[10px] text-gray-400">
              {d.label} ({d.value})
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}

// =================== Horizontal Bar Chart ===================

export function HorizontalBarChart({
  data,
  title,
  height = 200,
}: {
  data: ChartDataPoint[];
  title: string;
  height?: number;
}) {
  const containerRef = useRef<HTMLDivElement>(null);
  const svgRef = useRef<SVGSVGElement>(null);

  useEffect(() => {
    if (!svgRef.current || !containerRef.current || data.length === 0) return;

    const svg = d3.select(svgRef.current);
    svg.selectAll("*").remove();

    const width = containerRef.current.clientWidth;
    const margin = { top: 5, right: 40, bottom: 5, left: 90 };
    const innerWidth = width - margin.left - margin.right;
    const barHeight = 22;
    const chartHeight = Math.max(data.length * (barHeight + 4), 60);

    svg.attr("width", width).attr("height", chartHeight + margin.top + margin.bottom);

    const g = svg
      .append("g")
      .attr("transform", `translate(${margin.left},${margin.top})`);

    const maxVal = d3.max(data, (d) => d.value) || 1;

    const x = d3.scaleLinear().domain([0, maxVal]).range([0, innerWidth]);

    const y = d3
      .scaleBand()
      .domain(data.map((d) => d.label))
      .range([0, chartHeight])
      .padding(0.15);

    // Labels
    g.selectAll(".label")
      .data(data)
      .join("text")
      .attr("class", "label")
      .attr("x", -4)
      .attr("y", (d) => (y(d.label) || 0) + y.bandwidth() / 2)
      .attr("text-anchor", "end")
      .attr("dominant-baseline", "middle")
      .attr("fill", "#9ca3af")
      .attr("font-size", "10px")
      .text((d) => d.label.replace(/_/g, " "));

    // Bars
    g.selectAll("rect")
      .data(data)
      .join("rect")
      .attr("x", 0)
      .attr("y", (d) => y(d.label) || 0)
      .attr("height", y.bandwidth())
      .attr("rx", 4)
      .attr("fill", (d) => d.color || "#6b7280")
      .attr("opacity", 0.8)
      .attr("width", 0)
      .transition()
      .duration(600)
      .delay((_, i) => i * 60)
      .attr("width", (d) => x(d.value));

    // Value labels
    g.selectAll(".value")
      .data(data)
      .join("text")
      .attr("class", "value")
      .attr("x", (d) => x(d.value) + 6)
      .attr("y", (d) => (y(d.label) || 0) + y.bandwidth() / 2)
      .attr("dominant-baseline", "middle")
      .attr("fill", "#d1d5db")
      .attr("font-size", "11px")
      .attr("font-weight", "600")
      .text((d) => d.value);
  }, [data, height]);

  return (
    <div ref={containerRef} className="w-full">
      <svg ref={svgRef} className="w-full" />
    </div>
  );
}

// =================== Risk Entities Table ===================

export function TopEntitiesTable({
  entities,
}: {
  entities: Array<{ label: string; type: string; risk_score: number }>;
}) {
  const typeIcons: Record<string, string> = {
    phone: "📱",
    upi_id: "💳",
    bank_account: "🏦",
    email: "📧",
    url: "🔗",
    person: "🕵️",
    organization: "🏢",
    location: "📍",
    amount: "💰",
  };

  return (
    <div className="space-y-1.5">
      {entities.map((entity, i) => (
        <div
          key={i}
          className="flex items-center justify-between p-2 rounded-lg bg-white/[0.02] border border-white/[0.04]"
        >
          <div className="flex items-center gap-2 min-w-0">
            <span className="text-sm">{typeIcons[entity.type] || "📌"}</span>
            <span className="text-xs text-gray-300 font-mono truncate">
              {entity.label}
            </span>
          </div>
          <div className="flex items-center gap-2">
            <div className="w-16 h-1.5 rounded-full bg-white/[0.06] overflow-hidden">
              <div
                className="h-full rounded-full"
                style={{
                  width: `${entity.risk_score * 100}%`,
                  background:
                    entity.risk_score >= 0.7
                      ? "#ef4444"
                      : entity.risk_score >= 0.4
                        ? "#f97316"
                        : "#22c55e",
                }}
              />
            </div>
            <span className="text-[10px] text-gray-400 w-8 text-right">
              {Math.round(entity.risk_score * 100)}%
            </span>
          </div>
        </div>
      ))}
      {entities.length === 0 && (
        <p className="text-xs text-gray-600 text-center py-4">
          No high-risk entities detected yet
        </p>
      )}
    </div>
  );
}
