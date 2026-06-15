"""
DhanRadar — Concept-Explainer seed content (C1).

The authored source of truth for the `concepts.concept_explainers` table.
Lives under `backend/dhanradar/` so the `ci_guards` advisory-verb scan covers it.
Loaded by the idempotent `dhanradar.concepts.seed` command.

EDUCATION ONLY — every explainer describes an investing concept; none recommends
an action. The copy is evergreen (no FY dependency); every numeric example is a
clearly labelled hypothetical illustration with assumed figures (authored June
2026), never a projection, a promise, or an assessment of any actual fund or
person. SEBI boundary: describe what a concept IS — never what a reader should do.
"""

from __future__ import annotations

# Concepts-specific not-advice disclosure (non-neg #9). NOT_ADVICE +
# DISCLAIMER_VERSION are imported read-only from the shared compliance constants
# in service.py — this string is the concepts surface's own contextual disclosure.
CONCEPTS_DISCLOSURE = (
    "General investing education — not investment advice. These explainers describe "
    "concepts in plain language; they do not assess any fund, security, or person's "
    "situation. Investing involves risk, including possible loss of principal. For "
    "guidance on personal decisions, consult a SEBI-registered investment adviser."
)

# Human-readable not-advice line shown on every concepts surface. The module
# supplies its OWN text rather than the platform `NOT_ADVICE` marker token
# (which is a literal flag, not display copy) so the public pages render a real
# sentence, never the bare word "NOT_ADVICE".
CONCEPTS_NOT_ADVICE = "Not investment advice."

# Standing line appended to every numeric illustration in the bodies below.
_ILLUS = (
    "This is a hypothetical illustration with assumed figures (authored June 2026), "
    "not a projection of any actual investment. Real returns vary and may be negative."
)


