// DhanRadar — Stock Analysis page (Reliance Industries)

function StockAnalysisScreen() {
  const [period, setPeriod] = React.useState('1Y');
  const [tab, setTab] = React.useState('overview');
  const s = DR_DATA.focus;

  const periodMap = {
    '1D': { len: 78, vol: 0.006, trend: 0.05, seed: 12 },
    '1W': { len: 60, vol: 0.012, trend: 0.10, seed: 34 },
    '1M': { len: 100, vol: 0.018, trend: 0.18, seed: 56 },
    '6M': { len: 120, vol: 0.022, trend: 0.35, seed: 78 },
    '1Y': { len: 180, vol: 0.024, trend: 0.45, seed: 91 },
    '5Y': { len: 200, vol: 0.030, trend: 0.55, seed: 23 },
  };
  const cfg = periodMap[period];
  const priceData = React.useMemo(() => {
    const raw = DR_DATA.series(cfg.seed, cfg.len, cfg.trend, cfg.vol);
    // scale to end around current price
    const target = s.price;
    const last = raw[raw.length - 1];
    return raw.map(v => (v / last) * target);
  }, [period]);

  const up = s.chg >= 0;

  return (
    <div className="page">
      {/* Header */}
      <div className="page-h">
        <div>
          <div className="crumbs">
            <span>Stocks</span><Icon name="chevRight" size={12}/>
            <span>Energy</span><Icon name="chevRight" size={12}/>
            <span className="sec">RELIANCE</span>
          </div>
          <div className="row gap-3 center">
            <div className="ticker-logo" style={{ background: '#0A1F4A', width: 44, height: 44, fontSize: 16, borderRadius: 10 }}>R</div>
            <div>
              <h1 style={{ marginBottom: 2 }}>Reliance Industries Ltd.</h1>
              <div className="muted t12">
                <span className="mono">NSE: RELIANCE</span> · {s.sector} · Mcap {s.mcap}
              </div>
            </div>
          </div>
        </div>
        <div className="row gap-2">
          <button className="btn btn-ghost btn-sm"><Icon name="star" size={14}/> Watch</button>
          <button className="btn btn-ghost btn-sm"><Icon name="compare" size={14}/> Compare</button>
          <button className="btn btn-ghost btn-sm"><Icon name="bell" size={14}/> Set alert</button>
          <button className="btn btn-primary btn-sm">Buy on broker <Icon name="arrowRight" size={14}/></button>
        </div>
      </div>

      {/* Price + score row */}
      <div style={{ display: 'grid', gridTemplateColumns: '1.6fr 1fr', gap: 16, marginBottom: 16 }}>
        {/* Price card */}
        <div className="card">
          <div style={{ padding: '18px 22px', borderBottom: '1px solid var(--border)' }}>
            <div className="row between center" style={{ marginBottom: 14 }}>
              <div>
                <div className="row gap-3 center">
                  <span className="mono" style={{ fontSize: 36, fontWeight: 500, letterSpacing: '-0.025em', lineHeight: 1 }}>₹{s.price.toFixed(2)}</span>
                  <span className={up ? 'pos' : 'neg'} style={{ fontSize: 15, fontWeight: 500 }}>
                    {up ? '+' : ''}{s.chg.toFixed(2)} ({up ? '+' : ''}{s.chgPct}%)
                  </span>
                </div>
                <div className="muted t11" style={{ marginTop: 6 }}>NSE · Live · 14:32:08 IST · Vol {s.volume}</div>
              </div>
              <div className="row gap-1">
                {['1D','1W','1M','6M','1Y','5Y'].map(p => (
                  <button key={p} className={`chip${period === p ? ' active' : ''}`} style={{ minWidth: 38, justifyContent: 'center' }} onClick={() => setPeriod(p)}>{p}</button>
                ))}
              </div>
            </div>
            <AreaChart data={priceData} w={760} h={240} color={up ? 'var(--emerald)' : 'var(--red)'} />
          </div>

          {/* Range stats */}
          <div style={{ padding: '14px 22px', display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 16 }}>
            <div className="stat"><span className="stat-label">Day Range</span><span className="stat-value">{s.dayLow.toFixed(0)}–{s.dayHigh.toFixed(0)}</span></div>
            <div className="stat"><span className="stat-label">52-Wk Range</span><span className="stat-value">{s.yLow.toFixed(0)}–{s.yHigh.toFixed(0)}</span></div>
            <div className="stat"><span className="stat-label">PE Ratio</span><span className="stat-value">24.2 <span className="muted t11 mono">x</span></span></div>
            <div className="stat"><span className="stat-label">Div Yield</span><span className="stat-value">0.34<span className="muted t11 mono">%</span></span></div>
          </div>
        </div>

        {/* Score card */}
        <div className="card" style={{ display: 'flex', flexDirection: 'column' }}>
          <div className="card-h" style={{ padding: '14px 18px' }}>
            <h3>DhanRadar Score</h3>
            <div className="muted t11">Updated 12 May 2026</div>
            <span style={{ marginLeft: 'auto' }} className="badge signal-strong-buy">
              <span style={{ width: 6, height: 6, borderRadius: '50%', background: 'var(--emerald)' }}/>
              Strong Buy
            </span>
          </div>
          <div style={{ padding: '0 14px 14px', position: 'relative' }}>
            <RadarChart components={s.components} size={300} animateSweep={true}/>
            <div style={{ position: 'absolute', top: 130, left: 0, right: 0, textAlign: 'center', pointerEvents: 'none' }}>
              <div className="mono" style={{ fontSize: 44, fontWeight: 500, letterSpacing: '-0.04em', lineHeight: 1 }}>86</div>
              <div className="t10 upper muted" style={{ marginTop: 2 }}>out of 100</div>
            </div>
          </div>
          <div style={{ padding: '0 18px 16px', borderTop: '1px solid var(--border)' }}>
            <div className="muted t11" style={{ margin: '10px 0 4px' }}>Top 8% in Energy · #2 of 142 peers</div>
            <div className="row gap-2 mt-2">
              <button className="btn btn-ghost btn-sm grow"><Icon name="info" size={13}/> How is this calculated?</button>
            </div>
          </div>
        </div>
      </div>

      {/* Tabs */}
      <div className="tabs" style={{ marginBottom: 16 }}>
        {['overview','financials','peers','swot','valuation'].map(t => (
          <button key={t} className={`tab${tab === t ? ' active' : ''}`} onClick={() => setTab(t)}>
            {t === 'swot' ? 'SWOT' : t[0].toUpperCase() + t.slice(1)}
          </button>
        ))}
      </div>

      {/* Tab content */}
      {tab === 'overview' && <OverviewTab/>}
      {tab === 'financials' && <FinancialsTab/>}
      {tab === 'peers' && <PeersTab/>}
      {tab === 'swot' && <SWOTTab/>}
      {tab === 'valuation' && <ValuationTab/>}
    </div>
  );
}

