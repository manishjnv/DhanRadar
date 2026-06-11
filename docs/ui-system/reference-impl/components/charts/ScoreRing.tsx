import { cn } from '@/lib/cn';
const SIGNAL = (s: number) => s>=85?'Strong Buy':s>=70?'Buy':s>=55?'Hold':s>=40?'Caution':'Avoid';
const COLOR = (s: number) => s>=85?'var(--positive)':s>=70?'var(--blue)':s>=55?'var(--warn)':s>=40?'#F97316':'var(--negative)';
export function ScoreRing({ score, size = 96, stroke = 8, className }: { score: number; size?: number; stroke?: number; className?: string }) {
  const r = (size - stroke) / 2, c = 2 * Math.PI * r, off = c * (1 - score / 100);
  return (
    <div className={cn('relative inline-grid place-items-center', className)} style={{ width: size, height: size }}
         role="img" aria-label={`Score ${score} of 100, ${SIGNAL(score)}`}>
      <svg width={size} height={size} className="-rotate-90" aria-hidden>
        <circle cx={size/2} cy={size/2} r={r} fill="none" stroke="var(--ring-bg, rgba(15,23,42,.08))" strokeWidth={stroke}/>
        <circle cx={size/2} cy={size/2} r={r} fill="none" stroke={COLOR(score)} strokeWidth={stroke}
                strokeLinecap="round" strokeDasharray={c} strokeDashoffset={off}
                className="motion-safe:transition-[stroke-dashoffset] motion-safe:duration-700"/>
      </svg>
      <span className="absolute font-mono font-semibold tracking-tight" style={{ fontSize: size*0.34 }}>{score}</span>
    </div>
  );
}
