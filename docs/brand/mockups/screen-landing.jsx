// DhanRadar — desktop screens (Landing, Stock Analysis, Portfolio, Screener)

// ────────────────────────────────────────────────────────────────────
// LANDING
// ────────────────────────────────────────────────────────────────────
function LandingScreen({ onEnterApp, onThemeToggle, theme }) {
  const [q, setQ] = React.useState('');
  const [openFaq, setOpenFaq] = React.useState(0);

  const suggest = q.length > 0 ? DR_DATA.stocks.filter(s =>
    s.sym.toLowerCase().includes(q.toLowerCase()) ||
    s.name.toLowerCase().includes(q.toLowerCase())
  ).slice(0, 5) : [];

  const features = [
    { ico: 'radar', t: 'DhanRadar Score', d: 'A single 0–100 score that fuses valuation, growth, quality, momentum and risk. Built by analysts, not influencers.' },
    { ico: 'sparkles', t: 'Fair Value Estimate', d: 'See whether a stock is over- or under-valued today using multi-model intrinsic value.' },
    { ico: 'filter', t: 'Powerful Screeners', d: '50+ filters across fundamentals, technicals and quality signals. Save and share screens.' },
    { ico: 'compare', t: 'Side-by-side Compare', d: 'Pit any two or three stocks (or funds) against each other across 80+ data points.' },
    { ico: 'shield', t: 'Risk-aware Funds', d: 'Mutual fund analysis with Sharpe, Sortino, downside capture and rolling returns.' },
    { ico: 'book', t: 'Plain-English Insights', d: 'Every metric explained. From “PE ratio” to “debt to equity” — learn while you research.' },
  ];

  const faqs = [
    { q: 'What is the DhanRadar Score?', a: 'A composite 0–100 score blending five factors: valuation (cheap vs the market), growth (revenue, EPS, sales trajectory), quality (ROE, margins, cash flow), momentum (price and earnings momentum) and risk (debt, volatility, drawdowns). Each factor is normalised against the stock’s sector and peer set, so a 90 in Banking and a 90 in IT mean the same thing.' },
    { q: 'How is this different from a broker?', a: 'We don’t execute trades — we help you decide what to research. Bring your own broker. Plug into Zerodha, Groww, Upstox or any DP for live portfolio sync.' },
    { q: 'Is DhanRadar SEBI registered?', a: 'DhanRadar is a research analytics product. We do not provide tailored advice or buy/sell recommendations. Investments are subject to market risks; please read all scheme-related documents carefully.' },
    { q: 'Do you support mutual funds?', a: 'Yes — every equity, hybrid, debt and index fund in India is covered. Rolling returns, expense ratio, alpha, beta, Sharpe, downside capture, manager track record and category percentile are all surfaced.' },
    { q: 'Can I cancel anytime?', a: 'Of course. Pro and Premium are month-to-month. Cancel from your settings, no questions asked.' },
  ];

  return (
    <div className={`landing theme-${theme}`}>
      {/* Nav */}
      <nav className="landing-nav">
        <div className="brand" style={{ display: 'flex', gap: 10, alignItems: 'center', cursor: 'pointer' }}>
          <Logo size={28}/>
          <div>
            <div style={{ fontWeight: 600, fontSize: 15, letterSpacing: '-0.01em' }}>DhanRadar</div>
          </div>
        </div>
        <div className="links">
          <a>Stocks</a>
          <a>Mutual Funds</a>
          <a>Screener</a>
          <a>Compare</a>
          <a>Learn</a>
          <a>Pricing</a>
        </div>
        <div className="right">
          <button className="icon-btn" onClick={onThemeToggle}>
            <Icon name={theme === 'dark' ? 'sun' : 'moon'} />
          </button>
          <button className="btn btn-ghost btn-sm" onClick={onEnterApp}>Sign in</button>
          <button className="btn btn-primary btn-sm" onClick={onEnterApp}>Get started — free</button>
        </div>
      </nav>

      {/* Hero */}
      <section className="hero">
        <div className="grid-bg" />
        <div style={{ position: 'relative' }}>
          <div className="hero-eyebrow">
            <span className="dot"/>
            Markets open · NIFTY 50 ▲ 0.58%
          </div>
          <h1>
            Spot better<br/>
            investments <span className="accent">before</span> the crowd.
          </h1>
          <div className="hero-sub">
            DhanRadar scans 4,200+ Indian stocks and 2,800 mutual funds, then distils everything into a single 0–100 score —
            so you can stop guessing and start investing with conviction.
          </div>

          <div className="hero-search">
            <Icon name="search" size={18} />
            <input
              placeholder='Search for "Reliance", "Parag Parikh Flexi Cap", or any stock…'
              value={q} onChange={(e) => setQ(e.target.value)} />
            <button className="btn btn-primary btn-sm h-btn">
              Analyze <Icon name="arrowRight" size={14}/>
            </button>
            {suggest.length > 0 && (
              <div className="hero-suggest">
                {suggest.map(s => (
                  <div key={s.sym} className="row" style={{ padding: '12px 14px', gap: 12, borderBottom: '1px solid var(--border)', cursor: 'pointer' }} onClick={onEnterApp}>
                    <div className="ticker-logo" style={{ background: s.color, width: 32, height: 32 }}>{s.logo}</div>
                    <div className="col" style={{ flex: 1 }}>
                      <div className="ticker-name">{s.name}</div>
                      <div className="ticker-sub">{s.sym} · {s.sector}</div>
                    </div>
                    <div className="badge badge-info">Score {s.score}</div>
                    <div className="mono t13">₹{s.price.toFixed(2)}</div>
                  </div>
                ))}
              </div>
            )}
          </div>

          <div className="hero-trust">
            <div className="row gap-2"><span className="stars">★★★★★</span> 4.8 · 12,400 reviews</div>
            <div>Trusted by 240,000 retail investors</div>
            <div className="row gap-2"><Icon name="shield" size={14}/> SEBI-RA registered partners</div>
          </div>
        </div>

        {/* Score showcase */}
        <div className="hero-showcase">
          <div className="showcase-card">
            <div className="showcase-head">
              <div className="ticker-logo" style={{ background: '#0A1F4A' }}>R</div>
              <div className="col">
                <div style={{ fontWeight: 500, fontSize: 14 }}>Reliance Industries · RELIANCE</div>
                <div className="ticker-sub">NSE · Energy</div>
              </div>
              <div className="row gap-3" style={{ marginLeft: 'auto' }}>
                <div className="col" style={{ alignItems: 'flex-end' }}>
                  <div className="mono w-500" style={{ fontSize: 18 }}>₹2,841.30</div>
                  <div className="pos mono t12">+51.40 (+1.84%)</div>
                </div>
              </div>
            </div>

            <div style={{ padding: 22, display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 24, alignItems: 'center' }}>
              <RadarChart components={DR_DATA.focus.components} size={260} />
              <div className="col gap-4">
                <div>
                  <div className="t11 upper muted" style={{ marginBottom: 6 }}>DhanRadar Score</div>
                  <div className="row gap-3 center">
                    <div className="mono" style={{ fontSize: 56, fontWeight: 500, letterSpacing: '-0.04em', lineHeight: 1 }}>86</div>
                    <div className="col">
                      <span className="badge signal-strong-buy" style={{ padding: '3px 10px' }}>Strong Buy</span>
                      <div className="muted t11" style={{ marginTop: 4 }}>Top 8% in Energy sector</div>
                    </div>
                  </div>
                </div>
                <div className="divider"/>
                <div className="col gap-2">
                  {[
                    ['Valuation', 78, 'var(--emerald)'],
                    ['Growth', 82, 'var(--emerald)'],
                    ['Quality', 91, 'var(--emerald)'],
                    ['Momentum', 88, 'var(--emerald)'],
                    ['Risk', 71, 'var(--amber)'],
                  ].map(([n, v, c]) => (
                    <div key={n} className="row gap-3 t12">
                      <span style={{ width: 76, color: 'var(--text-secondary)' }}>{n}</span>
                      <div style={{ flex: 1, height: 5, background: 'var(--surface-2)', borderRadius: 3, overflow: 'hidden' }}>
                        <div style={{ width: `${v}%`, height: '100%', background: c, borderRadius: 3 }}/>
                      </div>
                      <span className="mono" style={{ width: 24, textAlign: 'right' }}>{v}</span>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          </div>

          <div className="col gap-4">
            <div className="showcase-card" style={{ padding: 18 }}>
              <div className="t11 upper muted" style={{ marginBottom: 10 }}>Fair Value · 1-year target</div>
              <div className="row between center" style={{ marginBottom: 4 }}>
                <div className="mono" style={{ fontSize: 32, fontWeight: 500, letterSpacing: '-0.03em' }}>₹3,120</div>
                <span className="badge badge-pos">+9.8% upside</span>
              </div>
              <div className="muted t12">DCF · Relative valuation · Earnings power model</div>
              <FairValueGauge current={2841} fair={3120} low={2221} high={3217} />
            </div>

            <div className="showcase-card" style={{ padding: 18 }}>
              <div className="t11 upper muted" style={{ marginBottom: 12 }}>Recent signals</div>
              <div className="col gap-3">
                {[
                  { t: 'Earnings beat', d: 'Q2 PAT ₹17,394 Cr vs ₹16,800 Cr est.', col: 'var(--emerald)' },
                  { t: 'Momentum shift', d: '50-DMA crossed above 200-DMA', col: 'var(--blue)' },
                  { t: 'Insider buying', d: 'Promoter holding up 22 bps QoQ', col: 'var(--emerald)' },
                ].map((s, i) => (
                  <div key={i} className="row gap-3 center">
                    <div style={{ width: 8, height: 8, borderRadius: '50%', background: s.col }}/>
                    <div className="col" style={{ flex: 1 }}>
                      <div className="t13 w-500">{s.t}</div>
                      <div className="muted t11">{s.d}</div>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* Stat strip */}
      <div className="stat-strip" style={{ maxWidth: 1200, margin: '0 auto' }}>
        {[
          ['4,200+', 'Stocks tracked'],
          ['2,800', 'Mutual funds'],
          ['240K', 'Active investors'],
          ['80+', 'Data points / stock'],
        ].map(([v, l]) => (
          <div key={l}>
            <div className="mono" style={{ fontSize: 32, fontWeight: 500, letterSpacing: '-0.025em' }}>{v}</div>
            <div className="muted t12 upper" style={{ marginTop: 4, letterSpacing: '0.08em' }}>{l}</div>
          </div>
        ))}
      </div>

      {/* Features */}
      <section className="section">
        <div className="section-eyebrow">// One platform · Every signal</div>
        <h2>Everything you need to research, <span className="it">nothing</span> you don’t.</h2>
        <div className="section-sub">
          Stop bouncing between five tabs. DhanRadar pulls the data, scores the stock, explains the metric, and shows you the trade-off — in one place.
        </div>
        <div className="feature-grid">
          {features.map(f => (
            <div key={f.t} className="feature">
              <div className="feature-ico"><Icon name={f.ico} size={18}/></div>
              <h3>{f.t}</h3>
              <p>{f.d}</p>
            </div>
          ))}
        </div>
      </section>

      {/* Pricing */}
      <section className="section">
        <div className="section-eyebrow">// Plans</div>
        <h2>Start free. <span className="it">Upgrade</span> when you outgrow it.</h2>
        <div className="section-sub">No card needed to try Pro for 14 days. Cancel anytime.</div>
        <div className="pricing-grid">
          <div className="plan">
            <div className="plan-name">Free</div>
            <div className="plan-price">₹0<span className="per"> /forever</span></div>
            <div className="plan-desc">For curious beginners testing the waters.</div>
            <ul>
              <li><Icon name="check" size={14}/>20 stock lookups / month</li>
              <li><Icon name="check" size={14}/>Basic DhanRadar Score</li>
              <li><Icon name="check" size={14}/>1 watchlist · 10 stocks</li>
              <li><Icon name="check" size={14}/>Education hub access</li>
            </ul>
            <button className="btn btn-ghost" onClick={onEnterApp}>Start free</button>
          </div>
          <div className="plan featured">
            <div className="row between center">
              <div className="plan-name" style={{ color: 'var(--text)' }}>Pro</div>
              <span className="badge badge-info">Most popular</span>
            </div>
            <div className="plan-price">₹399<span className="per"> /month</span></div>
            <div className="plan-desc">For serious retail investors and SIP-and-add types.</div>
            <ul>
              <li><Icon name="check" size={14}/>Unlimited stocks & funds</li>
              <li><Icon name="check" size={14}/>Fair Value estimate (DCF + relative)</li>
              <li><Icon name="check" size={14}/>50+ screener filters · save & share</li>
              <li><Icon name="check" size={14}/>10 watchlists · price & score alerts</li>
              <li><Icon name="check" size={14}/>Portfolio analytics & risk reports</li>
            </ul>
            <button className="btn btn-primary" onClick={onEnterApp}>Start 14-day trial</button>
          </div>
          <div className="plan">
            <div className="plan-name">Premium</div>
            <div className="plan-price">₹899<span className="per"> /month</span></div>
            <div className="plan-desc">For high-conviction investors who want every edge.</div>
            <ul>
              <li><Icon name="check" size={14}/>Everything in Pro</li>
              <li><Icon name="check" size={14}/>Analyst-curated portfolios</li>
              <li><Icon name="check" size={14}/>Tax & capital gains optimisation</li>
              <li><Icon name="check" size={14}/>API access & CSV export</li>
              <li><Icon name="check" size={14}/>Priority human support</li>
            </ul>
            <button className="btn btn-outline" onClick={onEnterApp}>Talk to us</button>
          </div>
        </div>
      </section>

      {/* FAQ */}
      <section className="section" style={{ maxWidth: 920 }}>
        <div className="section-eyebrow">// Frequently asked</div>
        <h2>Questions, <span className="it">answered.</span></h2>
        <div className="faq">
          {faqs.map((f, i) => (
            <div key={i} className="faq-item" onClick={() => setOpenFaq(openFaq === i ? -1 : i)}>
              <div className="faq-q">
                <span>{f.q}</span>
                <Icon name={openFaq === i ? 'chevDown' : 'chevRight'} size={16}/>
              </div>
              {openFaq === i && <div className="faq-a">{f.a}</div>}
            </div>
          ))}
        </div>
      </section>

      {/* Footer */}
      <footer className="footer">
        <div>
          <div className="row gap-3 center" style={{ marginBottom: 12 }}>
            <Logo size={28}/>
            <span style={{ fontWeight: 600, fontSize: 16 }}>DhanRadar</span>
          </div>
          <div className="footer-meta">Investment intelligence for India. DhanRadar is a research analytics platform — not an investment advisor. Markets carry risk.</div>
          <div className="muted t11" style={{ marginTop: 18 }}>© 2026 DhanRadar Tech Pvt. Ltd.</div>
        </div>
        <div><h4>Product</h4><ul><li><a>Stocks</a></li><li><a>Mutual funds</a></li><li><a>Screener</a></li><li><a>Compare</a></li><li><a>Watchlists</a></li></ul></div>
        <div><h4>Learn</h4><ul><li><a>Education hub</a></li><li><a>Glossary</a></li><li><a>Blog</a></li><li><a>Podcast</a></li></ul></div>
        <div><h4>Company</h4><ul><li><a>About</a></li><li><a>Careers</a></li><li><a>Press</a></li><li><a>Contact</a></li></ul></div>
        <div><h4>Legal</h4><ul><li><a>Terms</a></li><li><a>Privacy</a></li><li><a>Disclosures</a></li><li><a>SEBI guidelines</a></li></ul></div>
      </footer>
    </div>
  );
}

// ────────────────────────────────────────────────────────────────────
// Logo
// ────────────────────────────────────────────────────────────────────
function Logo({ size = 28 }) {
  return (
    <div style={{
      width: size, height: size, borderRadius: size * 0.27,
      background: 'linear-gradient(135deg, #0B1F3A 0%, #1E5EFF 100%)',
      display: 'grid', placeItems: 'center', position: 'relative', overflow: 'hidden',
      boxShadow: '0 1px 2px rgba(0,0,0,0.1)',
    }}>
      <svg width={size * 0.6} height={size * 0.6} viewBox="0 0 24 24" fill="none" stroke="white" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
        <circle cx="12" cy="12" r="9" opacity="0.4"/>
        <circle cx="12" cy="12" r="5" opacity="0.7"/>
        <path d="M12 12 L19 8"/>
        <circle cx="17.5" cy="9" r="1.2" fill="#1FD79A" stroke="none"/>
      </svg>
    </div>
  );
}

Object.assign(window, { LandingScreen, Logo });