# Each dict maps 1:1 to concepts.ConceptExplainer columns (minus updated_at).
CONCEPTS: list[dict] = [
    {
        "slug": "risk",
        "title": "What “risk” actually means in investing",
        "summary": (
            "Risk is the chance that an investment's outcome differs from what was "
            "expected — including the possibility of loss."
        ),
        "category": "Risk & return",
        "sort_order": 10,
        "body_md": (
            "## Risk is uncertainty, not just danger\n\n"
            "In everyday language, “risk” means danger. In investing, it has a more "
            "precise meaning: **the range of possible outcomes** an investment can have. "
            "An investment is riskier when its outcomes are more uncertain — when the "
            "eventual value could land far above *or* far below what was expected, "
            "including below the amount originally invested.\n\n"
            "## The main kinds of risk\n\n"
            "- **Market risk** — the value of investments moves with the broader market. "
            "When equity markets fall, most equity funds fall with them.\n"
            "- **Credit risk** — a bond issuer may fail to pay interest or principal on "
            "time. This mainly affects debt instruments and debt funds.\n"
            "- **Inflation risk** — money that grows slower than prices loses purchasing "
            "power even without a visible loss.\n"
            "- **Liquidity risk** — an asset may be hard to convert to cash quickly "
            "without a price concession.\n"
            "- **Concentration risk** — when a large share of a portfolio depends on one "
            "company, sector, or theme, a single setback affects much of the whole.\n\n"
            "## Risk and potential return are linked\n\n"
            "Assets with higher *potential* returns generally come with a wider range of "
            "possible outcomes. There is no known way to obtain higher expected returns "
            "without accepting more uncertainty — claims of high return with no risk are "
            "a classic warning sign of fraud.\n\n"
            "## How risk is communicated in India\n\n"
            "SEBI requires every mutual-fund scheme to display a **riskometer** — a "
            "standardised label from “Low” to “Very High” — in its "
            "documents, so the scheme's risk level is stated rather than implied.\n\n"
            "Related concepts: [volatility](/learn/concepts/volatility), "
            "[drawdown](/learn/concepts/drawdown), "
            "[diversification](/learn/concepts/diversification)."
        ),
    },
    {
        "slug": "volatility",
        "title": "Volatility: why prices wobble",
        "summary": (
            "Volatility measures how widely an investment's value swings around its "
            "average — in both directions."
        ),
        "category": "Risk & return",
        "sort_order": 20,
        "body_md": (
            "## What volatility measures\n\n"
            "Volatility is a measure of **how much an investment's value moves around** "
            "over time. A fund whose NAV drifts a little each day has low volatility; a "
            "fund whose NAV jumps and dips sharply has high volatility. The most common "
            "yardstick is **standard deviation** — the typical distance of returns from "
            "their own average.\n\n"
            "## Volatility is not the same as loss\n\n"
            "Volatility counts swings in *both* directions — sharp rises raise it just "
            "as sharp falls do. A volatile investment is not necessarily a losing one; "
            "it is one whose short-term value is harder to predict. The cost of "
            "volatility is **uncertainty over short horizons**: the shorter the period, "
            "the wider the range of outcomes an investor may experience.\n\n"
            "## An illustration\n\n"
            "Consider two hypothetical funds that both averaged 8% per year over a "
            "decade. Fund A's yearly results stayed between +4% and +12%; Fund B's "
            "ranged from −20% to +35%. The destination was similar, but the journey "
            "was very different — and an investor who needed the money in a down year "
            "would have faced very different exit values. " + _ILLUS + "\n\n"
            "## Why it matters\n\n"
            "Knowing a fund's volatility helps set expectations about the ride: how "
            "large the interim ups and downs have historically been, and how different "
            "a short holding period's outcome can be from the long-run average. "
            "Historical volatility describes the past; it does not predict future "
            "behaviour.\n\n"
            "Related concepts: [risk](/learn/concepts/risk), "
            "[drawdown](/learn/concepts/drawdown)."
        ),
    },
    {
        "slug": "drawdown",
        "title": "Drawdown: measuring the fall from a peak",
        "summary": (
            "Drawdown is the decline from an investment's highest point to a later low "
            "— a direct measure of historical downside."
        ),
        "category": "Risk & return",
        "sort_order": 30,
        "body_md": (
            "## What a drawdown is\n\n"
            "A **drawdown** is the fall in value from a peak to a subsequent trough, "
            "expressed as a percentage of the peak. If a fund's NAV reaches ₹100 and "
            "later falls to ₹80 before recovering, that episode was a **20% "
            "drawdown**. The largest such fall over a period is called the **maximum "
            "drawdown**. " + _ILLUS + "\n\n"
            "## The asymmetry of recovery\n\n"
            "Falls and recoveries are not symmetric. After a 20% fall (₹100 → "
            "₹80), getting back to ₹100 requires a **25%** rise. After a 50% "
            "fall, the recovery required is **100%**. This arithmetic is why large "
            "drawdowns weigh so heavily on long-term results — the deeper the fall, the "
            "disproportionately larger the climb back.\n\n"
            "## Drawdown vs volatility\n\n"
            "[Volatility](/learn/concepts/volatility) summarises the size of *all* "
            "swings, up and down. Drawdown isolates the part investors actually "
            "experience as loss: how far below a previous high the investment has been, "
            "and for how long. Two funds with similar volatility can have very "
            "different drawdown histories.\n\n"
            "## Why it matters\n\n"
            "Maximum drawdown describes the worst historical episode an investment has "
            "put its holders through — a concrete answer to “how bad has it been?”. "
            "Like all historical measures, it describes the past, not a limit on what "
            "the future can do.\n\n"
            "Related concepts: [risk](/learn/concepts/risk), "
            "[volatility](/learn/concepts/volatility)."
        ),
    },
    {
        "slug": "diversification",
        "title": "Diversification: not all eggs in one basket",
        "summary": (
            "Diversification spreads investments across assets that do not all move "
            "together, so one setback affects less of the whole."
        ),
        "category": "Portfolio basics",
        "sort_order": 40,
        "body_md": (
            "## The idea\n\n"
            "**Diversification** is the practice of spreading investments across many "
            "holdings — different companies, sectors, asset classes, or geographies — "
            "so that no single setback determines the fate of the whole portfolio. It "
            "is the practical response to an uncomfortable fact: nobody reliably knows "
            "in advance which individual investment will disappoint.\n\n"
            "## Why it works\n\n"
            "Diversification works because different assets **do not move in perfect "
            "lockstep**. When one part of a portfolio is falling, another may be flat "
            "or rising. The less correlated the parts, the smoother the combined "
            "whole tends to be — the portfolio's swings become smaller than the average "
            "of its components' swings.\n\n"
            "## What it can and cannot do\n\n"
            "- It **reduces concentration risk** — the damage one company, sector, or "
            "theme can do.\n"
            "- It **cannot remove market risk** — in a broad market fall, most equity "
            "holdings fall together, diversified or not.\n"
            "- Past a point it **dilutes rather than protects** — a portfolio of many "
            "near-identical funds repeats the same underlying holdings and adds "
            "complexity without adding meaningful diversification (an effect known as "
            "**portfolio overlap**).\n\n"
            "## How it appears in practice\n\n"
            "A mutual fund is itself a diversified vehicle — one unit represents dozens "
            "of underlying securities. At the portfolio level, diversification shows up "
            "as the mix across funds, asset classes, and styles, which is the subject "
            "of [asset allocation](/learn/concepts/asset-allocation).\n\n"
            "Related concepts: [risk](/learn/concepts/risk), "
            "[asset allocation](/learn/concepts/asset-allocation)."
        ),
    },
    {
        "slug": "asset-allocation",
        "title": "Asset allocation: how a portfolio is divided",
        "summary": (
            "Asset allocation is the split of a portfolio across asset classes — the "
            "mix that largely sets its risk-and-return character."
        ),
        "category": "Portfolio basics",
        "sort_order": 50,
        "body_md": (
            "## What asset allocation is\n\n"
            "**Asset allocation** is the way a portfolio is divided among asset classes "
            "— typically equity (shares), debt (bonds and money-market instruments), "
            "gold, and cash. Two portfolios with the same funds but different "
            "proportions are different portfolios: the **mix** is a major driver of how "
            "the whole behaves.\n\n"
            "## Why the mix matters so much\n\n"
            "Each asset class has its own character. Equity has historically offered "
            "higher long-run growth with larger interim swings; high-quality debt has "
            "offered steadier but lower returns; gold has often moved differently from "
            "both; cash is stable but loses purchasing power to inflation over time. "
            "The proportions among them set the portfolio's overall range of likely "
            "outcomes — often more than the choice of individual funds within each "
            "class.\n\n"
            "## An illustration of different characters\n\n"
            "A hypothetical 80/20 equity-debt mix and a 20/80 mix can be built from "
            "identical funds, yet behave very differently: in a year when equities "
            "fell 20% and debt returned 7%, the first mix would have fallen roughly "
            "14.6% while the second rose about 1.6%. Neither mix is “better” — "
            "they are different trade-offs between growth potential and stability. "
            + _ILLUS + "\n\n"
            "## A personal question — and out of scope here\n\n"
            "Which mix suits a particular person depends on their goals, horizon, "
            "income, and circumstances. That assessment is individual advice, which "
            "only a SEBI-registered investment adviser may provide; this page only "
            "explains what the concept is.\n\n"
            "Related concepts: [diversification](/learn/concepts/diversification), "
            "[risk](/learn/concepts/risk), [compounding](/learn/concepts/compounding)."
        ),
    },
    {
        "slug": "expense-ratio-ter",
        "title": "Expense ratio (TER): the cost of owning a fund",
        "summary": (
            "The total expense ratio is the annual percentage of a fund's assets "
            "deducted to run it — a cost that compounds over time."
        ),
        "category": "Costs",
        "sort_order": 60,
        "body_md": (
            "## What the TER is\n\n"
            "The **total expense ratio (TER)** is the annual cost of running a mutual "
            "fund, expressed as a percentage of its assets. It covers fund management, "
            "administration, audit, and (in some plans) distribution. The TER is not "
            "billed separately — it is **deducted from the fund's NAV a little every "
            "day**, so published NAVs and returns are already net of it.\n\n"
            "## Regulated, disclosed, and capped\n\n"
            "In India, SEBI caps how much TER a scheme may charge, with limits that "
            "vary by scheme type and size (larger funds face tighter caps; as of June "
            "2026). Every scheme discloses its current TER, so the cost of owning it "
            "is public information rather than a hidden fee.\n\n"
            "## Regular and direct plans\n\n"
            "Every open-ended scheme is offered in two plans that share the same "
            "portfolio and fund manager. The **regular plan** includes distributor "
            "commission inside its TER; the **direct plan** has no distributor "
            "commission and therefore a lower TER. The difference between the two is "
            "purely the cost layer — the underlying investments are identical.\n\n"
            "## Small percentages, large effects\n\n"
            "Because the TER is charged every year on the whole balance, small "
            "differences compound. As a hypothetical illustration: ₹1,00,000 "
            "growing at an assumed 8% a year before costs becomes about ₹2.06 lakh "
            "in 10 years at a 0.5% TER, but about ₹1.79 lakh at a 2% TER — a gap "
            "of roughly ₹27,000 created by costs alone. " + _ILLUS + "\n\n"
            "Related concepts: [compounding](/learn/concepts/compounding)."
        ),
    },
    {
        "slug": "sip-rupee-cost-averaging",
        "title": "SIP & rupee-cost averaging: investing in instalments",
        "summary": (
            "A SIP invests a fixed amount at regular intervals; rupee-cost averaging "
            "is the arithmetic of what that does to average cost."
        ),
        "category": "Investing habits",
        "sort_order": 70,
        "body_md": (
            "## What a SIP is\n\n"
            "A **systematic investment plan (SIP)** is a facility for investing a "
            "fixed amount into a mutual-fund scheme at a regular interval — usually "
            "monthly. It is a *method* of investing, not a separate product: the money "
            "goes into the same scheme it would in a lump sum, just spread over time.\n\n"
            "## The arithmetic: rupee-cost averaging\n\n"
            "Because the instalment is a fixed rupee amount, it automatically "
            "**purchases more units when the NAV is lower and fewer when it is "
            "higher**. As a hypothetical illustration: ₹1,000 invested monthly at "
            "NAVs of ₹50, ₹40, and ₹50 acquires 20 + 25 + 20 = 65 units — "
            "an average cost of about ₹46.15 per unit, slightly below the simple "
            "average NAV of ₹46.67 over those months. " + _ILLUS + "\n\n"
            "## What it does — and does not — do\n\n"
            "- It removes the need to decide *when* to invest each instalment, which "
            "spreads purchases across market conditions.\n"
            "- It aligns investing with how most people earn — in monthly income.\n"
            "- It does **not** assure a profit, and it does **not** protect against "
            "loss in a declining market — if the market falls and stays down, a SIP "
            "portfolio falls too. This caveat appears in mutual-fund documents "
            "because it is true.\n\n"
            "## A habit, not a verdict\n\n"
            "Whether instalments or a lump sum produced the better historical result "
            "depends entirely on the period — neither method wins universally. The SIP "
            "is best understood as a **discipline mechanism** whose value is "
            "behavioural as much as arithmetic.\n\n"
            "Related concepts: [compounding](/learn/concepts/compounding), "
            "[volatility](/learn/concepts/volatility)."
        ),
    },
    {
        "slug": "compounding",
        "title": "Compounding: growth on growth",
        "summary": (
            "Compounding is earning returns on past returns — an effect whose power "
            "comes from time, and which works on costs too."
        ),
        "category": "Investing habits",
        "sort_order": 80,
        "body_md": (
            "## The idea\n\n"
            "**Compounding** is what happens when returns themselves start earning "
            "returns. In year one, growth applies to the original amount; in year two, "
            "to the original amount *plus* year one's growth; and so on. The result is "
            "a snowball: growth that accelerates with time rather than accumulating in "
            "a straight line.\n\n"
            "## An illustration\n\n"
            "At an assumed constant 8% a year, ₹1,00,000 grows to about "
            "₹2.16 lakh in 10 years. Without compounding — if each year's 8% were "
            "earned only on the original amount — the total would be ₹1.80 lakh. "
            "The extra ≈₹36,000 is growth earned on growth. Real investments "
            "do not grow at a constant rate; values fluctuate and can fall. "
            + _ILLUS + "\n\n"
            "## Time is the active ingredient\n\n"
            "The compounding curve is gentle early and steep late: in the illustration "
            "above, more growth arrives in the final three years than in the first "
            "five. This is why the *length* of time invested has such weight in "
            "long-run outcomes — an effect that exists in the arithmetic itself, "
            "independent of any particular investment.\n\n"
            "## It works on costs too\n\n"
            "Compounding is indifferent to direction: annual costs and inflation "
            "compound exactly the way returns do, quietly scaling with the balance "
            "every year. The [expense ratio](/learn/concepts/expense-ratio-ter) "
            "explainer shows the same arithmetic applied to fees.\n\n"
            "Related concepts: [SIP & rupee-cost averaging]"
            "(/learn/concepts/sip-rupee-cost-averaging), "
            "[expense ratio (TER)](/learn/concepts/expense-ratio-ter)."
        ),
    },
    {
        "slug": "india-vix-explained",
        "title": "What India VIX tells you",
        "summary": (
            "India VIX is the NSE's measure of how much uncertainty options markets "
            "are pricing into the next 30 days — a real-time gauge of collective fear."
        ),
        "category": "Market signals",
        "sort_order": 90,
        "body_md": (
            "## What VIX stands for\n\n"
            "**India VIX** (Volatility Index) is a real-time index published by NSE. "
            "It is derived from Nifty 50 options prices and represents the annualised "
            "volatility that options traders are collectively pricing into the *next 30 "
            "calendar days*. A VIX of 20 means the market is pricing in roughly "
            "±20% annualised movement — or about ±5.8% over 30 days. " + _ILLUS + "\n\n"
            "## Fear gauge — but of expected future moves\n\n"
            "VIX rises when options buyers pay more for protection, which typically "
            "happens when market participants are uncertain or fearful. "
            "Historically, VIX spikes have coincided with sharp market falls — but VIX "
            "measures *expected* future volatility, not actual past volatility and not "
            "a prediction of direction.\n\n"
            "## What the levels typically imply\n\n"
            "- **Below 15** — relatively calm market; options are cheap; "
            "uncertainty is low.\n"
            "- **15–20** — normal market conditions; moderate uncertainty.\n"
            "- **20–30** — elevated anxiety; often seen around significant events or "
            "moderate market stress.\n"
            "- **Above 30** — high fear; seen during major corrections or crises.\n\n"
            "These are rough historical anchors, not thresholds with guaranteed outcomes.\n\n"
            "## What VIX is NOT\n\n"
            "VIX does not predict which direction markets will move. It also does not "
            "measure how much markets have already fallen — that is measured by the "
            "index level itself. High VIX means high uncertainty in both directions.\n\n"
            "Related concepts: [volatility](/learn/concepts/volatility), "
            "[market breadth](/learn/concepts/market-breadth-basics)."
        ),
    },
    {
        "slug": "dip-buying-discipline",
        "title": "Staged deployment: why not all-in during a dip",
        "summary": (
            "Deploying capital in stages during a market correction manages the risk "
            "of catching a falling knife — spreading purchases across a range of prices."
        ),
        "category": "Investing habits",
        "sort_order": 95,
        "body_md": (
            "## The appeal — and the trap — of buying the dip\n\n"
            "When markets fall, prices look cheaper than they did before. Deploying "
            "capital at lower prices *can* improve long-run returns — but markets can "
            "fall further still. The trap is going all-in at the first sign of a "
            "correction, only to watch prices fall another 20%.\n\n"
            "## Staged deployment: the idea\n\n"
            "**Staged deployment** (or a deployment ladder) spreads the capital across "
            "several tranches triggered at different levels of market stress. For "
            "example: deploy 20% of reserved capital if the market drops 5%, another "
            "20% if it drops 10%, and so on — reserving the final tranches for the "
            "deepest corrections. This is a hypothetical illustration, not a "
            "recommended strategy. " + _ILLUS + "\n\n"
            "## Why this works behaviourally\n\n"
            "- It removes the pressure of a single all-or-nothing decision.\n"
            "- It ensures some capital is always available if conditions worsen.\n"
            "- It converts panic into a pre-planned checklist executed on autopilot.\n\n"
            "## What it does not guarantee\n\n"
            "Staged deployment does not ensure a profit. Markets may not recover, or "
            "may recover before all tranches are deployed. Like all systematic "
            "approaches, its value is in the discipline it enforces, not a guaranteed "
            "outcome.\n\n"
            "Related concepts: [SIP & rupee-cost averaging]"
            "(/learn/concepts/sip-rupee-cost-averaging), "
            "[volatility](/learn/concepts/volatility)."
        ),
    },
    {
        "slug": "nifty-correction-history",
        "title": "Nifty corrections: what history shows",
        "summary": (
            "Indian equity markets have seen repeated corrections throughout their "
            "history — each felt permanent in the moment, each followed by recovery."
        ),
        "category": "Market signals",
        "sort_order": 100,
        "body_md": (
            "## Corrections are normal, not exceptional\n\n"
            "A **market correction** is generally defined as a fall of 10% or more "
            "from a recent peak. Bear markets are falls of 20% or more. The Nifty 50 "
            "has experienced both regularly since its inception — roughly every few "
            "years.\n\n"
            "## Historical pattern (educational overview)\n\n"
            "Looking at Nifty 50 history, significant drawdowns have included episodes "
            "during the dot-com bust (2001), the global financial crisis (2008–2009), "
            "the European debt crisis (2011), demonetisation (2016), the IL&FS credit "
            "crisis (2018), COVID-19 (2020), and global rate-hike fears (2022). "
            "In every case, the index recovered to new highs — eventually. The time to "
            "recovery has varied from months to years.\n\n"
            "## What historical patterns can and cannot tell us\n\n"
            "- Past corrections show that downturns *have always* been followed by "
            "recovery in India's equity markets — but this does not guarantee any "
            "future recovery will happen or on any particular timeline.\n"
            "- The severity and duration of corrections vary enormously.\n"
            "- Individual holdings, sectors, and small/mid-cap stocks can and do "
            "suffer longer drawdowns than the broad index.\n\n"
            "## The behavioural lesson\n\n"
            "Knowing that corrections are a recurring feature — not an aberration — can "
            "help investors avoid the common mistake of treating a fall as a signal to "
            "exit permanently. Historical context does not remove risk; it provides "
            "a frame for understanding it.\n\n"
            "Related concepts: [drawdown](/learn/concepts/drawdown), "
            "[volatility](/learn/concepts/volatility)."
        ),
    },
    {
        "slug": "sip-during-corrections",
        "title": "Keep your SIP running in corrections",
        "summary": (
            "Pausing a SIP during a market fall means missing the lower prices that "
            "are the chief arithmetic benefit of investing in instalments."
        ),
        "category": "Investing habits",
        "sort_order": 105,
        "body_md": (
            "## The instinct to pause — and why it backfires\n\n"
            "When markets fall sharply, the natural instinct is to pause or stop a SIP "
            "to 'wait for stability'. But the point of a SIP is precisely to buy during "
            "all conditions — including the uncomfortable ones.\n\n"
            "## What happens arithmetically when you pause\n\n"
            "Rupee-cost averaging works because a fixed instalment buys *more units* "
            "when the NAV is lower. A correction is when NAVs are most depressed — "
            "pausing a SIP at that moment skips the months where each rupee buys the "
            "most units. By the time markets recover and the investor resumes, prices "
            "are higher and fewer units are purchased per instalment. " + _ILLUS + "\n\n"
            "## What a SIP pause costs (hypothetically)\n\n"
            "Two investors both run a ₹10,000 SIP in a hypothetical fund. One pauses "
            "for 3 months during a 20% drawdown; the other continues. The one who "
            "continued bought units at depressed NAVs; the one who paused bought "
            "nothing during those months and resumed at higher prices. The exact "
            "difference depends on when and how fast the market recovers — these are "
            "illustrative assumptions, not a prediction. " + _ILLUS + "\n\n"
            "## Important caveat\n\n"
            "Continuing a SIP during a correction only makes sense if the underlying "
            "scheme still aligns with your goals and if you have the financial capacity "
            "to continue the instalment. Investing beyond one's means or risk tolerance "
            "is not advised by anyone. This page explains the concept, not your "
            "personal situation.\n\n"
            "Related concepts: [SIP & rupee-cost averaging]"
            "(/learn/concepts/sip-rupee-cost-averaging), "
            "[drawdown](/learn/concepts/drawdown)."
        ),
    },
    {
        "slug": "market-breadth-basics",
        "title": "Reading market breadth",
        "summary": (
            "Market breadth measures how many stocks are participating in a move — "
            "a narrow rally or decline tells a different story than a broad one."
        ),
        "category": "Market signals",
        "sort_order": 110,
        "body_md": (
            "## What market breadth is\n\n"
            "**Market breadth** refers to the number of individual stocks participating "
            "in a market's overall move. When the index rises but most stocks are "
            "falling, the rally is said to have *narrow* breadth — a handful of large "
            "stocks are driving the headline number while the rest lag.\n\n"
            "## Advances, declines, and the A/D ratio\n\n"
            "The most common breadth measure is the **advance-decline ratio (A/D "
            "ratio)**: the number of stocks that rose on a given day divided by the "
            "number that fell. An A/D ratio above 1 means more stocks advanced than "
            "declined — broad participation. An A/D ratio below 1 means the majority "
            "of stocks fell even if the index was flat or positive.\n\n"
            "## Why breadth matters\n\n"
            "- A broad rally (high A/D) suggests widespread buying; narrow rallies "
            "(low A/D) may be fragile.\n"
            "- A broad decline (very low A/D) can signal widespread selling and "
            "elevated fear — sometimes the condition where staged deployment makes "
            "most historical sense.\n"
            "- Breadth tells you *who* is participating, not *what* the market will do.\n\n"
            "## Limitations\n\n"
            "Breadth is one data point among many. Markets can sustain narrow rallies "
            "for extended periods; breadth divergences do not reliably predict "
            "reversals. Like all market signals, it describes current conditions — it "
            "does not forecast.\n\n"
            "Related concepts: [India VIX](/learn/concepts/india-vix-explained), "
            "[volatility](/learn/concepts/volatility)."
        ),
    },
    {
        "slug": "patience-in-investing",
        "title": "Patience: the compounding edge",
        "summary": (
            "Patience in investing is the willingness to stay invested through "
            "uncomfortable periods — the trait that lets compounding work its full "
            "effect."
        ),
        "category": "Investing habits",
        "sort_order": 115,
        "body_md": (
            "## Why patience is structural, not just character\n\n"
            "Long-run equity returns in India have historically been positive — but they "
            "have arrived unevenly. A significant fraction of total long-run returns has "
            "come in brief windows: missing the best few days or months in a decade "
            "has historically cost a large share of the gain. An investor who exits "
            "during bad periods risks missing the recovery.\n\n"
            "## The arithmetic of staying in\n\n"
            "Compounding accelerates with time: the later years of a long holding "
            "period contribute more absolute growth than the early years. An investor "
            "who exits after 7 years of a 10-year compounding curve captures only a "
            "fraction of the curve's total rise. " + _ILLUS + "\n\n"
            "## What patience is NOT\n\n"
            "- Patience is not the same as inaction. Reviewing allocations periodically "
            "and rebalancing is consistent with patience.\n"
            "- Patience does not mean staying invested in the *wrong* instrument "
            "indefinitely. The case for patience applies to diversified, goal-aligned "
            "investments — not to individual stocks or thematic bets held past their "
            "thesis.\n"
            "- Patience does not overcome poor asset allocation or mismatch between "
            "portfolio risk and personal situation.\n\n"
            "## The behavioural challenge\n\n"
            "Patience is cognitively difficult because short-term pain is vivid and "
            "immediate while compounding gains are slow and abstract. This is precisely "
            "why mechanical disciplines — SIPs, pre-set deployment ladders, and "
            "pre-committed rules — are useful: they remove the decision from the "
            "uncomfortable moment.\n\n"
            "Related concepts: [compounding](/learn/concepts/compounding), "
            "[SIP & rupee-cost averaging](/learn/concepts/sip-rupee-cost-averaging)."
        ),
    },
    {
        "slug": "sip-discipline",
        "title": "Why SIP discipline beats market timing",
        "summary": (
            "Consistent, rule-bound investing through market cycles has historically "
            "outperformed attempts to time when to invest — even imperfect timing."
        ),
        "category": "Investing habits",
        "sort_order": 120,
        "body_md": (
            "## The seductive idea of market timing\n\n"
            "Market timing — buying just before markets rise and selling just before "
            "they fall — would be immensely valuable if it were reliably possible. "
            "Decades of research across markets suggest it is not, at least not "
            "consistently. Even professionals whose entire job is predicting markets "
            "fail to do so better than chance over long horizons.\n\n"
            "## What 'SIP discipline' means\n\n"
            "SIP discipline means investing the same amount at the same interval — "
            "every month, regardless of whether markets are up, down, or sideways. "
            "It is a commitment to *not* try to time entry points, which removes the "
            "psychological burden of constant market-watching.\n\n"
            "## The evidence from hypothetical scenarios\n\n"
            "Studies have repeatedly modelled different investor types — the perfect "
            "timer, the consistent SIP investor, the investor who always buys at peaks, "
            "and the investor who leaves money in cash waiting for the perfect moment. "
            "The consistent SIP investor almost always beats the worst-timer and the "
            "perennial cash-holder, and typically comes close to the perfect timer "
            "(who does not exist in practice). " + _ILLUS + "\n\n"
            "## Why rules beat decisions under uncertainty\n\n"
            "Rules eliminate the worst outcomes of emotional decision-making. The "
            "biggest risk for most investors is not a bad market — it is acting "
            "impulsively at exactly the wrong moment. A pre-committed SIP schedule "
            "acts as a circuit-breaker against that impulse.\n\n"
            "Related concepts: [SIP & rupee-cost averaging]"
            "(/learn/concepts/sip-rupee-cost-averaging), "
            "[patience in investing](/learn/concepts/patience-in-investing), "
            "[compounding](/learn/concepts/compounding)."
        ),
    },
]
