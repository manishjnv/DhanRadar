// DhanRadar — Stock Screener

function ScreenerScreen() {
  const [filters, setFilters] = React.useState({
    sectors: new Set(['Banking', 'IT Services', 'Energy']),
    mcapMin: 50,        // in K Cr
    peMax: 40,
    roeMin: 12,
    deMax: 1.5,
    revGrowthMin: 5,
    scoreMin: 65,
  });
  const [sortKey, setSortKey] = React.useState('score');
  const [sortDir, setSortDir] = React.useState('desc');

  const toggleSector = (s) => setFilters(f => {
    const ns = new Set(f.sectors);
    if (ns.has(s)) ns.delete(s); else ns.add(s);
    return { ...f, sectors: ns };
  });

  const filtered = DR_DATA.stocks.filter(s =>
    filters.sectors.has(s.sector) &&
    s.mcap / 1000 >= filters.mcapMin &&
    s.pe <= filters.peMax &&
    s.roe >= filters.roeMin &&
    s.score >= filters.scoreMin
  ).sort((a, b) => {
    const av = a[sortKey], bv = b[sortKey];
    if (typeof av === 'string') return sortDir === 'asc' ? av.localeCompare(bv) : bv.localeCompare(av);
    return sortDir === 'asc' ? av - bv : bv - av;
  });

  const sectors = ['Banking', 'IT Services', 'Energy', 'FMCG', 'Auto', 'Telecom', 'Construction', 'Consumer'];

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
    <div className="page">
      <div className="page-h">
        <div>
          <div className="crumbs"><span>Discover</span><Icon name="chevRight" size={12}/><span className="sec">Stock Screener</span></div>
          <h1>Stock Screener</h1>
        </div>
        <div className="row gap-2">
          <button className="btn btn-ghost btn-sm"><Icon name="list" size={14}/> Saved screens (4)</button>
          <button className="btn btn-ghost btn-sm"><Icon name="plus" size={14}/> Save this screen</button>
          <button className="btn btn-primary btn-sm">Export CSV</button>
        </div>
      </div>

      {/* Quick presets */}
      <div className="row gap-2 wrap mb-4">
        <span className="t11 upper muted" style={{ marginRight: 8, alignSelf: 'center', fontWeight: 500 }}>Presets:</span>
        {['High-Quality Compounders', 'Value · PE < 20', 'Dividend Aristocrats', 'Momentum Movers', 'Turnaround Stories', 'Small-cap Hidden Gems'].map((p, i) => (
          <button key={p} className={`chip${i === 0 ? ' active' : ''}`}>{p}</button>
        ))}
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '260px 1fr', gap: 16 }}>
        {/* Filters sidebar */}
        <div className="card" style={{ alignSelf: 'flex-start' }}>
          <div className="card-h" style={{ padding: '14px 16px 12px' }}>
            <h3>Filters</h3>
            <div className="card-sub" style={{ marginLeft: 'auto' }}>{filtered.length} results</div>
          </div>
          <div className="divider"/>

          {/* Sector */}
          <div className="filter-row">
            <div className="filter-label">Sector</div>
            <div className="row gap-1 wrap">
              {sectors.map(s => (
                <button key={s} className={`chip${filters.sectors.has(s) ? ' active' : ''}`} onClick={() => toggleSector(s)}>{s}</button>
              ))}
            </div>
          </div>

          {/* Score */}
          <div className="filter-row">
            <div className="filter-label">
              <span>DhanRadar Score</span>
              <span className="mono">≥ {filters.scoreMin}</span>
            </div>
            <input type="range" min="0" max="100" value={filters.scoreMin}
              onChange={(e) => setFilters({...filters, scoreMin: +e.target.value})}/>
          </div>

          {/* Market cap */}
          <div className="filter-row">
            <div className="filter-label">
              <span>Market Cap</span>
              <span className="mono">≥ ₹{filters.mcapMin}K Cr</span>
            </div>
            <input type="range" min="0" max="2000" step="10" value={filters.mcapMin}
              onChange={(e) => setFilters({...filters, mcapMin: +e.target.value})}/>
          </div>

          {/* PE */}
          <div className="filter-row">
            <div className="filter-label">
              <span>PE Ratio</span>
              <span className="mono">≤ {filters.peMax}x</span>
            </div>
            <input type="range" min="5" max="100" value={filters.peMax}
              onChange={(e) => setFilters({...filters, peMax: +e.target.value})}/>
          </div>

          {/* ROE */}
          <div className="filter-row">
            <div className="filter-label">
              <span>ROE</span>
              <span className="mono">≥ {filters.roeMin}%</span>
            </div>
            <input type="range" min="0" max="40" value={filters.roeMin}
              onChange={(e) => setFilters({...filters, roeMin: +e.target.value})}/>
          </div>

          {/* D/E */}
          <div className="filter-row">
            <div className="filter-label">
              <span>Debt / Equity</span>
              <span className="mono">≤ {filters.deMax.toFixed(1)}</span>
            </div>
            <input type="range" min="0" max="3" step="0.1" value={filters.deMax}
              onChange={(e) => setFilters({...filters, deMax: +e.target.value})}/>
          </div>

          {/* Revenue growth */}
          <div className="filter-row">
            <div className="filter-label">
              <span>Revenue Growth (5Y)</span>
              <span className="mono">≥ {filters.revGrowthMin}%</span>
            </div>
            <input type="range" min="0" max="30" value={filters.revGrowthMin}
              onChange={(e) => setFilters({...filters, revGrowthMin: +e.target.value})}/>
          </div>

          <div style={{ padding: '12px 14px', borderTop: '1px solid var(--border)' }}>
            <button className="btn btn-ghost btn-sm" style={{ width: '100%' }}>+ Add filter</button>
          </div>
        </div>

        {/* Results */}
        <div className="card">
          <div className="card-h">
            <h3>Results</h3>
            <div className="card-sub">{filtered.length} of {DR_DATA.stocks.length} stocks match</div>
            <div className="row gap-2" style={{ marginLeft: 'auto' }}>
              <button className="chip"><Icon name="grid" size={12}/> Cards</button>
              <button className="chip active"><Icon name="list" size={12}/> Table</button>
            </div>
          </div>
          <div style={{ overflow: 'auto' }}>
            <table className="table">
              <thead>
                <tr>
                  <SortHead k="name">Company</SortHead>
                  <SortHead k="sector">Sector</SortHead>
                  <SortHead k="price" align="right">Price</SortHead>
                  <SortHead k="chg" align="right">1D</SortHead>
                  <SortHead k="mcap" align="right">Mcap (Cr)</SortHead>
                  <SortHead k="pe" align="right">PE</SortHead>
                  <SortHead k="roe" align="right">ROE</SortHead>
                  <SortHead k="score" align="right">Score</SortHead>
                  <th className="right">Signal</th>
                </tr>
              </thead>
              <tbody>
                {filtered.map(s => (
                  <tr key={s.sym} className="row-hover">
                    <td>
                      <div className="ticker">
                        <div className="ticker-logo" style={{ background: s.color }}>{s.logo}</div>
                        <div>
                          <div className="ticker-name">{s.name}</div>
                          <div className="ticker-sub">{s.sym}</div>
                        </div>
                      </div>
                    </td>
                    <td className="t12 sec">{s.sector}</td>
                    <td className="right mono">{s.price.toFixed(2)}</td>
                    <td className={`right mono ${s.chg >= 0 ? 'pos' : 'neg'}`}>{s.chg >= 0 ? '+' : ''}{s.chg.toFixed(2)}%</td>
                    <td className="right mono">{(s.mcap / 1000).toFixed(1)}K</td>
                    <td className="right mono">{s.pe.toFixed(1)}</td>
                    <td className="right mono">{s.roe.toFixed(1)}%</td>
                    <td className="right">
                      <div className="row" style={{ justifyContent: 'flex-end', gap: 6 }}>
                        <div style={{ width: 40, height: 4, background: 'var(--surface-2)', borderRadius: 2, overflow: 'hidden' }}>
                          <div style={{ width: `${s.score}%`, height: '100%', background: s.score >= 80 ? 'var(--emerald)' : s.score >= 65 ? 'var(--blue)' : 'var(--amber)' }}/>
                        </div>
                        <span className="mono w-500">{s.score}</span>
                      </div>
                    </td>
                    <td className="right">
                      <span className={`badge ${s.signal === 'Strong Buy' ? 'signal-strong-buy' : s.signal === 'Buy' ? 'badge-pos' : 'badge-neutral'}`}>{s.signal}</span>
                    </td>
                  </tr>
                ))}
                {filtered.length === 0 && (
                  <tr><td colSpan="9" style={{ padding: 60, textAlign: 'center' }}>
                    <div className="muted">No stocks match these filters. Relax some criteria.</div>
                  </td></tr>
                )}
              </tbody>
            </table>
          </div>
          <div style={{ padding: '12px 16px', borderTop: '1px solid var(--border)', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <span className="t12 muted">Showing 1–{filtered.length} of {filtered.length}</span>
            <div className="row gap-1">
              <button className="chip">‹ Prev</button>
              <button className="chip active">1</button>
              <button className="chip">Next ›</button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

// ────────────────────────────────────────────────────────────────────
// DASHBOARD (home / overview after login)
// ────────────────────────────────────────────────────────────────────
function DashboardScreen() {
  return (
    <div className="page">
      <div className="page-h">
        <div>
          <div className="crumbs"><span className="sec">Dashboard</span></div>
          <h1>Markets at a glance</h1>
        </div>
        <div className="row gap-2">
          <button className="btn btn-ghost btn-sm"><Icon name="filter" size={14}/> Customize</button>
        </div>
      </div>

      {/* Sector heatmap */}
      <div className="card mb-4">
        <div className="card-h"><h3>Sector Heatmap · Today</h3><div className="card-sub">% change · NSE</div></div>
        <div style={{ padding: '4px 16px 16px', display: 'grid', gridTemplateColumns: 'repeat(6, 1fr)', gap: 6 }}>
          {[
            { name: 'Banks', val: 1.42 }, { name: 'IT', val: 0.82 }, { name: 'Auto', val: 2.14 }, { name: 'FMCG', val: -0.84 },
            { name: 'Pharma', val: 0.42 }, { name: 'Energy', val: 1.84 }, { name: 'Metals', val: 2.62 }, { name: 'Realty', val: -1.22 },
            { name: 'Telecom', val: 2.04 }, { name: 'Capital Gds', val: 0.62 }, { name: 'Cement', val: -0.42 }, { name: 'Media', val: -2.14 },
          ].map((c, i) => <HeatmapCell key={i} name={c.name} val={c.val}/>)}
        </div>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 16 }}>
        {/* Top scored stocks */}
        <div className="card">
          <div className="card-h"><h3>Top Scored · This Week</h3></div>
          {DR_DATA.stocks.sort((a, b) => b.score - a.score).slice(0, 5).map((s, i) => (
            <div key={s.sym} className="row gap-3 center" style={{ padding: '10px 16px', borderTop: i === 0 ? '1px solid var(--border)' : 'none', borderBottom: '1px solid var(--border)' }}>
              <div className="ticker-logo" style={{ background: s.color, width: 30, height: 30 }}>{s.logo}</div>
              <div className="col" style={{ flex: 1 }}>
                <div className="t13 w-500">{s.sym}</div>
                <div className="muted t11">{s.sector}</div>
              </div>
              <div className="col" style={{ alignItems: 'flex-end' }}>
                <div className="mono t13">₹{s.price.toFixed(0)}</div>
                <div className={`t11 mono ${s.chg >= 0 ? 'pos' : 'neg'}`}>{s.chg >= 0 ? '+' : ''}{s.chg.toFixed(2)}%</div>
              </div>
              <ScoreRing score={s.score} size={40} stroke={4}/>
            </div>
          ))}
        </div>

        {/* News */}
        <div className="card">
          <div className="card-h"><h3>Market News</h3></div>
          {DR_DATA.news.map((n, i) => (
            <div key={i} style={{ padding: '12px 16px', borderTop: i === 0 ? '1px solid var(--border)' : 'none', borderBottom: '1px solid var(--border)' }}>
              <div className="row gap-2 mb-2">
                <span className="badge badge-info">{n.tag}</span>
                <span className="muted t11">{n.t}</span>
              </div>
              <div className="t13 w-500" style={{ lineHeight: 1.4 }}>{n.title}</div>
            </div>
          ))}
        </div>

        {/* Movers */}
        <div className="card">
          <div className="card-h"><h3>Market Movers</h3></div>
          <div style={{ padding: '4px 16px 16px' }}>
            <div className="t11 upper" style={{ color: 'var(--emerald)', margin: '8px 0', fontWeight: 500 }}>Top Gainers</div>
            {DR_DATA.movers.gainers.map(m => {
              const stock = DR_DATA.stocks.find(s => s.sym === m.sym) || { color: '#1E5EFF', logo: m.sym[0] };
              return (
                <div key={m.sym} className="row between" style={{ padding: '8px 0', borderBottom: '1px solid var(--border)' }}>
                  <div className="row gap-2">
                    <div className="ticker-logo" style={{ background: stock.color, width: 22, height: 22, fontSize: 10 }}>{stock.logo}</div>
                    <span className="mono t13">{m.sym}</span>
                  </div>
                  <Sparkline data={DR_DATA.series(m.sym.charCodeAt(0)*3, 30, 0.6, 0.02)} w={50} h={18} color="var(--emerald)"/>
                  <span className="mono t13 pos">+{m.pct.toFixed(2)}%</span>
                </div>
              );
            })}
            <div className="t11 upper" style={{ color: 'var(--red)', margin: '14px 0 8px', fontWeight: 500 }}>Top Losers</div>
            {DR_DATA.movers.losers.map(m => {
              const stock = DR_DATA.stocks.find(s => s.sym === m.sym) || { color: '#6B7280', logo: m.sym[0] };
              return (
                <div key={m.sym} className="row between" style={{ padding: '8px 0', borderBottom: '1px solid var(--border)' }}>
                  <div className="row gap-2">
                    <div className="ticker-logo" style={{ background: stock.color, width: 22, height: 22, fontSize: 10 }}>{stock.logo}</div>
                    <span className="mono t13">{m.sym}</span>
                  </div>
                  <Sparkline data={DR_DATA.series(m.sym.charCodeAt(0)*5, 30, -0.4, 0.02)} w={50} h={18} color="var(--red)"/>
                  <span className="mono t13 neg">{m.pct.toFixed(2)}%</span>
                </div>
              );
            })}
          </div>
        </div>
      </div>
    </div>
  );
}

Object.assign(window, { ScreenerScreen, DashboardScreen });
