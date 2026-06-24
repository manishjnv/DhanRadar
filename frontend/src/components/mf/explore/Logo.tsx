/** Small colored logo square with a letter — shared by the V4 explore sections. */
'use client';
import * as React from 'react';

export function Logo({ letter, color, size = 28 }: { letter: string; color: string; size?: number }) {
  return (
    <span
      aria-hidden="true"
      className="rounded-lg grid place-items-center text-white font-bold shrink-0 select-none"
      style={{ background: color, width: size, height: size, fontSize: Math.round(size * 0.42) }}
    >
      {letter}
    </span>
  );
}
