import { cn } from '@/lib/cn';
export function Card({ className, ...p }: React.HTMLAttributes<HTMLDivElement>) {
  return <div className={cn('bg-surface border border-line rounded-xl overflow-hidden', className)} {...p} />;
}
export function CardHeader({ title, sub }: { title: string; sub?: string }) {
  return (
    <div className="flex items-center gap-2 px-4 py-3 border-b border-line">
      <h3 className="text-sm font-semibold">{title}</h3>
      {sub && <span className="text-[11px] text-ink-muted ml-auto">{sub}</span>}
    </div>
  );
}
export const CardBody = (p: React.HTMLAttributes<HTMLDivElement>) => <div className="p-4" {...p} />;
