/**
 * AllocationDonut — SVG donut chart for category allocation.
 * Input: { category, pct }[]  where sum ≈ 100.
 * Uses warm brand palette tokens only; no hardcoded hex outside the palette.
 */
import * as React from 'react';

export interface AllocationSlice {
  category: string;
  pct: number;
}

// Warm palette slice colours (brand tokens, static)
const SLICE_COLORS = [
  '#1E5EFF', // royal
  '#00B386', // emerald
  '#00C2FF', // cyan
  '#F5A623', // amber
  '#E5484D', // red
  '#0B1F3A', // navy
  '#1FD79A', // emerald-dark
];

export interface AllocationDonutProps {
  data: AllocationSlice[];
  size?: number;
  strokeWidth?: number;
}

export function AllocationDonut({
  data,
  size = 180,
  strokeWidth = 26,
}: AllocationDonutProps) {
  const cx = size / 2;
  const cy = size / 2;
  const radius = (size - strokeWidth) / 2;
  const circum = 2 * Math.PI * radius;

  // Build arc segments
  let cumPct = 0;
  const segments = data.map((slice, i) => {
    const offset = circum * (1 - cumPct / 100);
    const dashLen = (slice.pct / 100) * circum;
    const gap = circum - dashLen;
    cumPct += slice.pct;
    return { ...slice, dashLen, gap, offset, color: SLICE_COLORS[i % SLICE_COLORS.length] };
  });

  return (
    <div className="flex flex-col items-center gap-4 sm:flex-row sm:items-start">
      {/* SVG */}
      <svg
        width={size}
        height={size}
        viewBox={`0 0 ${size} ${size}`}
        role="img"
        aria-label="Portfolio allocation by category"
        className="shrink-0"
      >
        {/* Track */}
        <circle
          cx={cx}
          cy={cy}
          r={radius}
          fill="none"
          stroke="var(--border)"
          strokeWidth={strokeWidth}
        />
        {segments.map((seg) => (
          <circle
            key={seg.category}
            cx={cx}
            cy={cy}
            r={radius}
            fill="none"
            stroke={seg.color}
            strokeWidth={strokeWidth - 2}
            strokeDasharray={`${seg.dashLen} ${seg.gap}`}
            strokeDashoffset={seg.offset}
            transform={`rotate(-90 ${cx} ${cy})`}
            strokeLinecap="butt"
          />
        ))}
        {/* Centre label */}
        <text
          x="50%"
          y="48%"
          textAnchor="middle"
          dominantBaseline="middle"
          fontSize="11"
          fontWeight="600"
          fill="var(--text)"
        >
          Allocation
        </text>
      </svg>

      {/* Legend */}
      <ul className="flex flex-col gap-2" aria-label="Category legend">
        {segments.map((seg) => (
          <li key={seg.category} className="flex items-center gap-2 text-small text-ink-secondary">
            <span
              className="inline-block h-2.5 w-2.5 rounded-full shrink-0"
              style={{ background: seg.color }}
              aria-hidden="true"
            />
            <span>{seg.category}</span>
            <span className="ml-auto pl-4 font-medium text-ink">{seg.pct}%</span>
          </li>
        ))}
      </ul>
    </div>
  );
}
