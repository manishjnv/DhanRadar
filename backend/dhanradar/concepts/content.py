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
]
