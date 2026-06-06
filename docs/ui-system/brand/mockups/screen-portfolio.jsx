// DhanRadar — Portfolio Dashboard

function PortfolioScreen() {
  const [tab, setTab] = React.useState('holdings');

  // Totals
  const totalValue = DR_DATA.holdings.reduce((s, h) => s + h.value, 0);
  const totalPnl = DR_DATA.holdings.reduce((s, h) => s + h.pnl, 0);
  const totalInvested = totalValue - totalPnl;
  const totalPct = (totalPnl / totalInvested) * 100;

  // Portfolio value series
  const portfolioSeries = React.useMemo(() => {
    const base = DR_DATA.series(73, 120, 0.45, 0.018);
    const scale = totalValue / base[base.length - 1];
    return base.map(v => v * scale);
  }, []);

  // Avg portfolio score (weighted)
  const avgScore = Math.round(
    DR_DATA.holdings.reduce((s, h) => s + h.score * (h.value / totalValue), 0)
  );

  return (
    <div className="page">
      <div className="page-h">
        <div>
          <div className="crumbs"><span>Portfolio</span><Icon name="chevRight" size={12}/><span className="sec">Overview</span></div>
          <h1>Good afternoon, Aarav</h1>
        </div>
        <div className="row gap-2">
          <button className="btn btn-ghost btn-sm"><Icon name="plus" size={14}/> Add holding</button>
          <button className="btn btn-ghost btn-sm"><Icon name="settings" size={14}/> Sync broker</button>
          <button className="btn btn-primary btn-sm">Download report</button>
        </div>
      </div>

      {/* Top summary row */}
      <div style={{ display: 'grid', gridTemplateColumns: '2fr 1fr 1fr', gap: 16, marginBottom: 16 }}>
        {/* Value card with chart */}
        <div className="card" style={{ overflow: 'hidden', position: 'relative' }}>
          <div style={{ padding: '18px 22px' }}>
            <div className="row between" style={{ alignItems: 'flex-start' }}>
              <div>
                <div className="t11 upper muted" style={{ marginBottom: 4, fontWeight: 500, letterSpacing: '0.06em' }}>Total Portfolio Value</div>
                <div className="row gap-3 center">
                  <span className="mono" style={{ fontSize: 36, fontWeight: 500, letterSpacing: '-0.025em', lineHeight: 1 }}>
                    ₹{totalValue.toLocaleString('en-IN', { maximumFractionDigits: 0 })}
                  </span>
                  <span className="pos t14 w-500">+₹{Math.round(totalPnl).toLocaleString('en-IN')} ({totalPct.toFixed(2)}%)</span>
                </div>
                <div className="muted t12" style={{ marginTop: 6 }}>Invested ₹{Math.round(totalInvested).toLocaleString('en-IN')} · 8 holdings</div>
              </div>
              <div className="row gap-1">
                {['1M','3M','6M','1Y','All'].map((p, i) => (
                  <button key={p} className={`chip${i === 3 ? ' active' : ''}`}>{p}</button>
                ))}
              </div>
            </div>
          </div>
          <div style={{ padding: '0 14px' }}>
            <AreaChart data={portfolioSeries} w={760} h={170} color="var(--emerald)"/>
          </div>
          <div style={{ padding: '8px 22px 16px', borderTop: '1px solid var(--border)', display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 16 }}>
            <div className="stat"><span className="stat-label">Day Change</span><span className="stat-value pos">+₹4,824</span></div>
            <div className="stat"><span className="stat-label">XIRR</span><span className="stat-value pos">18.42%</span></div>
            <div className="stat"><span className="stat-label">vs NIFTY 50</span><span className="stat-value pos">+4.6%</span></div>
            <div className="stat"><span className="stat-label">Sharpe</span><span className="stat-value">1.42</span></div>
          </div>
        </div>

        {/* Portfolio score */}
        <div className="card">
          <div className="card-h"><h3>Portfolio Score</h3><div className="card-sub">weighted</div></div>
          <div style={{ padding: '8px 16px 16px', display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 10 }}>
            <ScoreRing score={avgScore} size={120} stroke={10} />
            <div className="t13 sec">Above average · Top 22%</div>
            <div className="divider" style={{ width: '100%', margin: '6px 0' }}/>
            <div style={{ width: '100%', display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8 }}>
              <div className="col" style={{ alignItems: 'center' }}>
                <div className="mono w-500 t14">B+</div>
                <div className="muted t10 upper">Diversity</div>
              </div>
              <div className="col" style={{ alignItems: 'center' }}>
                <div className="mono w-500 t14">Low</div>
                <div className="muted t10 upper">Concentration</div>
              </div>
            </div>
          </div>
        </div>

        {/* Allocation donut */}
        <div className="card">
          <div className="card-h"><h3>Sector Allocation</h3></div>
          <div style={{ padding: '4px 16px 16px', display: 'flex', gap: 14, alignItems: 'center' }}>
            <div style={{ position: 'relative' }}>
              <DonutChart data={DR_DATA.sectorAllocation} size={120} thickness={14}/>
              <div style={{ position: 'absolute', inset: 0, display: 'grid', placeItems: 'center', flexDirection: 'column' }}>
                <div className="col" style={{ textAlign: 'center' }}>
                  <div className="t10 upper muted">Holdings</div>
                  <div className="mono w-500 t18">{DR_DATA.holdings.length}</div>
                </div>
              </div>
            </div>
            <div style={{ flex: 1 }}>
              {DR_DATA.sectorAllocation.slice(0, 5).map(s => (
                <div key={s.name} className="legend-row">
                  <div className="sw" style={{ background: s.color }}/>
                  <div className="nm t12">{s.name}</div>
                  <div className="vl t12">{s.pct.toFixed(1)}%</div>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>

      {/* Tabs */}
      <div className="tabs" style={{ marginBottom: 16 }}>
        {['holdings','watchlist','alerts','transactions'].map(t => (
          <button key={t} className={`tab${tab === t ? ' active' : ''}`} onClick={() => setTab(t)}>
            {t[0].toUpperCase() + t.slice(1)}
          </button>
        ))}
      </div>

      {tab === 'holdings' && <HoldingsTab/>}
      {tab === 'watchlist' && <WatchlistTab/>}
      {tab === 'alerts' && <AlertsTab/>}
      {tab === 'transactions' && <TransactionsTab/>}
    </div>
  );
}

function HoldingsTab() {
  const [sortKey, setSortKey] = React.useState('value');
  const [sortDir, setSortDir] = React.useState('desc');

  const sorted = [...DR_DATA.holdings].sort((a, b) => {
    const av = a[sortKey], bv = b[sortKey];
    if (typeof av === 'string') return sortDir === 'asc' ? av.localeCompare(bv) : bv.localeCompare(av);
    return sortDir === 'asc' ? av - bv : bv - av;
  });

  const flip = (k) => { if (sortKey === k) setSortDir(d => d === 'asc' ? 'desc' : 'asc'); else { setSortKey(k); setSortDir('desc'); } };
  const SortHead = ({ k, children, align }) => (
    <th className={align === 'right' ? 'right' : ''} onClick={() => flip(k)} style={{ cursor: 'pointer' }}>
      <span style={{ display: 'inline-flex', alignItems: 'center', gap: 4 }}>
        {children}
        {sortKey === k && <Icon name={sortDir === 'asc' ? 'arrowUp' : 'arrowDown'} size={10}/>}
      </span>
    </th>
  );

  return (
    <div className="card">
      <div className="card-h">
        <h3>Holdings</h3>
        <div className="card-sub">Click any row to analyze</div>
        <div className="row gap-2" style={{ marginLeft: 'auto' }}>
          <button className="chip"><Icon name="grid" size={12}/> Group by sector</button>
          <button className="chip"><Icon name="filter" size={12}/> Filter</button>
        </div>
      </div>
      <table className="table">
        <thead>
          <tr>
            <SortHead k="name">Stock</SortHead>
            <SortHead k="qty" align="right">Qty</SortHead>
            <SortHead k="avg" align="right">Avg</SortHead>
            <SortHead k="ltp" align="right">LTP</SortHead>
            <SortHead k="value" align="right">Value</SortHead>
            <SortHead k="pnl" align="right">P&L</SortHead>
            <SortHead k="pnlPct" align="right">Return</SortHead>
            <SortHead k="weight" align="right">Weight</SortHead>
            <SortHead k="score" align="right">Score</SortHead>
          </tr>
        </thead>
        <tbody>
          {sorted.map(h => {
            const stock = DR_DATA.stocks.find(s => s.sym === h.sym);
            return (
              <tr key={h.sym} className="row-hover">
                <td>
                  <div className="ticker">
                    <div className="ticker-logo" style={{ background: stock?.color || '#1E5EFF' }}>{stock?.logo || h.sym[0]}</div>
                    <div>
                      <div className="ticker-name">{h.name}</div>
                      <div className="ticker-sub">{h.sym}</div>
                    </div>
                  </div>
                </td>
                <td className="right mono">{h.qty}</td>
                <td className="right mono">{h.avg.toFixed(2)}</td>
                <td className="right mono">{h.ltp.toFixed(2)}</td>
                <td className="right mono w-500">₹{h.value.toLocaleString('en-IN', { maximumFractionDigits: 0 })}</td>
                <td className={`right mono w-500 ${h.pnl >= 0 ? 'pos' : 'neg'}`}>{h.pnl >= 0 ? '+' : ''}₹{Math.abs(h.pnl).toLocaleString('en-IN', { maximumFractionDigits: 0 })}</td>
                <td className={`right mono ${h.pnlPct >= 0 ? 'pos' : 'neg'}`}>{h.pnlPct >= 0 ? '+' : ''}{h.pnlPct.toFixed(2)}%</td>
                <td className="right">
                  <div className="row" style={{ justifyContent: 'flex-end', gap: 6 }}>
                    <div style={{ width: 48, height: 4, background: 'var(--surface-2)', borderRadius: 2, overflow: 'hidden' }}>
                      <div style={{ width: `${h.weight * 3}%`, height: '100%', background: 'var(--blue)' }}/>
                    </div>
                    <span className="mono t12">{h.weight.toFixed(1)}%</span>
                  </div>
                </td>
                <td className="right">
                  <span className={`badge ${h.score >= 80 ? 'badge-pos' : h.score >= 65 ? 'badge-neutral' : 'badge-warn'}`}>{h.score}</span>
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

function WatchlistTab() {
  return (
    <div style={{ display: 'grid', gridTemplateColumns: '2fr 1fr', gap: 16 }}>
      <div className="card">
        <div className="card-h"><h3>Watchlist · Primary</h3></div>
        <table className="table">
          <thead><tr><th>Stock</th><th className="right">LTP</th><th className="right">Chg</th><th className="right">Score</th><th className="right">Signal</th></tr></thead>
          <tbody>
            {DR_DATA.watchlist.map(w => (
              <tr key={w.sym} className="row-hover">
                <td><div className="row gap-2"><span className="mono w-500">{w.sym}</span><span className="t12 muted">{w.name}</span></div></td>
                <td className="right mono">{w.ltp.toFixed(2)}</td>
                <td className={`right mono ${w.chg >= 0 ? 'pos' : 'neg'}`}>{w.chg >= 0 ? '+' : ''}{w.chg.toFixed(2)}%</td>
                <td className="right mono">{w.score}</td>
                <td className="right"><span className={`badge ${w.score >= 75 ? 'badge-pos' : 'badge-neutral'}`}>{w.score >= 75 ? 'Buy' : 'Hold'}</span></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <div className="card">
        <div className="card-h"><h3>Sector Movers</h3></div>
        <div style={{ padding: '4px 16px 16px' }}>
          <div className="t11 upper" style={{ color: 'var(--emerald)', margin: '8px 0', fontWeight: 500 }}>Gainers</div>
          {DR_DATA.movers.gainers.map(m => (
            <div key={m.sym} className="row between" style={{ padding: '8px 0', borderBottom: '1px solid var(--border)' }}>
              <span className="mono t13">{m.sym}</span>
              <span className="mono t13 pos">+{m.pct.toFixed(2)}%</span>
            </div>
          ))}
          <div className="t11 upper" style={{ color: 'var(--red)', margin: '14px 0 8px', fontWeight: 500 }}>Losers</div>
          {DR_DATA.movers.losers.map(m => (
            <div key={m.sym} className="row between" style={{ padding: '8px 0', borderBottom: '1px solid var(--border)' }}>
              <span className="mono t13">{m.sym}</span>
              <span className="mono t13 neg">{m.pct.toFixed(2)}%</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

function AlertsTab() {
  const alerts = [
    { sym: 'TCS', t: 'Price crossed', cond: '> ₹4,100', when: '2 hrs ago', triggered: true },
    { sym: 'RELIANCE', t: 'Score change', cond: '85 → 86', when: 'Today', triggered: true },
    { sym: 'HDFCBANK', t: 'Earnings due', cond: 'Q2 results · 22 Oct', when: '3 days', triggered: false },
    { sym: 'INFY', t: 'PE below', cond: '< 28', when: 'Active', triggered: false },
  ];
  return (
    <div className="card">
      <div className="card-h"><h3>Alerts</h3><div className="card-sub">{alerts.length} configured</div>
        <button className="btn btn-ghost btn-sm" style={{ marginLeft: 'auto' }}><Icon name="plus" size={14}/> New alert</button>
      </div>
      {alerts.map((a, i) => (
        <div key={i} style={{ padding: '14px 18px', borderBottom: i === alerts.length - 1 ? 'none' : '1px solid var(--border)' }} className="row gap-4">
          <span style={{ width: 8, height: 8, borderRadius: '50%', background: a.triggered ? 'var(--emerald)' : 'var(--text-muted)' }}/>
          <span className="mono w-500 t13" style={{ width: 100 }}>{a.sym}</span>
          <span className="t13 sec" style={{ width: 140 }}>{a.t}</span>
          <span className="mono t13 muted" style={{ flex: 1 }}>{a.cond}</span>
          <span className="muted t11">{a.when}</span>
          <button className="icon-btn"><Icon name="settings" size={14}/></button>
        </div>
      ))}
    </div>
  );
}

function TransactionsTab() {
  const txns = [
    { d: '12 May 2026', sym: 'RELIANCE', side: 'Buy', qty: 8, p: 2756.40 },
    { d: '08 May 2026', sym: 'TCS', side: 'Buy', qty: 4, p: 4081.20 },
    { d: '02 May 2026', sym: 'HDFCBANK', side: 'Sell', qty: 12, p: 1689.55 },
    { d: '26 Apr 2026', sym: 'BHARTIARTL', side: 'Buy', qty: 12, p: 1542.10 },
    { d: '18 Apr 2026', sym: 'INFY', side: 'Buy', qty: 10, p: 1714.80 },
  ];
  return (
    <div className="card">
      <div className="card-h"><h3>Recent Transactions</h3></div>
      <table className="table">
        <thead><tr><th>Date</th><th>Stock</th><th>Side</th><th className="right">Qty</th><th className="right">Price</th><th className="right">Total</th></tr></thead>
        <tbody>
          {txns.map((t, i) => (
            <tr key={i} className="row-hover">
              <td className="mono">{t.d}</td>
              <td className="mono w-500">{t.sym}</td>
              <td><span className={`badge ${t.side === 'Buy' ? 'badge-pos' : 'badge-neg'}`}>{t.side}</span></td>
              <td className="right mono">{t.qty}</td>
              <td className="right mono">{t.p.toFixed(2)}</td>
              <td className="right mono w-500">₹{(t.qty * t.p).toLocaleString('en-IN', { maximumFractionDigits: 0 })}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

Object.assign(window, { PortfolioScreen });
