"use client";

/**
 * Loading Skeleton Components
 *
 * Provides consistent skeleton loading states for all NETRA pages.
 * Uses CSS animations (no JS overhead) for smooth shimmer effects.
 */

function Shimmer({ className = "", style }: { className?: string; style?: React.CSSProperties }) {
  return (
    <div
      className={`animate-pulse rounded bg-white/[0.06] ${className}`}
      style={style}
    />
  );
}

/** Skeleton for metric stat cards on the dashboard */
export function MetricCardSkeleton() {
  return (
    <div className="glass-card p-4 space-y-3">
      <div className="flex items-center gap-2">
        <Shimmer className="h-8 w-8 rounded-lg" />
        <Shimmer className="h-3 w-20" />
      </div>
      <Shimmer className="h-8 w-16" />
      <Shimmer className="h-2 w-24" />
    </div>
  );
}

/** Skeleton for a full row of metric cards */
export function DashboardMetricsSkeleton() {
  return (
    <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-3">
      {Array.from({ length: 5 }).map((_, i) => (
        <MetricCardSkeleton key={i} />
      ))}
    </div>
  );
}

/** Skeleton for chart cards */
export function ChartSkeleton({ height = 200 }: { height?: number }) {
  return (
    <div className="glass-card p-5 space-y-3">
      <div className="flex items-center gap-2">
        <Shimmer className="h-4 w-4 rounded" />
        <Shimmer className="h-3 w-32" />
      </div>
      <Shimmer className="w-full rounded-lg" style={{ height }} />
    </div>
  );
}

/** Skeleton for threat feed items */
export function ThreatFeedSkeleton() {
  return (
    <div className="glass-card p-4 space-y-2">
      <Shimmer className="h-3 w-24" />
      {Array.from({ length: 5 }).map((_, i) => (
        <div key={i} className="flex items-center gap-3 py-2">
          <Shimmer className="h-6 w-6 rounded-full flex-shrink-0" />
          <div className="flex-1 space-y-1.5">
            <Shimmer className="h-3 w-full" />
            <Shimmer className="h-2 w-3/4" />
          </div>
          <Shimmer className="h-4 w-12 rounded-full" />
        </div>
      ))}
    </div>
  );
}

/** Skeleton for the detect page form area */
export function DetectFormSkeleton() {
  return (
    <div className="glass-card p-6 space-y-4">
      <div className="flex gap-2">
        {Array.from({ length: 3 }).map((_, i) => (
          <Shimmer key={i} className="h-8 w-24 rounded-lg" />
        ))}
      </div>
      <Shimmer className="h-32 w-full rounded-lg" />
      <Shimmer className="h-10 w-full rounded-lg" />
    </div>
  );
}

/** Skeleton for the investigate page graph area */
export function GraphSkeleton() {
  return (
    <div className="glass-card p-4 space-y-3">
      <div className="flex items-center gap-2">
        <Shimmer className="h-4 w-4 rounded" />
        <Shimmer className="h-3 w-40" />
      </div>
      <Shimmer className="w-full h-[400px] rounded-lg" />
    </div>
  );
}

/** Skeleton for entity list items */
export function EntityListSkeleton({ count = 6 }: { count?: number }) {
  return (
    <div className="space-y-2">
      {Array.from({ length: count }).map((_, i) => (
        <div key={i} className="flex items-center gap-3 p-2.5 rounded-lg bg-white/[0.02]">
          <Shimmer className="h-6 w-6 rounded flex-shrink-0" />
          <div className="flex-1 space-y-1">
            <Shimmer className="h-3 w-3/4" />
            <Shimmer className="h-2 w-1/2" />
          </div>
          <Shimmer className="h-5 w-10 rounded-full" />
        </div>
      ))}
    </div>
  );
}

/** Full page loading state */
export function PageLoadingSkeleton({ title }: { title: string }) {
  return (
    <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8 py-8">
      <div className="flex items-center gap-3 mb-8">
        <Shimmer className="h-6 w-6 rounded" />
        <Shimmer className="h-6 w-48" />
      </div>
      <div className="text-center py-20">
        <div className="inline-flex items-center gap-2 text-sm text-gray-500">
          <div className="h-4 w-4 border-2 border-cyan-400 border-t-transparent rounded-full animate-spin" />
          Loading {title}...
        </div>
      </div>
    </div>
  );
}
