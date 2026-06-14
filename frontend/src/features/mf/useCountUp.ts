import * as React from 'react';

/** Animates from 0 to `target` over `duration` ms (cubic ease-out). */
export function useCountUp(target: number, duration = 900): number {
  const [value, setValue] = React.useState(0);
  const rafRef = React.useRef<number>(0);

  React.useEffect(() => {
    cancelAnimationFrame(rafRef.current);
    if (target === 0) { setValue(0); return; }
    const start = performance.now();
    const tick = (now: number) => {
      const t = Math.min((now - start) / duration, 1);
      const eased = 1 - Math.pow(1 - t, 3); // cubic ease-out
      setValue(target * eased);
      if (t < 1) rafRef.current = requestAnimationFrame(tick);
      else setValue(target); // ensure exact final value
    };
    rafRef.current = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(rafRef.current);
  }, [target, duration]);

  return value;
}
