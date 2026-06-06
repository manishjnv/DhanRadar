// DhanRadar — App shell (sidebar + topbar + routing) and Mobile screens

function AppShell({ theme, setTheme, screen, setScreen }) {
  const navItems = [
    { id: 'dashboard', label: 'Dashboard', icon: 'home' },
    { id: 'stock', label: 'Stock Analysis', icon: 'chart' },
    { id: 'screener', label: 'Screener', icon: 'filter' },
    { id: 'portfolio', label: 'Portfolio', icon: 'portfolio' },
  ];
  const navSecondary = [
    { id: 'compare', label: 'Compare', icon: 'compare' },
    { id: 'funds', label: 'Mutual Funds', icon: 'fund' },
    { id: 'watchlist', label: 'Watchlists', icon: 'star', pill: '4' },
    { id: 'learn', label: 'Learn', icon: 'book' },
    { id: 'alerts', label: 'Alerts', icon: 'bell', pill: '2' },
  ];

  return (
    <div className={`dr-app theme-${theme}`}>
      <div className="shell">
        {/* Sidebar */}
        <aside className="sidebar">
          <div className="brand" style={{ cursor: 'pointer' }} onClick={() => setScreen('landing')}>
            <Logo size={32}/>
            <div>
              <div className="brand-name">DhanRadar</div>
              <div className="brand-sub">Investor Console</div>
            </div>
          </div>

          <div className="nav-section-label">Workspace</div>
          {navItems.map(n => (
            <div key={n.id} className={`nav-item${screen === n.id ? ' active' : ''}`} onClick={() => setScreen(n.id)}>
              <span className="icon"><Icon name={n.icon} size={16}/></span>
              <span>{n.label}</span>
            </div>
          ))}

          <div className="nav-section-label">Discover</div>
          {navSecondary.map(n => (
            <div key={n.id} className={`nav-item${screen === n.id ? ' active' : ''}`} onClick={() => n.id === 'compare' || n.id === 'funds' || n.id === 'learn' ? setScreen(n.id) : null}>
              <span className="icon"><Icon name={n.icon} size={16}/></span>
              <span>{n.label}</span>
              {n.pill && <span className="pill">{n.pill}</span>}
            </div>
          ))}

          <div className="sidebar-footer">
            <div className="upgrade-card">
              <div className="upgrade-title">
                <Icon name="sparkles" size={14}/>
                Upgrade to Pro
              </div>
              <div className="upgrade-sub">Unlimited screeners, fair-value models, score alerts.</div>
              <button className="btn btn-primary btn-sm" style={{ width: '100%' }}>Try 14 days free</button>
            </div>
            <div className="nav-item">
              <span className="icon"><Icon name="settings" size={16}/></span>
              <span>Settings</span>
            </div>
          </div>
        </aside>

        {/* Main */}
        <div className="main">
          <div className="topbar">
            <div className="search">
              <Icon name="search" size={15} />
              <input className="search-input" placeholder="Search stocks, funds, sectors, news…"/>
              <span className="kbd">⌘K</span>
            </div>
            <div className="market-indicator">
              {DR_DATA.indices.slice(0, 3).map(idx => (
                <div className="mi" key={idx.name}>
                  <span className="mi-name">{idx.name}</span>
                  <span className="mi-val">
                    {idx.value.toLocaleString('en-IN', { maximumFractionDigits: 2 })}
                    <span className={`mi-delta ${idx.pct >= 0 ? 'pos' : 'neg'}`}>{idx.pct >= 0 ? '+' : ''}{idx.pct.toFixed(2)}%</span>
                  </span>
                </div>
              ))}
            </div>
            <div className="topbar-actions">
              <button className="icon-btn" onClick={() => setTheme(theme === 'dark' ? 'light' : 'dark')}>
                <Icon name={theme === 'dark' ? 'sun' : 'moon'} size={16}/>
              </button>
              <button className="icon-btn"><Icon name="bell" size={16}/></button>
              <button className="icon-btn"><Icon name="settings" size={16}/></button>
              <div className="avatar">AS</div>
            </div>
          </div>

          {screen === 'dashboard' && <DashboardScreen/>}
          {screen === 'stock' && <StockAnalysisScreen/>}
          {screen === 'screener' && <ScreenerScreen/>}
          {screen === 'portfolio' && <PortfolioScreen/>}
          {screen === 'compare' && <ComparePlaceholder/>}
          {screen === 'funds' && <FundsPlaceholder/>}
          {screen === 'learn' && <LearnPlaceholder/>}
        </div>
      </div>
    </div>
  );
}

