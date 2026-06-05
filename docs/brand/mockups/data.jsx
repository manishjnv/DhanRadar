// DhanRadar — sample data + icons
// Indian stocks, mutual funds, holdings.

const DR_DATA = {
  indices: [
    { name: 'NIFTY 50', value: 24812.45, delta: 142.6, pct: 0.58 },
    { name: 'SENSEX', value: 81468.12, delta: 412.8, pct: 0.51 },
    { name: 'BANK NIFTY', value: 52186.20, delta: -84.3, pct: -0.16 },
    { name: 'USD/INR', value: 84.21, delta: 0.04, pct: 0.05 },
  ],

  stocks: [
    { sym: 'RELIANCE', name: 'Reliance Industries', sector: 'Energy', mcap: 1842000, price: 2841.30, chg: 1.84, pe: 24.2, roe: 9.4, score: 86, signal: 'Strong Buy', color: '#0A1F4A', logo: 'R' },
    { sym: 'TCS', name: 'Tata Consultancy Svcs', sector: 'IT Services', mcap: 1485000, price: 4102.10, chg: 0.62, pe: 30.1, roe: 50.2, score: 91, signal: 'Strong Buy', color: '#1F4E9E', logo: 'T' },
    { sym: 'HDFCBANK', name: 'HDFC Bank', sector: 'Banking', mcap: 1268000, price: 1672.55, chg: -0.42, pe: 18.9, roe: 17.1, score: 84, signal: 'Buy', color: '#003E80', logo: 'H' },
    { sym: 'INFY', name: 'Infosys', sector: 'IT Services', mcap: 760000, price: 1842.80, chg: 1.21, pe: 28.5, roe: 31.8, score: 82, signal: 'Buy', color: '#0E3F7C', logo: 'I' },
    { sym: 'BHARTIARTL', name: 'Bharti Airtel', sector: 'Telecom', mcap: 905000, price: 1612.40, chg: 2.04, pe: 65.2, roe: 12.6, score: 78, signal: 'Buy', color: '#E53935', logo: 'B' },
    { sym: 'ICICIBANK', name: 'ICICI Bank', sector: 'Banking', mcap: 838000, price: 1192.10, chg: 0.71, pe: 19.4, roe: 17.9, score: 87, signal: 'Strong Buy', color: '#B62034', logo: 'I' },
    { sym: 'SBIN', name: 'State Bank of India', sector: 'Banking', mcap: 712000, price: 798.40, chg: -0.18, pe: 11.2, roe: 17.3, score: 79, signal: 'Buy', color: '#2A4D9C', logo: 'S' },
    { sym: 'ITC', name: 'ITC Limited', sector: 'FMCG', mcap: 552000, price: 442.05, chg: 0.34, pe: 27.6, roe: 28.5, score: 76, signal: 'Hold', color: '#1B5E20', logo: 'I' },
    { sym: 'LT', name: 'Larsen & Toubro', sector: 'Construction', mcap: 498000, price: 3618.90, chg: 1.42, pe: 35.4, roe: 14.8, score: 81, signal: 'Buy', color: '#1A237E', logo: 'L' },
    { sym: 'HINDUNILVR', name: 'Hindustan Unilever', sector: 'FMCG', mcap: 581000, price: 2476.60, chg: -0.84, pe: 56.8, roe: 18.4, score: 72, signal: 'Hold', color: '#0D47A1', logo: 'H' },
    { sym: 'MARUTI', name: 'Maruti Suzuki', sector: 'Auto', mcap: 386000, price: 12284.50, chg: 1.62, pe: 28.9, roe: 17.2, score: 80, signal: 'Buy', color: '#0277BD', logo: 'M' },
    { sym: 'TITAN', name: 'Titan Company', sector: 'Consumer', mcap: 296000, price: 3344.20, chg: -1.12, pe: 88.4, roe: 32.6, score: 70, signal: 'Hold', color: '#6A1B9A', logo: 'T' },
  ],

  // Focal stock for analysis page
  focus: {
    sym: 'RELIANCE',
    name: 'Reliance Industries Ltd.',
    exchange: 'NSE',
    sector: 'Energy · Conglomerate',
    price: 2841.30,
    chg: 51.40,
    chgPct: 1.84,
    dayLow: 2792.10, dayHigh: 2848.55, yLow: 2221.05, yHigh: 3217.90,
    mcap: '₹19.21 L Cr',
    volume: '8.42 M',
    score: 86,
    fairValue: 3120,
    components: { valuation: 78, growth: 82, quality: 91, momentum: 88, risk: 71 },
    pros: [
      'Healthy ROE of 9.4% with consistent earnings growth',
      'Strong moat in retail and telecom (Jio) verticals',
      'Net debt reduction of ₹38,000 Cr in last 4 quarters',
      'Diversified revenue across O2C, Retail, Digital',
    ],
    cons: [
      'PE ratio of 24.2 is above 5-yr sector median',
      'Capital intensive — high working capital cycle',
      'Petrochem cyclicality remains a margin headwind',
    ],
    financials: [
      { label: 'Revenue', y2022: 7929, y2023: 8918, y2024: 9001, y2025: 9836 },
      { label: 'EBITDA', y2022: 1257, y2023: 1543, y2024: 1632, y2025: 1798 },
      { label: 'Net Profit', y2022: 671, y2023: 744, y2024: 791, y2025: 824 },
      { label: 'EPS (₹)', y2022: 98.5, y2023: 109.8, y2024: 116.2, y2025: 121.7 },
    ],
    peers: [
      { sym: 'RELIANCE', score: 86, pe: 24.2, pb: 2.4, roe: 9.4, mcap: '19.21L' },
      { sym: 'ONGC',     score: 71, pe: 8.2,  pb: 1.0, roe: 12.8, mcap: '3.42L'  },
      { sym: 'IOC',      score: 64, pe: 12.4, pb: 1.1, roe: 8.6,  mcap: '1.86L'  },
      { sym: 'BPCL',     score: 68, pe: 9.6,  pb: 1.5, roe: 16.2, mcap: '1.42L'  },
    ],
    swot: {
      strengths: ['Vertical integration', 'Pricing power in Jio', 'Strong cash flow', 'Family-promoter governance'],
      weaknesses: ['Capex-heavy', 'Margin volatility', 'Slow EV transition'],
      opportunities: ['Green energy giga-complex', 'Retail expansion in Tier 2/3', 'AI/Cloud through Jio'],
      threats: ['Crude price swings', 'Regulatory caps in telecom', 'Renewable competition'],
    }
  },

  holdings: [
    { sym: 'RELIANCE', name: 'Reliance Industries', qty: 38, avg: 2412.0, ltp: 2841.30, value: 107969.40, pnl: 16321.40, pnlPct: 17.79, weight: 22.4, score: 86 },
    { sym: 'TCS', name: 'TCS', qty: 22, avg: 3680.0, ltp: 4102.10, value: 90246.20, pnl: 9286.20, pnlPct: 11.47, weight: 18.7, score: 91 },
    { sym: 'HDFCBANK', name: 'HDFC Bank', qty: 48, avg: 1542.0, ltp: 1672.55, value: 80282.40, pnl: 6266.40, pnlPct: 8.46, weight: 16.6, score: 84 },
    { sym: 'INFY', name: 'Infosys', qty: 32, avg: 1462.0, ltp: 1842.80, value: 58969.60, pnl: 12185.60, pnlPct: 26.05, weight: 12.2, score: 82 },
    { sym: 'BHARTIARTL', name: 'Bharti Airtel', qty: 24, avg: 1186.0, ltp: 1612.40, value: 38697.60, pnl: 10233.60, pnlPct: 35.95, weight: 8.0, score: 78 },
    { sym: 'ICICIBANK', name: 'ICICI Bank', qty: 28, avg: 982.0, ltp: 1192.10, value: 33378.80, pnl: 5882.80, pnlPct: 21.39, weight: 6.9, score: 87 },
    { sym: 'ITC', name: 'ITC Limited', qty: 60, avg: 412.0, ltp: 442.05, value: 26523.00, pnl: 1803.00, pnlPct: 7.29, weight: 5.5, score: 76 },
    { sym: 'TITAN', name: 'Titan Company', qty: 14, avg: 3120.0, ltp: 3344.20, value: 46818.80, pnl: 3138.80, pnlPct: 7.19, weight: 9.7, score: 70 },
  ],

  sectorAllocation: [
    { name: 'Banking', pct: 31.5, color: '#1E5EFF' },
    { name: 'IT Services', pct: 30.9, color: '#00C2FF' },
    { name: 'Energy', pct: 22.4, color: '#00B386' },
    { name: 'Consumer', pct: 9.7, color: '#F5A623' },
    { name: 'Telecom', pct: 8.0, color: '#A855F7' },
    { name: 'FMCG', pct: 5.5, color: '#EC4899' },
  ],

  watchlist: [
    { sym: 'TATAMOTORS', name: 'Tata Motors', ltp: 942.40, chg: 2.84, score: 81 },
    { sym: 'ADANIENT', name: 'Adani Enterprises', ltp: 2784.50, chg: -1.42, score: 64 },
    { sym: 'WIPRO', name: 'Wipro', ltp: 562.80, chg: 0.92, score: 73 },
    { sym: 'ASIANPAINT', name: 'Asian Paints', ltp: 2412.30, chg: -0.62, score: 68 },
  ],

  movers: {
    gainers: [
      { sym: 'BHARTIARTL', pct: 4.21 },
      { sym: 'TATAMOTORS', pct: 3.62 },
      { sym: 'M&M', pct: 2.94 },
      { sym: 'LT', pct: 2.51 },
    ],
    losers: [
      { sym: 'TITAN', pct: -2.84 },
      { sym: 'ASIANPAINT', pct: -1.92 },
      { sym: 'HINDUNILVR', pct: -1.46 },
      { sym: 'NESTLEIND', pct: -1.21 },
    ]
  },

  news: [
    { tag: 'Earnings', t: '2h ago', title: 'Reliance Q2 profit beats estimates on Jio ARPU expansion', sym: 'RELIANCE' },
    { tag: 'Macro', t: '3h ago', title: 'RBI holds repo rate at 6.50%; growth forecast trimmed to 6.6%' },
    { tag: 'IPO', t: '5h ago', title: 'NSDL IPO oversubscribed 41x on final day; allotment Friday' },
    { tag: 'Sector', t: '6h ago', title: 'Auto stocks rally on festive season delivery numbers' },
  ],

  // Generates a deterministic price series for sparklines / charts
  series(seed, len = 80, trend = 0.4, vol = 0.022) {
    let s = seed; const out = []; let v = 100;
    const rand = () => { s = (s * 9301 + 49297) % 233280; return s / 233280; };
    for (let i = 0; i < len; i++) {
      const r = rand() - 0.5;
      v = v * (1 + r * vol + trend * 0.0015);
      out.push(v);
    }
    return out;
  },
};