function OverviewTab() {
  const s = DR_DATA.focus;
  return (
    <div style={{ display: 'grid', gridTemplateColumns: '2fr 1fr', gap: 16 }}>
      {/* Pros/cons */}
      <div className="card">
        <div className="card-h"><h3>Pros & Cons</h3><div className="card-sub">Generated from latest financials and price action</div></div>
        <div style={{ padding: '0 18px 16px', display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }}>
          <div>
            <div className="t11 upper" style={{ color: 'var(--emerald)', marginBottom: 10, fontWeight: 500 }}>▲ Strengths</div>
            <div className="col gap-3">
              {s.pros.map((p, i) => (
                <div key={i} className="row gap-2" style={{ alignItems: 'flex-start' }}>
                  <Icon name="check" size={14} stroke={2} />
                  <div className="t13 sec" style={{ lineHeight: 1.5 }}>{p}</div>
                </div>
              ))}
            </div>
          </div>
          <div>
            <div className="t11 upper" style={{ color: 'var(--red)', marginBottom: 10, fontWeight: 500 }}>▼ Concerns</div>
            <div className="col gap-3">
              {s.cons.map((p, i) => (
                <div key={i} className="row gap-2" style={{ alignItems: 'flex-start' }}>
                  <Icon name="close" size={14} stroke={2}/>
                  <div className="t13 sec" style={{ lineHeight: 1.5 }}>{p}</div>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>

      {/* Fair value */}
      <div className="card">
        <div className="card-h"><h3>Fair Value Estimate</h3><div className="card-sub">1-year</div></div>
        <div style={{ padding: '0 18px 18px' }}>
          <div className="row between center mb-2">
            <span className="mono" style={{ fontSize: 28, fontWeight: 500, letterSpacing: '-0.03em' }}>₹{s.fairValue.toLocaleString('en-IN')}</span>
            <span className="badge badge-pos">+9.8%</span>
          </div>
          <FairValueGauge current={s.price} fair={s.fairValue} low={s.yLow} high={s.yHigh}/>
        </div>
      </div>

      {/* Key metrics */}
      <div className="card" style={{ gridColumn: '1 / -1' }}>
        <div className="card-h"><h3>Key Metrics</h3><div className="card-sub">vs sector median · 5-yr CAGR shown where applicable</div></div>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(6, 1fr)' }}>
          {[
            ['Market Cap', '₹19.21L Cr', '—'],
            ['EPS (TTM)', '₹121.7', '+8.4% YoY'],
            ['ROE', '9.4%', 'vs 11.2% sector'],
            ['Debt/Equity', '0.42', 'Healthy'],
            ['Rev. CAGR (5Y)', '14.2%', '+'],
            ['Profit CAGR (5Y)', '11.8%', '+'],
            ['Promoter Hold', '50.3%', '+22bps'],
            ['FII Holding', '22.8%', '−18bps'],
            ['Book Value', '₹1,184', '+'],
            ['Beta', '1.04', 'Market-like'],
            ['Free Cash Flow', '₹62.4K Cr', '+'],
            ['Operating Margin', '17.8%', '+'],
          ].map(([k, v, sub], i) => (
            <div key={i} style={{ padding: '14px 16px', borderRight: (i+1) % 6 === 0 ? 'none' : '1px solid var(--border)', borderBottom: i < 6 ? '1px solid var(--border)' : 'none' }}>
              <div className="t11 upper muted" style={{ letterSpacing: '0.06em', fontWeight: 500 }}>{k}</div>
              <div className="mono t16 w-500" style={{ marginTop: 4 }}>{v}</div>
              <div className="t11 muted" style={{ marginTop: 2 }}>{sub}</div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

function FinancialsTab() {
  const f = DR_DATA.focus.financials;
  return (
    <div className="card">
      <div className="card-h">
        <h3>Financial Statements</h3>
        <div className="card-sub">in ₹ Crore · standalone</div>
        <div className="row gap-2" style={{ marginLeft: 'auto' }}>
          <button className="chip active">Annual</button>
          <button className="chip">Quarterly</button>
        </div>
      </div>
      <table className="table">
        <thead>
          <tr>
            <th>Metric</th>
            <th className="right">FY22</th>
            <th className="right">FY23</th>
            <th className="right">FY24</th>
            <th className="right">FY25</th>
            <th className="right">Trend</th>
            <th className="right">YoY</th>
          </tr>
        </thead>
        <tbody>
          {f.map(r => {
            const vals = [r.y2022, r.y2023, r.y2024, r.y2025];
            const yoy = ((vals[3] - vals[2]) / vals[2]) * 100;
            return (
              <tr key={r.label} className="row-hover">
                <td>{r.label}</td>
                {vals.map((v, i) => <td key={i} className="right mono">{typeof v === 'number' && v > 100 ? v.toLocaleString('en-IN') : v}</td>)}
                <td className="right"><Sparkline data={vals} w={70} h={22} color={yoy >= 0 ? 'var(--emerald)' : 'var(--red)'} fill /></td>
                <td className={`right mono ${yoy >= 0 ? 'pos' : 'neg'}`}>{yoy >= 0 ? '+' : ''}{yoy.toFixed(1)}%</td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

function PeersTab() {
  const peers = DR_DATA.focus.peers;
  return (
    <div className="card">
      <div className="card-h"><h3>Peer Comparison</h3><div className="card-sub">Energy · Conglomerate</div></div>
      <table className="table">
        <thead>
          <tr>
            <th>Company</th>
            <th className="right">Score</th>
            <th className="right">PE</th>
            <th className="right">P/B</th>
            <th className="right">ROE</th>
            <th className="right">Mcap (Cr)</th>
            <th className="right">Signal</th>
          </tr>
        </thead>
        <tbody>
          {peers.map((p, i) => {
            const signal = p.score >= 80 ? 'Buy' : p.score >= 65 ? 'Hold' : 'Avoid';
            const cls = p.score >= 80 ? 'badge-pos' : p.score >= 65 ? 'badge-neutral' : 'badge-neg';
            return (
              <tr key={p.sym} className="row-hover" style={i === 0 ? { background: 'var(--blue-soft)' } : {}}>
                <td>
                  <div className="row gap-2">
                    <span className="mono w-500">{p.sym}</span>
                    {i === 0 && <span className="badge badge-info">Current</span>}
                  </div>
                </td>
                <td className="right">
                  <div className="row" style={{ justifyContent: 'flex-end', gap: 8 }}>
                    <div style={{ width: 56, height: 5, background: 'var(--surface-2)', borderRadius: 3, overflow: 'hidden' }}>
                      <div style={{ width: `${p.score}%`, height: '100%', background: p.score >= 80 ? 'var(--emerald)' : p.score >= 65 ? 'var(--amber)' : 'var(--red)' }}/>
                    </div>
                    <span className="mono w-500">{p.score}</span>
                  </div>
                </td>
                <td className="right mono">{p.pe.toFixed(1)}x</td>
                <td className="right mono">{p.pb.toFixed(1)}</td>
                <td className="right mono">{p.roe.toFixed(1)}%</td>
                <td className="right mono">{p.mcap}</td>
                <td className="right"><span className={`badge ${cls}`}>{signal}</span></td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

function SWOTTab() {
  const { strengths, weaknesses, opportunities, threats } = DR_DATA.focus.swot;
  const sections = [
    { t: 'Strengths', items: strengths, color: 'var(--emerald)', ico: 'arrowUp' },
    { t: 'Weaknesses', items: weaknesses, color: 'var(--red)', ico: 'arrowDown' },
    { t: 'Opportunities', items: opportunities, color: 'var(--blue)', ico: 'sparkles' },
    { t: 'Threats', items: threats, color: 'var(--amber)', ico: 'bolt' },
  ];
  return (
    <div className="swot-grid">
      {sections.map(sec => (
        <div key={sec.t} className="swot-cell">
          <div className="swot-title" style={{ color: sec.color }}>
            <Icon name={sec.ico} size={13}/>
            {sec.t}
          </div>
          <ul>
            {sec.items.map((x, i) => <li key={i}>{x}</li>)}
          </ul>
        </div>
      ))}
    </div>
  );
}

function ValuationTab() {
  return (
    <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }}>
      <div className="card">
        <div className="card-h"><h3>Multi-model Fair Value</h3><div className="card-sub">3 models, weighted</div></div>
        <div style={{ padding: '4px 18px 18px' }}>
          {[
            { name: 'Discounted Cash Flow', val: 3240, weight: 50 },
            { name: 'Relative (PE band)', val: 2980, weight: 30 },
            { name: 'Earnings Power Value', val: 3060, weight: 20 },
          ].map(m => (
            <div key={m.name} style={{ padding: '12px 0', borderBottom: '1px solid var(--border)' }}>
              <div className="row between center mb-2">
                <span className="t13 w-500">{m.name}</span>
                <span className="mono t14 w-500">₹{m.val.toLocaleString('en-IN')}</span>
              </div>
              <div className="row gap-3 center">
                <div style={{ flex: 1, height: 4, background: 'var(--surface-2)', borderRadius: 2, overflow: 'hidden' }}>
                  <div style={{ width: `${(m.val / 3500) * 100}%`, height: '100%', background: 'var(--blue)' }}/>
                </div>
                <span className="muted t11 mono">Weight {m.weight}%</span>
              </div>
            </div>
          ))}
          <div className="row between center" style={{ marginTop: 18, padding: 14, borderRadius: 10, background: 'var(--blue-soft)' }}>
            <div>
              <div className="t11 upper muted" style={{ color: 'var(--blue)', fontWeight: 500 }}>Weighted Fair Value</div>
              <div className="mono" style={{ fontSize: 28, fontWeight: 500, letterSpacing: '-0.025em' }}>₹3,120</div>
            </div>
            <span className="badge badge-pos">+9.8% upside</span>
          </div>
        </div>
      </div>

      <div className="card">
        <div className="card-h"><h3>Valuation vs Peers</h3><div className="card-sub">PE band over 5 years</div></div>
        <div style={{ padding: '14px 22px 18px' }}>
          <AreaChart data={DR_DATA.series(42, 60, 0.1, 0.025).map(v => v / 5)} w={400} h={200} color="var(--blue)"/>
          <div className="row gap-4 mt-3">
            <div className="row gap-2"><span style={{ width: 10, height: 2, background: 'var(--blue)' }}/><span className="t11 muted">RELIANCE PE</span></div>
            <div className="row gap-2"><span style={{ width: 10, height: 2, background: 'var(--text-muted)' }}/><span className="t11 muted">Sector median</span></div>
            <div className="row gap-2"><span style={{ width: 10, height: 2, background: 'var(--amber)' }}/><span className="t11 muted">5-yr avg band</span></div>
          </div>
        </div>
      </div>
    </div>
  );
}

Object.assign(window, { StockAnalysisScreen });