// ────────────────────────────────────────────────────────────────────
// Compare & Funds & Learn — light pages
// ────────────────────────────────────────────────────────────────────
function ComparePlaceholder() {
  const sel = [DR_DATA.stocks[0], DR_DATA.stocks[1], DR_DATA.stocks[3]];
  return (
    <div className="page">
      <div className="page-h">
        <div>
          <div className="crumbs"><span>Discover</span><Icon name="chevRight" size={12}/><span className="sec">Compare</span></div>
          <h1>Compare</h1>
        </div>
        <button className="btn btn-ghost btn-sm"><Icon name="plus" size={14}/> Add stock</button>
      </div>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 16 }}>
        {sel.map(s => (
          <div key={s.sym} className="card">
            <div style={{ padding: '18px', borderBottom: '1px solid var(--border)' }}>
              <div className="row gap-3 center mb-3">
                <div className="ticker-logo" style={{ background: s.color, width: 38, height: 38 }}>{s.logo}</div>
                <div>
                  <div className="t14 w-500">{s.name}</div>
                  <div className="muted t11">{s.sym} · {s.sector}</div>
                </div>
              </div>
              <div className="mono" style={{ fontSize: 28, fontWeight: 500, letterSpacing: '-0.02em' }}>₹{s.price.toFixed(2)}</div>
              <div className={`mono t13 ${s.chg >= 0 ? 'pos' : 'neg'}`}>{s.chg >= 0 ? '+' : ''}{s.chg.toFixed(2)}%</div>
            </div>
            <div style={{ padding: 18, display: 'flex', justifyContent: 'center' }}>
              <RadarChart components={{ valuation: 50 + s.score % 40, growth: 40 + s.score % 50, quality: 60 + s.score % 35, momentum: 50 + s.score % 45, risk: 40 + s.score % 40 }} size={220} animateSweep={false}/>
            </div>
            <div className="divider"/>
            <div style={{ padding: '14px 18px' }}>
              {[['Score', s.score], ['PE', s.pe.toFixed(1) + 'x'], ['ROE', s.roe.toFixed(1) + '%'], ['Mcap', '₹' + (s.mcap/1000).toFixed(1) + 'K Cr']].map(([k, v]) => (
                <div key={k} className="row between" style={{ padding: '7px 0', borderBottom: '1px solid var(--border)' }}>
                  <span className="t12 muted">{k}</span>
                  <span className="mono t13 w-500">{v}</span>
                </div>
              ))}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

function FundsPlaceholder() {
  const funds = [
    { name: 'Parag Parikh Flexi Cap', cat: 'Flexi Cap', nav: 84.21, ret3y: 22.4, score: 92, expense: 0.62, aum: '78,420 Cr', risk: 'Moderate' },
    { name: 'Quant Small Cap Fund', cat: 'Small Cap', nav: 256.40, ret3y: 38.6, score: 88, expense: 0.62, aum: '24,180 Cr', risk: 'High' },
    { name: 'Mirae Asset Large Cap', cat: 'Large Cap', nav: 102.84, ret3y: 16.2, score: 84, expense: 0.54, aum: '37,920 Cr', risk: 'Moderate' },
    { name: 'Axis Bluechip Fund', cat: 'Large Cap', nav: 62.30, ret3y: 12.4, score: 76, expense: 0.49, aum: '34,210 Cr', risk: 'Low' },
    { name: 'HDFC Mid-Cap Opportunities', cat: 'Mid Cap', nav: 184.50, ret3y: 28.4, score: 86, expense: 0.81, aum: '64,720 Cr', risk: 'Moderate' },
  ];
  return (
    <div className="page">
      <div className="page-h">
        <div>
          <div className="crumbs"><span>Discover</span><Icon name="chevRight" size={12}/><span className="sec">Mutual Funds</span></div>
          <h1>Mutual Funds</h1>
        </div>
      </div>
      <div className="card">
        <div className="card-h"><h3>Top-rated equity funds</h3><div className="card-sub">DhanRadar score ≥ 75 · sorted by 3-yr return</div></div>
        <table className="table">
          <thead><tr><th>Fund</th><th>Category</th><th className="right">NAV</th><th className="right">3Y Return</th><th className="right">Expense</th><th className="right">AUM</th><th className="right">Risk</th><th className="right">Score</th></tr></thead>
          <tbody>
            {funds.map(f => (
              <tr key={f.name} className="row-hover">
                <td className="t13 w-500">{f.name}</td>
                <td><span className="badge badge-neutral">{f.cat}</span></td>
                <td className="right mono">{f.nav.toFixed(2)}</td>
                <td className="right mono pos w-500">+{f.ret3y.toFixed(1)}%</td>
                <td className="right mono">{f.expense.toFixed(2)}%</td>
                <td className="right mono">{f.aum}</td>
                <td className="right">
                  <span className={`badge ${f.risk === 'Low' ? 'badge-pos' : f.risk === 'Moderate' ? 'badge-warn' : 'badge-neg'}`}>{f.risk}</span>
                </td>
                <td className="right"><span className="mono w-500">{f.score}</span></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function LearnPlaceholder() {
  const topics = [
    { ico: 'book', t: 'Investing 101', d: 'Stocks, shares, mutual funds — what they actually are.', lessons: 12 },
    { ico: 'chart', t: 'Reading Financial Statements', d: 'P&L, balance sheet, cash flow without an MBA.', lessons: 8 },
    { ico: 'shield', t: 'Risk & Diversification', d: 'How to size positions and stop blowing up.', lessons: 9 },
    { ico: 'rupee', t: 'Valuation Models', d: 'DCF, multiples, and when each one lies to you.', lessons: 11 },
    { ico: 'pie', t: 'Mutual Fund Selection', d: 'Beyond past returns — expense, tracking error, alpha.', lessons: 7 },
    { ico: 'sparkles', t: 'Behavioural Finance', d: 'Why your brain is the biggest risk to your portfolio.', lessons: 6 },
  ];
  return (
    <div className="page">
      <div className="page-h">
        <div>
          <div className="crumbs"><span className="sec">Education Hub</span></div>
          <h1>Learn investing — in plain English</h1>
        </div>
      </div>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 16 }}>
        {topics.map((t, i) => (
          <div key={i} className="card" style={{ padding: 20, cursor: 'pointer' }}>
            <div className="feature-ico"><Icon name={t.ico} size={18}/></div>
            <div className="t16 w-500 mt-2">{t.t}</div>
            <div className="muted t12 mt-2" style={{ lineHeight: 1.5 }}>{t.d}</div>
            <div className="row between center mt-4">
              <span className="t11 muted">{t.lessons} lessons</span>
              <span className="t12 w-500" style={{ color: 'var(--blue)' }}>Start →</span>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

// ────────────────────────────────────────────────────────────────────
// Root App with internal nav (each instance is independent)
// ────────────────────────────────────────────────────────────────────
function DhanRadarApp({ initialTheme = 'light', initialScreen = 'landing' }) {
  const [theme, setTheme] = React.useState(initialTheme);
  const [screen, setScreen] = React.useState(initialScreen);
  const toggle = () => setTheme(t => t === 'dark' ? 'light' : 'dark');

  if (screen === 'landing') {
    return (
      <div className={`dr-app theme-${theme}`}>
        <LandingScreen
          onEnterApp={() => setScreen('dashboard')}
          onThemeToggle={toggle}
          theme={theme}
        />
      </div>
    );
  }
  return <AppShell theme={theme} setTheme={setTheme} screen={screen} setScreen={setScreen}/>;
}

Object.assign(window, { AppShell, DhanRadarApp, ComparePlaceholder, FundsPlaceholder, LearnPlaceholder });
