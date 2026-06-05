// DhanRadar — Mobile screens (used inside iOS frames)

function MobileApp({ theme = 'dark', initialScreen = 'home' }) {
  const [screen, setScreen] = React.useState(initialScreen);

  return (
    <div className={`dr-app theme-${theme} mob-app`}>
      {screen === 'home' && <MobHome onNav={setScreen}/>}
      {screen === 'stock' && <MobStock onNav={setScreen}/>}
      {screen === 'portfolio' && <MobPortfolio onNav={setScreen}/>}
      {screen === 'screener' && <MobScreener onNav={setScreen}/>}
      <MobTabbar active={screen} onNav={setScreen}/>
    </div>
  );
}

function MobTabbar({ active, onNav }) {
  const tabs = [
    { id: 'home', label: 'Markets', icon: 'home' },
    { id: 'screener', label: 'Screener', icon: 'filter' },
    { id: 'stock', label: 'Discover', icon: 'radar' },
    { id: 'portfolio', label: 'Portfolio', icon: 'portfolio' },
  ];
  return (
    <div className="mob-tabbar">
      {tabs.map(t => (
        <button key={t.id} className={`mob-tab${active === t.id ? ' active' : ''}`} onClick={() => onNav(t.id)}>
          <span className="icon"><Icon name={t.icon} size={20}/></span>
          <span>{t.label}</span>
        </button>
      ))}
    </div>
  );
}

function MobHome({ onNav }) {
  return (
    <>
      <div className="mob-header">
        <div>
          <div className="mob-greet">Good evening</div>
          <div className="mob-name">Aarav S.</div>
        </div>
        <div className="row gap-2">
          <button className="icon-btn"><Icon name="bell" size={18}/></button>
          <div className="avatar" style={{ width: 32, height: 32, fontSize: 12 }}>AS</div>
        </div>
      </div>
      <div className="mob-content">
        <div className="mob-search">
          <Icon name="search" size={15}/>
          <span>Search stocks, funds…</span>
        </div>

        {/* Indices strip */}
        <div className="row gap-2 mt-4 noscroll" style={{ overflowX: 'auto', margin: '16px -16px 0', padding: '0 16px' }}>
          {DR_DATA.indices.map(idx => (
            <div key={idx.name} className="mob-card" style={{ minWidth: 140, padding: 12, flex: '0 0 auto' }}>
              <div className="t10 upper muted" style={{ fontWeight: 500, letterSpacing: '0.08em' }}>{idx.name}</div>
              <div className="mono t16 w-500 mt-2">{idx.value.toLocaleString('en-IN', { maximumFractionDigits: 2 })}</div>
              <div className={`mono t11 ${idx.pct >= 0 ? 'pos' : 'neg'}`} style={{ marginTop: 2 }}>
                {idx.pct >= 0 ? '+' : ''}{idx.pct.toFixed(2)}%
              </div>
              <div className="mt-2"><Sparkline data={DR_DATA.series(idx.name.charCodeAt(0)*3, 30, idx.pct >= 0 ? 0.4 : -0.3, 0.02)} w={116} h={24} color={idx.pct >= 0 ? 'var(--emerald)' : 'var(--red)'} fill/></div>
            </div>
          ))}
        </div>

        {/* Top scored */}
        <div className="row between mt-6 mb-3" style={{ alignItems: 'baseline' }}>
          <div className="t14 w-500">Top-scored today</div>
          <span className="t11" style={{ color: 'var(--blue)' }}>See all →</span>
        </div>
        <div className="mob-card" style={{ padding: 0 }}>
          {DR_DATA.stocks.sort((a, b) => b.score - a.score).slice(0, 4).map((s, i) => (
            <div key={s.sym} className="row gap-3 center" style={{ padding: '12px 14px', borderBottom: i === 3 ? 'none' : '1px solid var(--border)' }} onClick={() => onNav('stock')}>
              <div className="ticker-logo" style={{ background: s.color, width: 32, height: 32 }}>{s.logo}</div>
              <div className="col" style={{ flex: 1, minWidth: 0 }}>
                <div className="t13 w-500" style={{ whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{s.name}</div>
                <div className="muted t11">{s.sym}</div>
              </div>
              <div className="col" style={{ alignItems: 'flex-end' }}>
                <div className="mono t13">₹{s.price.toFixed(0)}</div>
                <div className={`mono t11 ${s.chg >= 0 ? 'pos' : 'neg'}`}>{s.chg >= 0 ? '+' : ''}{s.chg.toFixed(2)}%</div>
              </div>
              <ScoreRing score={s.score} size={38} stroke={4}/>
            </div>
          ))}
        </div>

        {/* News */}
        <div className="row between mt-6 mb-3" style={{ alignItems: 'baseline' }}>
          <div className="t14 w-500">Market pulse</div>
          <span className="t11" style={{ color: 'var(--blue)' }}>More →</span>
        </div>
        <div className="mob-card" style={{ padding: 0 }}>
          {DR_DATA.news.slice(0, 3).map((n, i) => (
            <div key={i} style={{ padding: '12px 14px', borderBottom: i === 2 ? 'none' : '1px solid var(--border)' }}>
              <div className="row gap-2 mb-2">
                <span className="badge badge-info" style={{ fontSize: 10 }}>{n.tag}</span>
                <span className="muted t10">{n.t}</span>
              </div>
              <div className="t12 w-500" style={{ lineHeight: 1.4 }}>{n.title}</div>
            </div>
          ))}
        </div>

        {/* Sector heatmap mini */}
        <div className="t14 w-500 mt-6 mb-3">Sectors today</div>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 6 }}>
          {[
            { name: 'Banks', val: 1.42 }, { name: 'IT', val: 0.82 }, { name: 'Auto', val: 2.14 },
            { name: 'FMCG', val: -0.84 }, { name: 'Energy', val: 1.84 }, { name: 'Metals', val: 2.62 },
          ].map((c, i) => <HeatmapCell key={i} name={c.name} val={c.val}/>)}
        </div>
      </div>
    </>
  );
}

