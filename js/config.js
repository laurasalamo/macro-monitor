// Section/card/chart definitions driving the generic renderer in app.js.
// Adding or removing a card later is a matter of editing this array only.

// Regime Dashboard indicator cards. Thresholds and bullish/neutral/bearish
// ratings come from scripts/regime_logic.py via data.json; this only covers
// presentation. `period` drives how the as-of date reads; `lineLabel` renames the
// main chart line; `extra` adds more
// lines to the card's pop-up chart.
const REGIME_CARDS = [
  { key: "gdp_growth", label: "GDP Growth", suffix: "% real growth", unit: "%", period: "quarter",
    title: "Real GDP Growth (annualized, quarter over quarter)", fred: "A191RL1Q225SBEA" },
  { key: "cpi_yoy", label: "Inflation (CPI)", suffix: "% YoY", unit: "%", period: "month",
    title: "CPI Inflation (year over year)", fred: "CPIAUCSL" },
  { key: "unemployment", label: "Unemployment", suffix: "%", unit: "%", period: "month",
    title: "Unemployment Rate", fred: "UNRATE" },
  { key: "payrolls_mom", label: "Payrolls MoM", suffix: "K", unit: "K", signed: true, period: "month",
    title: "Nonfarm Payrolls, monthly change (thousands)", fred: "PAYEMS" },
  { key: "spread_10y2y", label: "10Y-2Y Spread", suffix: "pp", unit: "pp", signed: true, period: "day",
    title: "10-Year minus 2-Year Treasury Yield", fred: "T10Y2Y" },
  { key: "spread_2y3m", label: "2Y-3M Spread", suffix: "pp", unit: "pp", signed: true, period: "day",
    title: "2-Year minus 3-Month Treasury Yield", fred: "DGS2,DGS3MO" },
  { key: "claims_4wk", label: "Jobless Claims", suffix: "K", unit: "K", period: "week",
    title: "Initial Jobless Claims, 4-week average (thousands)", fred: "IC4WSA",
    lineLabel: "4-week average", extra: [{ key: "initial_claims", label: "Weekly" }] },
];

// Time-range buttons for section charts (see setupChartControls in app.js).
const STANDARD_RANGES = ["1Y", "2Y", "5Y", "10Y", "Max"];

