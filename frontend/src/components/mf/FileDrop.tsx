'use client';

import * as React from 'react';
import { cn } from '@/lib/cn';

export interface FileDropProps {
  onFile: (file: File) => void;
  accept?: string;
  disabled?: boolean;
  className?: string;
}

export function FileDrop({ onFile, accept = '.pdf', disabled, className }: FileDropProps) {
  const [dragging, setDragging] = React.useState(false);
  const inputRef = React.useRef<HTMLInputElement>(null);

  function handleDrop(e: React.DragEvent<HTMLDivElement>) {
    e.preventDefault();
    setDragging(false);
    const file = e.dataTransfer.files[0];
    if (file) onFile(file);
  }

  function handleChange(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (file) onFile(file);
  }

  return (
    <div
      role="button"
      tabIndex={disabled ? -1 : 0}
      aria-label="Drop your CAS PDF here or click to choose"
      aria-disabled={disabled}
      className={cn(
        'flex flex-col items-center justify-center gap-3 rounded-lg border-2 border-dashed border-line p-10 text-center transition-colors cursor-pointer',
        dragging && 'border-royal bg-royal/5',
        !dragging && !disabled && 'hover:border-line-strong hover:bg-surface-2',
        disabled && 'opacity-50 cursor-not-allowed',
        className,
      )}
      onDragOver={(e) => { e.preventDefault(); setDragging(true); }}
      onDragLeave={() => setDragging(false)}
      onDrop={handleDrop}
      onClick={() => !disabled && inputRef.current?.click()}
      onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') inputRef.current?.click(); }}
    >
      <span className="text-3xl" aria-hidden="true">📄</span>
      <div>
        <p className="text-body font-medium text-ink">Drop your CAS PDF here</p>
        <p className="text-small text-ink-muted mt-1">or click to choose a file</p>
      </div>
      <p className="text-caption text-ink-muted">Accepts .pdf only</p>
      <input
        ref={inputRef}
        type="file"
        accept={accept}
        className="sr-only"
        aria-hidden="true"
        tabIndex={-1}
        onChange={handleChange}
        disabled={disabled}
      />
    </div>
  );
}
