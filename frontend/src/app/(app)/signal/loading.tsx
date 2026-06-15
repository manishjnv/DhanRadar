export default function SignalLoading() {
  return (
    <div className="flex flex-col gap-6 animate-pulse">
      {/* Page heading skeleton */}
      <div className="space-y-2">
        <div className="h-7 w-24 rounded-lg bg-surface-2" />
        <div className="h-4 w-48 rounded bg-surface-2" />
      </div>

      {/* Tab bar skeleton */}
      <div className="flex gap-0 border-b border-line pb-0">
        <div className="mr-4 h-10 w-16 rounded-t bg-surface-2" />
        <div className="h-10 w-24 rounded-t bg-surface-2" />
      </div>

      {/* Hero card skeleton */}
      <div className="rounded-xl border border-line bg-surface p-4 space-y-3">
        <div className="flex gap-4">
          <div className="h-16 w-16 rounded-full bg-surface-2" />
          <div className="flex-1 space-y-2">
            <div className="h-5 w-40 rounded bg-surface-2" />
            <div className="h-4 w-24 rounded bg-surface-2" />
          </div>
        </div>
        <div className="h-4 w-full rounded bg-surface-2" />
      </div>

      {/* 3-column card skeletons */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
        {[1, 2, 3].map((i) => (
          <div key={i} className="rounded-xl border border-line bg-surface p-4 space-y-2">
            <div className="h-3 w-20 rounded bg-surface-2" />
            <div className="h-6 w-28 rounded bg-surface-2" />
            <div className="h-2 w-full rounded-full bg-surface-2" />
          </div>
        ))}
      </div>
    </div>
  );
}