function MobStock({ onNav }) {
  const s = DR_DATA.focus;
  const data = React.useMemo(() => DR_DATA.series(91, 80, 0.5, 0.025).map(v => v / DR_DATA.series(91, 80, 0.5, 0.025)[79] * s.price), []);
  return (
    <>
      <div className="mob-header" style={{ paddingBottom: 0 }}>
        <button className="icon-btn" onClick={() => onNav('home')}>
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M15 6 L9 12 L15 18"/></svg>
        </button>
        <div className="t13 w-500">Stock Analysis</div>
        <button className="icon-btn"><Icon name="star" size={18}/></button>
      </div>
      <div className="mob-content" style={{ paddingTop: 8 }}>
        {/* Header */}
        <div className="row gap-3 center mb-3" style={{ padding: '8px 0' }}>
          <div className="ticker-logo" style={{ background: '#0A1F4A', width: 40, height: 40 }}>R</div>
          <div className="col" style={{ flex: 1 }}>
            <div className="t14 w-500">Reliance Industries</div>
            <div className="muted t11">NSE: RELIANCE · Energy</div>
          </div>
        </div>
        <div className="row gap-3 center">
          <div className="mono" style={{ fontSize: 30, fontWeight: 500, letterSpacing: '-0.025em' }}>₹{s.price.toFixed(2)}</div>
          <span className="pos mono t13">+{s.chg.toFixed(2)} (+{s.chgPct}%)</span>
        </div>

        {/* Chart */}
        <div className="mt-3" style={{ margin: '0 -16px' }}>
          <AreaChart data={data} w={358} h={170} color="var(--emerald)"/>
        </div>
        <div className="row gap-1 mt-2">
          {['1D','1W','1M','6M','1Y','5Y'].map((p, i) => (
            <button key={p} className={`chip${i === 4 ? ' active' : ''}`} style={{ flex: 1, justifyContent: 'center' }}>{p}</button>
          ))}
        </div>

        {/* DhanRadar Score */}
        <div className="mob-card mt-4">
          <div className="row between center mb-3">
            <div>
              <div className="t11 upper muted" style={{ fontWeight: 500 }}>DhanRadar Score</div>
              <div className="row gap-2 center mt-2">
                <div className="mono" style={{ fontSize: 40, fontWeight: 500, letterSpacing: '-0.03em', lineHeight: 1 }}>86</div>
                <span className="badge signal-strong-buy">Strong Buy</span>
              </div>
            </div>
            <RadarChart components={s.components} size={130} animateSweep={true} showLabels={false}/>
          </div>
          <div className="col gap-2 mt-3">
            {[
              ['Valuation', 78, 'var(--emerald)'],
              ['Growth', 82, 'var(--emerald)'],
              ['Quality', 91, 'var(--emerald)'],
              ['Momentum', 88, 'var(--emerald)'],
              ['Risk', 71, 'var(--amber)'],
            ].map(([n, v, c]) => (
              <div key={n} className="row gap-3 t12">
                <span style={{ width: 70, color: 'var(--text-secondary)' }}>{n}</span>
                <div style={{ flex: 1, height: 4, background: 'var(--surface-2)', borderRadius: 3, overflow: 'hidden' }}>
                  <div style={{ width: `${v}%`, height: '100%', background: c, borderRadius: 3 }}/>
                </div>
                <span className="mono" style={{ width: 22, textAlign: 'right' }}>{v}</span>
              </div>
            ))}
          </div>
        </div>

        {/* Fair value */}
        <div className="mob-card mt-3">
          <div className="t11 upper muted mb-2" style={{ fontWeight: 500 }}>Fair Value · 1-year</div>
          <div className="row between center">
            <div className="mono" style={{ fontSize: 24, fontWeight: 500 }}>₹3,120</div>
            <span className="badge badge-pos">+9.8% upside</span>
          </div>
          <div className="mt-3" style={{ height: 6, borderRadius: 3, background: 'linear-gradient(90deg, var(--red), var(--amber), var(--emerald))', opacity: 0.4, position: 'relative' }}>
            <div style={{ position: 'absolute', left: '55%', top: -3, width: 2, height: 12, background: 'var(--text)' }}/>
            <div style={{ position: 'absolute', left: '78%', top: -2, width: 10, height: 10, borderRadius: '50%', background: 'var(--emerald)', border: '2px solid var(--bg)' }}/>
          </div>
          <div className="row between mt-2">
            <span className="t11 muted mono">Current ₹2,841</span>
            <span className="t11 mono" style={{ color: 'var(--emerald)' }}>Target ₹3,120</span>
          </div>
        </div>

        {/* Action */}
        <button className="btn btn-primary mt-4" style={{ width: '100%', height: 44 }}>
          Buy on connected broker
        </button>
      </div>
    </>
  );
}

