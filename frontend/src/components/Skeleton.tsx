"use client";

export function SkeletonLine({ width = "100%", height = 14 }: { width?: string | number; height?: number }) {
  return <div className="skeleton" style={{ width, height }} />;
}

export function SkeletonCanvas() {
  return (
    <div className="card p-6" style={{ minHeight: 220 }}>
      <div className="flex items-center justify-between mb-5">
        <SkeletonLine width={180} height={16} />
        <SkeletonLine width={80} height={24} />
      </div>
      <div className="flex items-center justify-around py-6">
        {Array.from({ length: 6 }).map((_, i) => (
          <div key={i} className="flex flex-col items-center gap-2">
            <div className="skeleton skeleton-circle" style={{ width: 48, height: 48 }} />
            <SkeletonLine width={60} height={10} />
          </div>
        ))}
      </div>
      <div className="flex justify-center gap-8 mt-2">
        {Array.from({ length: 5 }).map((_, i) => (
          <SkeletonLine key={i} width={40} height={4} />
        ))}
      </div>
    </div>
  );
}

export function SkeletonOutputCard() {
  return (
    <div className="skeleton-card">
      <div className="flex items-center gap-3 mb-4">
        <div className="skeleton skeleton-circle" style={{ width: 32, height: 32 }} />
        <SkeletonLine width={140} height={16} />
        <SkeletonLine width={80} height={20} />
      </div>
      <div className="space-y-3 pl-11">
        <SkeletonLine width="90%" />
        <SkeletonLine width="75%" />
        <SkeletonLine width="60%" />
      </div>
    </div>
  );
}

export function SkeletonActivity() {
  return (
    <div className="card p-4">
      <SkeletonLine width={80} height={10} />
      <div className="mt-4 space-y-3">
        {Array.from({ length: 4 }).map((_, i) => (
          <div key={i} className="flex gap-3 pl-3" style={{ borderLeft: "2px solid var(--border)" }}>
            <div>
              <SkeletonLine width={180} height={12} />
              <SkeletonLine width={60} height={10} />
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

export function DashboardSkeleton() {
  return (
    <div className="min-h-screen p-6 max-w-6xl mx-auto animate-fade-in">
      {/* Header */}
      <div className="mb-6">
        <SkeletonLine width={50} height={12} />
        <div className="flex items-center justify-between mt-4 mb-2">
          <SkeletonLine width={220} height={28} />
          <SkeletonLine width={100} height={26} />
        </div>
        <SkeletonLine width="70%" height={14} />
      </div>

      {/* Canvas */}
      <div className="mb-6">
        <SkeletonCanvas />
      </div>

      {/* Tabs */}
      <div className="flex gap-1 mb-5">
        <SkeletonLine width={130} height={38} />
        <SkeletonLine width={120} height={38} />
      </div>

      {/* Content */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="lg:col-span-2 space-y-4">
          <SkeletonOutputCard />
          <SkeletonOutputCard />
        </div>
        <div className="lg:col-span-1">
          <SkeletonActivity />
        </div>
      </div>
    </div>
  );
}