// Icon set — clean line icons
const Icon = ({ name, size = 16, stroke = 1.6 }) => {
  const props = {
    width: size, height: size, viewBox: '0 0 24 24', fill: 'none',
    stroke: 'currentColor', strokeWidth: stroke, strokeLinecap: 'round', strokeLinejoin: 'round'
  };
  const paths = {
    radar: (<g><circle cx="12" cy="12" r="9"/><circle cx="12" cy="12" r="5"/><path d="M12 12 L19 8"/><circle cx="17.5" cy="9" r="0.8" fill="currentColor"/></g>),
    home: (<path d="M3 11 L12 4 L21 11 V20 H14 V14 H10 V20 H3 Z"/>),
    chart: (<g><path d="M3 20 H21"/><path d="M5 16 L9 11 L13 14 L20 6"/></g>),
    portfolio: (<g><rect x="3" y="6" width="18" height="14" rx="2"/><path d="M8 6 V4 H16 V6"/><path d="M3 12 H21"/></g>),
    search: (<g><circle cx="11" cy="11" r="7"/><path d="M16 16 L21 21"/></g>),
    filter: (<path d="M3 5 H21 L14 13 V20 L10 18 V13 L3 5 Z"/>),
    compare: (<g><path d="M4 4 V20"/><path d="M20 4 V20"/><path d="M4 12 H20"/><path d="M9 8 L4 12 L9 16"/><path d="M15 8 L20 12 L15 16"/></g>),
    book: (<path d="M4 4 H10 C11 4 12 5 12 6 V20 C12 19 11 18 10 18 H4 Z M20 4 H14 C13 4 12 5 12 6 V20 C12 19 13 18 14 18 H20 Z"/>),
    bell: (<g><path d="M6 16 V11 a6 6 0 1 1 12 0 V16 L20 18 H4 Z"/><path d="M10 21 H14"/></g>),
    settings: (<g><circle cx="12" cy="12" r="3"/><path d="M12 2 V5 M12 19 V22 M2 12 H5 M19 12 H22 M5 5 L7 7 M17 17 L19 19 M5 19 L7 17 M17 7 L19 5"/></g>),
    list: (<g><path d="M3 6 H21"/><path d="M3 12 H21"/><path d="M3 18 H21"/></g>),
    grid: (<g><rect x="3" y="3" width="7" height="7"/><rect x="14" y="3" width="7" height="7"/><rect x="3" y="14" width="7" height="7"/><rect x="14" y="14" width="7" height="7"/></g>),
    spark: (<path d="M3 18 L8 10 L13 14 L21 4"/>),
    arrowUp: (<g><path d="M12 19 V5"/><path d="M5 12 L12 5 L19 12"/></g>),
    arrowDown: (<g><path d="M12 5 V19"/><path d="M5 12 L12 19 L19 12"/></g>),
    arrowRight: (<g><path d="M5 12 H19"/><path d="M12 5 L19 12 L12 19"/></g>),
    plus: (<g><path d="M12 5 V19"/><path d="M5 12 H19"/></g>),
    star: (<path d="M12 3 L14.5 9 L21 9.5 L16 14 L17.5 21 L12 17.5 L6.5 21 L8 14 L3 9.5 L9.5 9 Z"/>),
    check: (<path d="M4 12 L10 18 L20 6"/>),
    chevDown: (<path d="M6 9 L12 15 L18 9"/>),
    chevRight: (<path d="M9 6 L15 12 L9 18"/>),
    sun: (<g><circle cx="12" cy="12" r="4"/><path d="M12 2 V5 M12 19 V22 M2 12 H5 M19 12 H22 M4.5 4.5 L6.5 6.5 M17.5 17.5 L19.5 19.5 M4.5 19.5 L6.5 17.5 M17.5 6.5 L19.5 4.5"/></g>),
    moon: (<path d="M20 14 A8 8 0 0 1 10 4 A8 8 0 1 0 20 14 Z"/>),
    close: (<g><path d="M6 6 L18 18"/><path d="M6 18 L18 6"/></g>),
    info: (<g><circle cx="12" cy="12" r="9"/><path d="M12 8 V8.1"/><path d="M12 11 V17"/></g>),
    fund: (<g><circle cx="12" cy="12" r="9"/><path d="M12 3 A9 9 0 0 1 21 12 L12 12 Z" fill="currentColor" opacity="0.18" stroke="none"/><path d="M12 12 L18 7"/></g>),
    rupee: (<g><path d="M7 5 H17"/><path d="M7 9 H17"/><path d="M7 5 C11 5 13 6.5 13 9 C13 11.5 11 13 7 13 H10 L17 20"/></g>),
    bolt: (<path d="M13 3 L4 14 H11 L9 21 L20 9 H13 Z"/>),
    shield: (<path d="M12 3 L20 6 V12 C20 17 16 20 12 21 C8 20 4 17 4 12 V6 Z"/>),
    pie: (<g><path d="M12 3 V12 L20 17 A9 9 0 1 1 12 3 Z"/></g>),
    eye: (<g><path d="M2 12 C4 7 8 4 12 4 C16 4 20 7 22 12 C20 17 16 20 12 20 C8 20 4 17 2 12 Z"/><circle cx="12" cy="12" r="3"/></g>),
    sparkles: (<g><path d="M12 3 L13.5 9 L19 10.5 L13.5 12 L12 18 L10.5 12 L5 10.5 L10.5 9 Z"/><path d="M19 4 L19.6 6 L21 6.5 L19.6 7 L19 9 L18.4 7 L17 6.5 L18.4 6 Z"/></g>),
  };
  return <svg {...props}>{paths[name] || null}</svg>;
};

Object.assign(window, { DR_DATA, Icon });