function MobPortfolio({ onNav }) {
  const totalValue = DR_DATA.holdings.reduce((s, h) => s + h.value, 0);
  const totalPnl = DR_DATA.holdings.reduce((s, h) => s + h.pnl, 0);
  const totalPct = (totalPnl / (totalValue - totalPnl)) * 100;
  const portfolioSeries = DR_DATA.series(73, 80, 0.45, 0.018);

  return (
    <>
      <div className="mob-header">
        <div>
          <div className="mob-greet">Portfolio</div>
          <div className="mob-name">Overview</div>
        </div>
        <button className="icon-btn"><Icon name="plus" size={18}/></button>
      </div>
      <div className="mob-content">
        {/* Value */}
        <div className="mob-card">
          <div className="t11 upper muted" style={{ fontWeight: 500, letterSpacing: '0.08em' }}>Total Value</div>
          <div className="mono mt-2" style={{ fontSize: 30, fontWeight: 500, letterSpacing: '-0.025em' }}>
            ₹{totalValue.toLocaleString('en-IN', { maximumFractionDigits: 0 })}
          </div>
          <div className="row gap-3 mt-2">
            <span className="pos mono t13 w-500">+₹{Math.round(totalPnl).toLocaleString('en-IN')}</span>
            <span className="pos mono t13">+{totalPct.toFixed(2)}%</span>
          </div>
          <div className="mt-3" style={{ margin: '0 -16px -8px' }}>
            <AreaChart data={portfolioSeries} w={358} h={100} color="var(--emerald)"/>
          </div>
        </div>

        {/* Quick stats */}
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8, marginTop: 12 }}>
          <div className="mob-card" style={{ padding: 14 }}>
            <div className="t10 upper muted" style={{ fontWeight: 500 }}>XIRR</div>
            <div className="mono t18 w-500 pos">18.42%</div>
          </div>
          <div className="mob-card" style={{ padding: 14 }}>
            <div className="t10 upper muted" style={{ fontWeight: 500 }}>vs NIFTY</div>
            <div className="mono t18 w-500 pos">+4.6%</div>
          </div>
        </div>

        {/* Allocation */}
        <div className="mob-card mt-4">
          <div className="row between center mb-3">
            <div className="t14 w-500">Sector Allocation</div>
            <span className="t11" style={{ color: 'var(--blue)' }}>Detail →</span>
          </div>
          <div className="row gap-4 center">
            <DonutChart data={DR_DATA.sectorAllocation} size={100} thickness={12}/>
            <div style={{ flex: 1 }}>
              {DR_DATA.sectorAllocation.slice(0, 4).map(s => (
                <div key={s.name} className="row gap-2 center" style={{ padding: '5px 0' }}>
                  <div style={{ width: 8, height: 8, borderRadius: 2, background: s.color }}/>
                  <span className="t12" style={{ flex: 1 }}>{s.name}</span>
                  <span className="mono t12 muted">{s.pct.toFixed(1)}%</span>
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* Holdings */}
        <div className="row between mt-4 mb-3" style={{ alignItems: 'baseline' }}>
          <div className="t14 w-500">Holdings · {DR_DATA.holdings.length}</div>
          <span className="t11 muted">By value ↓</span>
        </div>
        <div className="mob-card" style={{ padding: 0 }}>
          {DR_DATA.holdings.slice(0, 5).map((h, i) => {
            const stock = DR_DATA.stocks.find(s => s.sym === h.sym);
            return (
              <div key={h.sym} className="row gap-3 center" style={{ padding: '12px 14px', borderBottom: i === 4 ? 'none' : '1px solid var(--border)' }} onClick={() => onNav('stock')}>
                <div className="ticker-logo" style={{ background: stock?.color, width: 30, height: 30 }}>{stock?.logo}</div>
                <div className="col" style={{ flex: 1, minWidth: 0 }}>
                  <div className="t13 w-500">{h.sym}</div>
                  <div className="muted t11">{h.qty} · avg ₹{h.avg.toFixed(0)}</div>
                </div>
                <div className="col" style={{ alignItems: 'flex-end' }}>
                  <div className="mono t13 w-500">₹{(h.value/1000).toFixed(1)}K</div>
                  <div className={`mono t11 ${h.pnlPct >= 0 ? 'pos' : 'neg'}`}>+{h.pnlPct.toFixed(2)}%</div>
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </>
  );
}

function MobScreener({ onNav }) {
  const filtered = DR_DATA.stocks.filter(s => s.score >= 75).sort((a, b) => b.score - a.score);
  return (
    <>
      <div className="mob-header">
        <div>
          <div className="mob-greet">Discover</div>
          <div className="mob-name">Screener</div>
        </div>
        <button className="icon-btn"><Icon name="filter" size={18}/></button>
      </div>
      <div className="mob-content">
        <div className="row gap-2 wrap mb-3">
          {['High Quality', 'Value', 'Momentum', 'Dividend'].map((p, i) => (
            <button key={p} className={`chip${i === 0 ? ' active' : ''}`}>{p}</button>
          ))}
        </div>
        <div className="mob-card" style={{ padding: 0 }}>
          {filtered.map((s, i) => (
            <div key={s.sym} className="row gap-3 center" style={{ padding: '14px', borderBottom: i === filtered.length - 1 ? 'none' : '1px solid var(--border)' }} onClick={() => onNav('stock')}>
              <div className="ticker-logo" style={{ background: s.color, width: 36, height: 36 }}>{s.logo}</div>
              <div className="col" style={{ flex: 1, minWidth: 0 }}>
                <div className="t13 w-500">{s.name}</div>
                <div className="muted t11 mono">{s.sym} · {s.sector}</div>
              </div>
              <div className="col" style={{ alignItems: 'flex-end' }}>
                <div className="mono t13">₹{s.price.toFixed(0)}</div>
                <div className={`mono t11 ${s.chg >= 0 ? 'pos' : 'neg'}`}>{s.chg >= 0 ? '+' : ''}{s.chg.toFixed(2)}%</div>
              </div>
              <ScoreRing score={s.score} size={42} stroke={5}/>
            </div>
          ))}
        </div>
      </div>
    </>
  );
}

Object.assign(window, { MobileApp, MobHome, MobStock, MobPortfolio, MobScreener });
