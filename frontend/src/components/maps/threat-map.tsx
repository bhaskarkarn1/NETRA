"use client";

import { useEffect, useRef, useState } from "react";
import type { GeoPoint } from "@/lib/api";

// MapLibre types for dynamic import
type MapLibreMap = import("maplibre-gl").Map;

/**
 * Threat Heat Map — India
 *
 * Uses MapLibre GL JS (open-source fork of Mapbox GL JS) with OpenStreetMap tiles.
 * No API key required. Renders scam origin locations as a heat layer
 * with circle markers for individual points.
 */
export function ThreatMap({
  points,
  height = 400,
}: {
  points: GeoPoint[];
  height?: number;
}) {
  const containerRef = useRef<HTMLDivElement>(null);
  const mapRef = useRef<MapLibreMap | null>(null);
  const [loaded, setLoaded] = useState(false);

  useEffect(() => {
    if (!containerRef.current || mapRef.current) return;

    let map: MapLibreMap;

    // Dynamic import to avoid SSR issues
    import("maplibre-gl").then((maplibregl) => {
      map = new maplibregl.Map({
        container: containerRef.current!,
        style: {
          version: 8,
          name: "NETRA Dark",
          sources: {
            osm: {
              type: "raster",
              tiles: [
                "https://a.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}@2x.png",
                "https://b.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}@2x.png",
                "https://c.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}@2x.png",
              ],
              tileSize: 256,
              attribution:
                '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> &copy; <a href="https://carto.com/attributions">CARTO</a>',
            },
          },
          layers: [
            {
              id: "osm-tiles",
              type: "raster",
              source: "osm",
              minzoom: 0,
              maxzoom: 19,
            },
          ],
        },
        center: [82.0, 22.5], // Center of India
        zoom: 4.2,
        minZoom: 3,
        maxZoom: 12,
      });

      map.addControl(new maplibregl.NavigationControl(), "top-right");

      map.on("load", () => {
        mapRef.current = map;
        setLoaded(true);
      });
    });

    return () => {
      if (map) {
        map.remove();
        mapRef.current = null;
      }
    };
  }, []);

  // Add data layers when map is loaded and points change
  useEffect(() => {
    if (!mapRef.current || !loaded || points.length === 0) return;

    const map = mapRef.current;

    // GeoJSON feature collection
    const geojson: GeoJSON.FeatureCollection = {
      type: "FeatureCollection",
      features: points.map((p) => ({
        type: "Feature" as const,
        geometry: {
          type: "Point" as const,
          coordinates: [p.lng, p.lat],
        },
        properties: {
          label: p.label,
          state: p.state,
          is_hotspot: p.is_hotspot,
          risk_score: p.risk_score,
          case_count: p.case_count,
          scam_types: p.scam_types.join(", "),
          // Weight for heat layer: hotspots + high risk = more intense
          weight: p.is_hotspot ? 0.8 + p.risk_score * 0.2 : p.risk_score,
        },
      })),
    };

    // Remove old layers/source if they exist (for re-renders)
    if (map.getLayer("threat-heat")) map.removeLayer("threat-heat");
    if (map.getLayer("threat-circles")) map.removeLayer("threat-circles");
    if (map.getLayer("threat-labels")) map.removeLayer("threat-labels");
    if (map.getSource("threat-data")) map.removeSource("threat-data");

    // Add source
    map.addSource("threat-data", {
      type: "geojson",
      data: geojson,
    });

    // Heat layer
    map.addLayer({
      id: "threat-heat",
      type: "heatmap",
      source: "threat-data",
      maxzoom: 10,
      paint: {
        "heatmap-weight": ["get", "weight"],
        "heatmap-intensity": ["interpolate", ["linear"], ["zoom"], 3, 0.8, 10, 2],
        "heatmap-radius": ["interpolate", ["linear"], ["zoom"], 3, 25, 10, 40],
        "heatmap-opacity": ["interpolate", ["linear"], ["zoom"], 7, 0.9, 10, 0.3],
        "heatmap-color": [
          "interpolate",
          ["linear"],
          ["heatmap-density"],
          0, "rgba(0, 0, 0, 0)",
          0.1, "rgba(6, 182, 212, 0.15)",   // cyan-400
          0.3, "rgba(59, 130, 246, 0.4)",    // blue-500
          0.5, "rgba(139, 92, 246, 0.5)",    // violet-500
          0.7, "rgba(249, 115, 22, 0.6)",    // orange-500
          0.9, "rgba(239, 68, 68, 0.8)",     // red-500
          1.0, "rgba(220, 38, 38, 1)",       // red-600
        ],
      },
    });

    // Circle markers (visible on zoom)
    map.addLayer({
      id: "threat-circles",
      type: "circle",
      source: "threat-data",
      minzoom: 5,
      paint: {
        "circle-radius": [
          "interpolate", ["linear"], ["zoom"],
          5, 4,
          10, 10,
        ],
        "circle-color": [
          "case",
          ["get", "is_hotspot"], "#ef4444",
          [">=", ["get", "risk_score"], 0.7], "#f97316",
          [">=", ["get", "risk_score"], 0.4], "#eab308",
          "#06b6d4",
        ],
        "circle-stroke-color": "rgba(255,255,255,0.3)",
        "circle-stroke-width": 1,
        "circle-opacity": 0.85,
      },
    });

    // Labels on zoom
    map.addLayer({
      id: "threat-labels",
      type: "symbol",
      source: "threat-data",
      minzoom: 6,
      layout: {
        "text-field": ["get", "label"],
        "text-size": 11,
        "text-offset": [0, 1.5],
        "text-anchor": "top",
      },
      paint: {
        "text-color": "#d1d5db",
        "text-halo-color": "rgba(0,0,0,0.8)",
        "text-halo-width": 1,
      },
    });

    // Popup on click
    map.on("click", "threat-circles", (e) => {
      if (!e.features || e.features.length === 0) return;
      const props = e.features[0].properties;
      if (!props) return;

      const coords = (e.features[0].geometry as GeoJSON.Point).coordinates.slice() as [number, number];

      import("maplibre-gl").then(({ Popup }) => {
        new Popup({ closeButton: false, className: "netra-popup" })
          .setLngLat(coords)
          .setHTML(`
            <div style="font-family: system-ui; font-size: 12px; color: #e5e7eb; padding: 4px;">
              <div style="font-weight: 700; font-size: 13px; margin-bottom: 4px;">${props.label}</div>
              <div style="color: #9ca3af;">State: ${props.state}</div>
              <div style="color: ${props.is_hotspot ? '#ef4444' : '#9ca3af'};">
                ${props.is_hotspot ? '🔴 Known Hotspot' : '📍 Detected Location'}
              </div>
              <div>Risk: <span style="color: ${Number(props.risk_score) >= 0.7 ? '#ef4444' : '#eab308'};">${Math.round(Number(props.risk_score) * 100)}%</span></div>
              <div style="color: #9ca3af; font-size: 11px; margin-top: 2px;">${props.scam_types}</div>
            </div>
          `)
          .addTo(map);
      });
    });

    // Cursor change
    map.on("mouseenter", "threat-circles", () => {
      map.getCanvas().style.cursor = "pointer";
    });
    map.on("mouseleave", "threat-circles", () => {
      map.getCanvas().style.cursor = "";
    });
  }, [points, loaded]);

  return (
    <div className="relative w-full rounded-xl overflow-hidden border border-white/[0.06]">
      <div ref={containerRef} style={{ height: `${height}px`, width: "100%" }} />
      {!loaded && (
        <div className="absolute inset-0 flex items-center justify-center bg-black/50">
          <div className="flex items-center gap-2 text-sm text-gray-400">
            <div className="h-4 w-4 border-2 border-cyan-400 border-t-transparent rounded-full animate-spin" />
            Loading map...
          </div>
        </div>
      )}
    </div>
  );
}