const SECTIONS = [
  { id: "regime", title: "Regime Dashboard", kind: "regime" },

  {
    id: "credit",
    title: "Credit Spreads",
    description:
      "Option-adjusted spreads vs Treasuries. HY widening typically leads equity drawdowns by 1–3 months.",
    cards: [
      { label: "HY OAS", path: "credit_spreads.hy_oas", unit: "pp" },
      { label: "IG OAS", path: "credit_spreads.ig_oas", unit: "pp" },
      { label: "EM Corp OAS", path: "credit_spreads.em_corp_oas", unit: "pp" },
    ],
    chart: {
      title: "Credit Spreads",
      // Range buttons above the chart; "Max" is everything data.json has.
      ranges: ["3M", "6M", "1Y", "2Y", "Max"],
      defaultRange: "Max",
      toggles: true,
      note: "FRED publishes only the last 3 years of ICE BofA spread data.",
      series: [
        { path: "credit_spreads.hy_oas", label: "HY OAS", color: "#dc2626" },
        { path: "credit_spreads.ig_oas", label: "IG OAS", color: "#2563eb" },
        { path: "credit_spreads.em_corp_oas", label: "EM Corp OAS", color: "#d97706" },
      ],
    },
  },

  {
    id: "inflation",
    title: "Inflation Expectations",
    description:
      "Nominal Treasury yield ≈ breakeven (market-implied inflation) + TIPS real yield, for 5Y and 10Y, plus the 5Y5Y forward and Core PCE — the underlying inflation the Fed targets.",
    cardColumns: 4, // one row of 5Y measures, one of 10Y
    cards: [
      { label: "5Y Treasury", path: "treasury_spreads.y5", unit: "%" },
      { label: "5Y Breakeven", path: "inflation.breakeven_5y", unit: "%" },
      { label: "5Y TIPS Yield", path: "inflation.tips_5y", unit: "%" },
      { label: "5Y5Y Forward", path: "inflation.forward_5y5y", unit: "%" },
      { label: "10Y Treasury", path: "treasury_spreads.y10", unit: "%" },
      { label: "10Y Breakeven", path: "inflation.breakeven_10y", unit: "%" },
      { label: "10Y TIPS Yield", path: "inflation.real_10y", unit: "%" },
      { label: "Core PCE YoY", path: "inflation.core_pce_yoy", unit: "%" },
    ],
    chart: {
      title: "Nominal Yields, Breakevens, TIPS Yields & Core PCE",
      ranges: STANDARD_RANGES,
      defaultRange: "5Y",
      toggles: true,
      note: "Click a label to show or hide its line.",
      series: [
        { path: "treasury_spreads.y5", label: "5Y Nominal", color: "#3b82f6" },
        { path: "treasury_spreads.y10", label: "10Y Nominal", color: "#f97316" },
        { path: "inflation.breakeven_5y", label: "5Y BE", color: "#22c55e" },
        { path: "inflation.breakeven_10y", label: "10Y BE", color: "#d946ef" },
        { path: "inflation.tips_5y", label: "5Y TIPS", color: "#eab308" },
        { path: "inflation.real_10y", label: "10Y TIPS", color: "#06b6d4" },
        { path: "inflation.forward_5y5y", label: "5Y5Y Fwd", color: "#ef4444" },
        { path: "inflation.core_pce_yoy", label: "Core PCE", color: "#94a3b8" },
      ],
    },
  },

  {
    id: "liquidity",
    title: "Liquidity & Financial Conditions",
    description:
      "NFCI is the Chicago Fed's index of overall financial conditions. Above zero = tighter than average, below = looser. Click a card to chart it.",
    cards: [
      { label: "NFCI", path: "liquidity.nfci", unit: "" },
      { label: "Fed Balance Sheet", path: "liquidity.fed_assets", unit: "T$" },
      { label: "Overnight RRP", path: "liquidity.rrp", unit: "T$" },
      { label: "M2", path: "liquidity.m2", unit: "T$" },
    ],
    chart: {
      // Click a card to chart it; one series at a time since units differ.
      switchable: true,
      ranges: STANDARD_RANGES,
      defaultRange: "5Y",
      series: [
        { path: "liquidity.nfci", label: "NFCI", title: "NFCI (Chicago Fed National Financial Conditions Index)", color: "#4f46e5" },
        { path: "liquidity.fed_assets", label: "Fed Balance Sheet", title: "Fed Balance Sheet — total assets (T$)", color: "#16a34a" },
        { path: "liquidity.rrp", label: "Overnight RRP", title: "Overnight Reverse Repo usage (T$)", color: "#d97706" },
        { path: "liquidity.m2", label: "M2", title: "M2 Money Supply (T$)", color: "#0891b2" },
      ],
    },
  },

  { id: "yield_curve", title: "Yield Curve Shape", kind: "curve" },

  // kind "macro": cards with a data-age badge, then two charts side by side.
  // `stateKey` colors a card's value by its Regime Dashboard rating; `asOfPath`
  // is the release dated in the section header.
  {
    id: "growth_inflation",
    title: "Growth & Inflation",
    kind: "macro",
    asOfPath: "growth_labor.cpi_yoy",
    cards: [
      { label: "Real GDP Growth", path: "growth_labor.gdp_growth", unit: "%", decimals: 1, stateKey: "gdp_growth" },
      { label: "CPI YoY", path: "growth_labor.cpi_yoy", unit: "%", decimals: 1, stateKey: "cpi_yoy" },
      { label: "Saving Rate", path: "growth_labor.saving_rate", unit: "%", decimals: 1 },
      { label: "Fed Funds", path: "growth_labor.fed_funds", unit: "%", decimals: 2 },
    ],
    charts: [
      {
        title: "Consumption-Adjusted Growth",
        subtitle: "Real GDP growth / (1 − Saving Rate)",
        bars: true,
        unit: "%",
        timeUnit: "quarter",
        ranges: STANDARD_RANGES,
        defaultRange: "1Y",
        series: [{ path: "growth_labor.adj_growth", label: "Adjusted growth" }],
      },
      {
        title: "Consumption Backed by Income",
        subtitle: "Real PCE / (1 − Saving Rate), trillions of chained 2017 $",
        unit: "T",
        timeUnit: "quarter",
        ranges: STANDARD_RANGES,
        defaultRange: "1Y",
        series: [{ path: "growth_labor.consumption_backed", label: "Consumption backed by income", color: "#3b82f6" }],
      },
    ],
  },

  {
    id: "labor",
    title: "Labor Market",
    kind: "macro",
    asOfPath: "growth_labor.initial_claims",
    cards: [
      { label: "Unemployment", path: "growth_labor.unemployment", unit: "%", decimals: 1, stateKey: "unemployment" },
      { label: "Payrolls (monthly)", path: "growth_labor.payrolls_mom", unit: "K", decimals: 0, signed: true, stateKey: "payrolls_mom" },
      { label: "Jobless Claims", path: "growth_labor.initial_claims", unit: "K", decimals: 0, showDate: true },
      { label: "Participation Rate", path: "growth_labor.participation", unit: "%", decimals: 1 },
    ],
    charts: [
      {
        title: "Unemployment Rate",
        unit: "%",
        ranges: STANDARD_RANGES,
        defaultRange: "2Y",
        series: [{ path: "growth_labor.unemployment", label: "Unemployment", color: "#3b82f6" }],
      },
      {
        title: "Payrolls by Category (MoM Δ, thousands)",
        categoryPath: "growth_labor.payrolls_by_category",
        datePath: "growth_labor.payrolls_mom",
      },
    ],
  },

  {
    id: "cross_asset",
    title: "Cross-Asset",
    description:
      "Cross-asset directional reads. Stocks↑ + USD↑ + Gold↓ = clean risk-on. Mixed signals = caution.",
    cards: [
      { label: "VIX", path: "cross_asset.vix", unit: "" },
      { label: "Gold (USD/oz)", path: "cross_asset.gold", unit: "$" },
      { label: "WTI (USD/bbl)", path: "cross_asset.wti", unit: "$" },
      { label: "Broad Dollar Index", path: "cross_asset.dxy", unit: "" },
      { label: "EUR/USD", path: "cross_asset.eurusd", unit: "" },
      { label: "USD/JPY", path: "cross_asset.usdjpy", unit: "" },
    ],
  },

  {
    id: "momentum",
    title: "Momentum Composite",
    kind: "momentum",
    description:
      "Cross-sectional ETF momentum ranking, updated daily. Score 0–100 = 45% trend + 15% acceleration + 25% proximity to 52-week high + 15% low volatility, each percentile-ranked against the other ETFs below (a relative ranking, not a return forecast). Own methodology, inspired by the concept of commercial momentum-ranking tools but not a reproduction of any specific one's formula.",
  },

  {
    id: "treasury",
    title: "Treasury Spreads",
    cardColumns: 3,
    cards: [
      { label: "2Y Treasury", path: "treasury_spreads.y2", unit: "%" },
      { label: "3M Treasury", path: "treasury_spreads.m3", unit: "%" },
      { label: "5Y Treasury", path: "treasury_spreads.y5", unit: "%" },
      { label: "10Y Treasury", path: "treasury_spreads.y10", unit: "%" },
      { label: "2Y-3M Spread", path: "treasury_spreads.spread_2y3m", unit: "pp" },
      { label: "10Y-2Y Spread", path: "treasury_spreads.spread_10y2y", unit: "pp" },
    ],
    chart: {
      title: "Treasury Yields: 10Y vs 2Y",
      ranges: STANDARD_RANGES,
      defaultRange: "5Y",
      toggles: true,
      series: [
        { path: "treasury_spreads.y10", label: "10Y Treasury", color: "#2563eb" },
        { path: "treasury_spreads.y2", label: "2Y Treasury", color: "#d97706" },
      ],
    },
  },
];
