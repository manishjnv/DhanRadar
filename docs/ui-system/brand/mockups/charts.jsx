// DhanRadar — charts: radar score, sparkline, area chart, donut

// Generic helpers
const drMin = (xs) => Math.min.apply(null, xs);
const drMax = (xs) => Math.max.apply(null, xs);
const drLerp = (a, b, t) => a + (b - a) * t;

// ────────────────────────────────────────────────────────────────────
// Sparkline (inline)
// ────────────────────────────────────────────────────────────────────
const Sparkline = ({ data, w = 80, h = 24, color = 'currentColor', strokeWidth = 1.4, fill = false }) => {
  if (!data?.length) return null;
  const lo = drMin(data), hi = drMax(data);
  const range = hi - lo || 1;
  const stepX = w / (data.length - 1);
  const points = data.map((v, i) => [i * stepX, h - ((v - lo) / range) * (h - 2) - 1]);
  const d = 'M' + points.map(([x, y]) => `${x.toFixed(1)},${y.toFixed(1)}`).join(' L');
  const area = d + ` L ${w},${h} L 0,${h} Z`;
  return (
    <svg width={w} height={h} style={{ overflow: 'visible' }}>
      {fill && <path d={area} fill={color} opacity="0.12" />}
      <path d={d} fill="none" stroke={color} strokeWidth={strokeWidth} strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
};

// ────────────────────────────────────────────────────────────────────
// AreaChart — price chart with grid, gradient fill, hover-tooltip
// ────────────────────────────────────────────────────────────────────
const AreaChart = ({ data, w = 720, h = 280, color, accent }) => {
  if (!data?.length) return null;
  const padL = 8, padR = 44, padT = 16, padB = 28;
  const innerW = w - padL - padR, innerH = h - padT - padB;
  const lo = drMin(data) * 0.985, hi = drMax(data) * 1.01;
  const range = hi - lo;
  const stepX = innerW / (data.length - 1);
  const pts = data.map((v, i) => [padL + i * stepX, padT + innerH - ((v - lo) / range) * innerH]);
  const dLine = 'M' + pts.map(([x, y]) => `${x.toFixed(1)},${y.toFixed(1)}`).join(' L');
  const dArea = dLine + ` L ${padL + innerW},${padT + innerH} L ${padL},${padT + innerH} Z`;

  // Y-axis ticks
  const ticks = 4;
  const yTicks = Array.from({ length: ticks + 1 }, (_, i) => {
    const val = lo + (range * i) / ticks;
    const y = padT + innerH - (i / ticks) * innerH;
    return { val, y };
  });

  // X-axis labels — show 6 evenly spaced
  const xLabelCount = 6;
  const months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
  const xLabels = Array.from({ length: xLabelCount }, (_, i) => {
    const idx = Math.floor((i / (xLabelCount - 1)) * (data.length - 1));
    const x = padL + idx * stepX;
    const mi = Math.floor((i / (xLabelCount - 1)) * 11);
    return { x, label: months[mi] };
  });

  const gid = 'g' + Math.floor(Math.random() * 99999);
  return (
    <svg width={w} height={h} style={{ display: 'block' }}>
      <defs>
        <linearGradient id={gid} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor={accent || color} stopOpacity="0.32"/>
          <stop offset="100%" stopColor={accent || color} stopOpacity="0"/>
        </linearGradient>
      </defs>
      {yTicks.map((t, i) => (
        <g key={i}>
          <line x1={padL} y1={t.y} x2={padL + innerW} y2={t.y} stroke="var(--chart-grid)" strokeDasharray={i === 0 || i === ticks ? '' : '2 4'} />
          <text x={padL + innerW + 6} y={t.y + 3} fontSize="10" fontFamily="Geist Mono" fill="var(--text-muted)">
            {t.val.toFixed(0)}
          </text>
        </g>
      ))}
      {xLabels.map((t, i) => (
        <text key={i} x={t.x} y={h - 8} fontSize="10" fontFamily="Geist Mono" fill="var(--text-muted)" textAnchor="middle">{t.label}</text>
      ))}
      <path d={dArea} fill={`url(#${gid})`} />
      <path d={dLine} fill="none" stroke={color} strokeWidth="1.6" />
      {/* current price dot */}
      <circle cx={pts[pts.length - 1][0]} cy={pts[pts.length - 1][1]} r="3.5" fill={color} />
      <circle cx={pts[pts.length - 1][0]} cy={pts[pts.length - 1][1]} r="6" fill={color} opacity="0.18" />
    </svg>
  );
};

// ────────────────────────────────────────────────────────────────────
// Score Ring — circular progress
// ────────────────────────────────────────────────────────────────────
const ScoreRing = ({ score = 0, size = 80, stroke = 6, color, label }) => {
  const r = (size - stroke) / 2;
  const c = 2 * Math.PI * r;
  const off = c * (1 - score / 100);
  const col = color || (score >= 80 ? 'var(--emerald)' : score >= 65 ? 'var(--blue)' : score >= 50 ? 'var(--amber)' : 'var(--red)');
  return (
    <div className="score-ring" style={{ width: size, height: size }}>
      <svg width={size} height={size}>
        <circle cx={size/2} cy={size/2} r={r} fill="none" stroke="var(--score-ring-bg)" strokeWidth={stroke}/>
        <circle cx={size/2} cy={size/2} r={r} fill="none" stroke={col} strokeWidth={stroke}
          strokeLinecap="round" strokeDasharray={c} strokeDashoffset={off}
          style={{ transition: 'stroke-dashoffset 1s cubic-bezier(.2,.7,.2,1)' }}/>
      </svg>
      <div className="score-num" style={{ fontSize: size * 0.32 }}>{score}</div>
      {label && <div className="score-label" style={{ marginTop: size * 0.55 }}>{label}</div>}
    </div>
  );
};

// ────────────────────────────────────────────────────────────────────
// RadarChart — DhanRadar signature: pentagon radar with animated sweep
// ────────────────────────────────────────────────────────────────────
const RadarChart = ({ components, size = 320, animateSweep = true, color, showLabels = true }) => {
  const labels = [
    { key: 'valuation', label: 'Valuation' },
    { key: 'growth', label: 'Growth' },
    { key: 'quality', label: 'Quality' },
    { key: 'momentum', label: 'Momentum' },
    { key: 'risk', label: 'Risk' },
  ];
  const n = labels.length;
  const cx = size / 2, cy = size / 2;
  const maxR = size * 0.34;
  // 5 rings
  const rings = [0.2, 0.4, 0.6, 0.8, 1.0];
  // angle: top = -90deg
  const angle = (i) => (-Math.PI / 2) + (i * 2 * Math.PI) / n;

  // polygon points for each ring
  const ringPath = (ratio) => {
    return Array.from({ length: n }, (_, i) => {
      const a = angle(i);
      return [cx + Math.cos(a) * maxR * ratio, cy + Math.sin(a) * maxR * ratio];
    });
  };

  // value polygon
  const valPts = labels.map((l, i) => {
    const v = (components[l.key] || 0) / 100;
    const a = angle(i);
    return [cx + Math.cos(a) * maxR * v, cy + Math.sin(a) * maxR * v];
  });
  const valPath = 'M' + valPts.map(([x, y]) => `${x.toFixed(1)},${y.toFixed(1)}`).join(' L') + ' Z';

  const accent = color || 'var(--blue)';
  return (
    <div className="radar-wrap" style={{ width: size, height: size }}>
      <svg className="radar-svg" width={size} height={size}>
        <defs>
          <radialGradient id="radarFill" cx="50%" cy="50%" r="50%">
            <stop offset="0%" stopColor={accent} stopOpacity="0.32"/>
            <stop offset="100%" stopColor={accent} stopOpacity="0.06"/>
          </radialGradient>
          <linearGradient id="sweepGrad" x1="0%" y1="0%" x2="100%" y2="0%">
            <stop offset="0%" stopColor={accent} stopOpacity="0"/>
            <stop offset="100%" stopColor={accent} stopOpacity="0.4"/>
          </linearGradient>
        </defs>

        {/* rings */}
        {rings.map((r, i) => {
          const pts = ringPath(r);
          const d = 'M' + pts.map(([x, y]) => `${x.toFixed(1)},${y.toFixed(1)}`).join(' L') + ' Z';
          return <path key={i} d={d} fill="none" stroke="var(--chart-grid)" strokeWidth={i === rings.length - 1 ? 1 : 0.8}/>;
        })}

        {/* axes */}
        {labels.map((_, i) => {
          const a = angle(i);
          return <line key={i} x1={cx} y1={cy} x2={cx + Math.cos(a)*maxR} y2={cy + Math.sin(a)*maxR} stroke="var(--chart-grid)" strokeWidth={0.8}/>;
        })}

        {/* sweep */}
        {animateSweep && (
          <g className="radar-sweep" style={{ transformOrigin: `${cx}px ${cy}px` }}>
            <path d={`M ${cx} ${cy} L ${cx + maxR} ${cy} A ${maxR} ${maxR} 0 0 0 ${cx + maxR * Math.cos(-Math.PI/3)} ${cy + maxR * Math.sin(-Math.PI/3)} Z`}
              fill="url(#sweepGrad)" opacity="0.7"/>
          </g>
        )}

        {/* value polygon */}
        <path d={valPath} fill="url(#radarFill)" stroke={accent} strokeWidth="1.8" strokeLinejoin="round"/>

        {/* dots at vertices */}
        {valPts.map(([x, y], i) => (
          <g key={i}>
            <circle cx={x} cy={y} r="4" fill="var(--bg)" stroke={accent} strokeWidth="1.8"/>
          </g>
        ))}

        {/* center dot */}
        <circle cx={cx} cy={cy} r="2.5" fill={accent}/>

        {/* labels */}
        {showLabels && labels.map((l, i) => {
          const a = angle(i);
          const lx = cx + Math.cos(a) * (maxR + 24);
          const ly = cy + Math.sin(a) * (maxR + 24);
          const v = components[l.key];
          return (
            <g key={l.key}>
              <text x={lx} y={ly - 2} fontSize="11" fontFamily="Geist" fontWeight="500" fill="var(--text-secondary)" textAnchor="middle">{l.label}</text>
              <text x={lx} y={ly + 12} fontSize="11" fontFamily="Geist Mono" fill="var(--text)" textAnchor="middle">{v}</text>
            </g>
          );
        })}
      </svg>
    </div>
  );
};

// ────────────────────────────────────────────────────────────────────
// Donut — for allocation
// ────────────────────────────────────────────────────────────────────
const DonutChart = ({ data, size = 200, thickness = 24 }) => {
  const r = (size - thickness) / 2;
  const cx = size / 2, cy = size / 2;
  const total = data.reduce((s, d) => s + d.pct, 0);
  let acc = 0;
  const segs = data.map((d) => {
    const start = (acc / total) * 2 * Math.PI - Math.PI / 2;
    acc += d.pct;
    const end = (acc / total) * 2 * Math.PI - Math.PI / 2;
    const large = end - start > Math.PI ? 1 : 0;
    const x1 = cx + Math.cos(start) * r, y1 = cy + Math.sin(start) * r;
    const x2 = cx + Math.cos(end) * r, y2 = cy + Math.sin(end) * r;
    return { d: `M ${x1} ${y1} A ${r} ${r} 0 ${large} 1 ${x2} ${y2}`, color: d.color };
  });
  return (
    <svg width={size} height={size}>
      <circle cx={cx} cy={cy} r={r} fill="none" stroke="var(--surface-2)" strokeWidth={thickness}/>
      {segs.map((s, i) => (
        <path key={i} d={s.d} fill="none" stroke={s.color} strokeWidth={thickness} strokeLinecap="butt"/>
      ))}
    </svg>
  );
};

// ────────────────────────────────────────────────────────────────────
// Candlestick chart — small, for context
// ────────────────────────────────────────────────────────────────────
const Candles = ({ data, w = 360, h = 120 }) => {
  // synthesize OHLC from price series
  if (!data?.length) return null;
  const cands = [];
  for (let i = 0; i < data.length - 1; i += 2) {
    const a = data[i], b = data[i + 1] || a;
    const o = a, c = b;
    const hi = Math.max(a, b) * (1 + 0.003 * ((i % 3)));
    const lo = Math.min(a, b) * (1 - 0.003 * ((i % 4)));
    cands.push({ o, c, hi, lo });
  }
  const lo = drMin(cands.map(c => c.lo)), hi = drMax(cands.map(c => c.hi));
  const range = hi - lo || 1;
  const cw = w / cands.length;
  const cbw = Math.max(2, cw * 0.55);
  const y = (v) => h - ((v - lo) / range) * (h - 6) - 3;
  return (
    <svg width={w} height={h}>
      {cands.map((c, i) => {
        const x = i * cw + cw / 2;
        const up = c.c >= c.o;
        const col = up ? 'var(--emerald)' : 'var(--red)';
        const yo = y(c.o), yc = y(c.c);
        const top = Math.min(yo, yc), btm = Math.max(yo, yc);
        return (
          <g key={i} stroke={col} fill={col}>
            <line x1={x} y1={y(c.hi)} x2={x} y2={y(c.lo)} strokeWidth="1"/>
            <rect x={x - cbw / 2} y={top} width={cbw} height={Math.max(1, btm - top)} opacity={up ? 1 : 1}/>
          </g>
        );
      })}
    </svg>
  );
};

// ────────────────────────────────────────────────────────────────────
// Sector heatmap
// ────────────────────────────────────────────────────────────────────
const HeatmapCell = ({ name, val }) => {
  const positive = val >= 0;
  const intensity = Math.min(1, Math.abs(val) / 4);
  const bg = positive
    ? `color-mix(in srgb, var(--emerald) ${15 + intensity * 60}%, var(--surface-2))`
    : `color-mix(in srgb, var(--red) ${15 + intensity * 60}%, var(--surface-2))`;
  return (
    <div style={{ background: bg, borderRadius: 8, padding: '10px 12px', display: 'flex', flexDirection: 'column', gap: 2, color: 'white', minHeight: 56 }}>
      <div style={{ fontSize: 11, fontWeight: 500, opacity: 0.95 }}>{name}</div>
      <div className="mono" style={{ fontSize: 13, fontWeight: 500 }}>{positive ? '+' : ''}{val.toFixed(2)}%</div>
    </div>
  );
};

// ────────────────────────────────────────────────────────────────────
// Fair-value gauge — horizontal range with markers
// ────────────────────────────────────────────────────────────────────
const FairValueGauge = ({ current, fair, low, high }) => {
  const cPos = ((current - low) / (high - low)) * 100;
  const fPos = ((fair - low) / (high - low)) * 100;
  const undervalued = current < fair;
  return (
    <div style={{ position: 'relative', padding: '24px 8px 8px' }}>
      <div style={{ height: 6, borderRadius: 3, background: 'linear-gradient(90deg, var(--red) 0%, var(--amber) 50%, var(--emerald) 100%)', opacity: 0.5 }}/>
      <div style={{ position: 'absolute', left: `calc(${cPos}% - 1px)`, top: 18, width: 2, height: 22, background: 'var(--text)' }}/>
      <div style={{ position: 'absolute', left: `calc(${cPos}% - 28px)`, top: -2, fontSize: 10, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.06em', fontWeight: 500 }}>Current</div>
      <div style={{ position: 'absolute', left: `calc(${cPos}% - 22px)`, top: 44, fontSize: 12 }} className="mono">₹{current.toFixed(0)}</div>

      <div style={{ position: 'absolute', left: `calc(${fPos}% - 6px)`, top: 14, width: 12, height: 12, borderRadius: '50%', background: 'var(--emerald)', border: '2px solid var(--bg)' }}/>
      <div style={{ position: 'absolute', left: `calc(${fPos}% - 30px)`, top: 44, fontSize: 12, color: 'var(--emerald)' }} className="mono">Fair ₹{fair}</div>

      <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: 64, fontSize: 10.5, color: 'var(--text-muted)', fontFamily: 'Geist Mono' }}>
        <span>₹{low}</span><span>₹{high}</span>
      </div>
      <div style={{ marginTop: 12, fontSize: 12, color: undervalued ? 'var(--emerald)' : 'var(--red)', fontWeight: 500 }}>
        {undervalued ? `Undervalued by ${(((fair - current) / current) * 100).toFixed(1)}%` : `Overvalued by ${(((current - fair) / current) * 100).toFixed(1)}%`}
      </div>
    </div>
  );
};

Object.assign(window, { Sparkline, AreaChart, ScoreRing, RadarChart, DonutChart, Candles, HeatmapCell, FairValueGauge });
