#!/usr/bin/env python3
"""
Market Briefing Updater — run this anytime to refresh ~/Claude/market_briefing.md
Usage: python3 ~/Claude/update_market_briefing.py
"""

import subprocess
import sys
import re
from datetime import datetime, date

def install(pkg):
    subprocess.check_call([sys.executable, "-m", "pip", "install", pkg, "-q"])

try:
    import yfinance as yf
except ImportError:
    print("Installing yfinance...")
    install("yfinance")
    import yfinance as yf

try:
    import requests
    from bs4 import BeautifulSoup
except ImportError:
    print("Installing requests/beautifulsoup4...")
    install("requests")
    install("beautifulsoup4")
    import requests
    from bs4 import BeautifulSoup

# ── Tickers ────────────────────────────────────────────────────────────────────

TICKERS = {
    "S&P 500":            "^GSPC",
    "Nasdaq":             "^IXIC",
    "Dow Jones":          "^DJI",
    "VIX":                "^VIX",
    "10-Year Treasury":   "^TNX",
    "3-Month Treasury":   "^IRX",
    "Dollar Index (DXY)": "DX-Y.NYB",
    "Bitcoin":            "BTC-USD",
    "Gold":               "GC=F",
    "WTI Crude Oil":      "CL=F",
}

EXTENDED_TICKERS = {
    "Silver":          "SI=F",
    "Copper":          "HG=F",
    "Natural Gas":     "NG=F",
    "EUR/USD":         "EURUSD=X",
    "USD/JPY":         "JPY=X",
    "LQD (IG Bonds)":  "LQD",
    "HYG (HY Bonds)":  "HYG",
}

SECTORS = {
    "Technology":       "XLK",
    "Financials":       "XLF",
    "Energy":           "XLE",
    "Healthcare":       "XLV",
    "Industrials":      "XLI",
    "Consumer Disc.":   "XLY",
    "Consumer Staples": "XLP",
    "Comm. Services":   "XLC",
    "Utilities":        "XLU",
    "Real Estate":      "XLRE",
    "Materials":        "XLB",
}

# FOMC meeting dates 2026 (start of each meeting)
FOMC_DATES_2026 = [
    date(2026, 1, 28), date(2026, 3, 18), date(2026, 5, 6),
    date(2026, 6, 17), date(2026, 7, 29), date(2026, 9, 16),
    date(2026, 11, 4), date(2026, 12, 9),
]

# ── Fetch all market data once ─────────────────────────────────────────────────

def fetch_market_data():
    all_keys = {
        'sp': '^GSPC', 'ndq': '^IXIC', 'dji': '^DJI',
        'tnx': '^TNX', 'irx': '^IRX', 'vix': '^VIX',
        'dxy': 'DX-Y.NYB', 'gold': 'GC=F', 'btc': 'BTC-USD', 'oil': 'CL=F',
        'silver': 'SI=F', 'copper': 'HG=F', 'natgas': 'NG=F',
        'eurusd': 'EURUSD=X', 'usdjpy': 'JPY=X',
        'lqd': 'LQD', 'hyg': 'HYG',
    }
    info = {}
    for k, v in all_keys.items():
        try:
            info[k] = yf.Ticker(v).fast_info
        except:
            info[k] = None

    def safe_price(k):
        try: return info[k].last_price if info[k] else None
        except: return None

    def safe_prev(k):
        try: return info[k].previous_close if info[k] else None
        except: return None

    def pct(k):
        p, c = safe_price(k), safe_prev(k)
        return ((p - c) / c) * 100 if p and c and c != 0 else 0.0

    try:
        _tnx_p = safe_price('tnx')
        _tnx_c = safe_prev('tnx')
        md = {
            'sp_price':  safe_price('sp'),  'sp_chg':  pct('sp'),
            'ndq_price': safe_price('ndq'), 'ndq_chg': pct('ndq'),
            'dji_price': safe_price('dji'), 'dji_chg': pct('dji'),
            'vix_val':   safe_price('vix') or 20,
            'vix_chg':   (safe_price('vix') or 20) - (safe_prev('vix') or 20),
            'yield_10y': _tnx_p or 4.3,
            'yield_3m':  safe_price('irx') or 3.6,
            'yield_chg': ((_tnx_p - _tnx_c) * 100) if (_tnx_p is not None and _tnx_c is not None) else 0.0,
            'dxy_val':   safe_price('dxy') or 100, 'dxy_chg': pct('dxy'),
            'gold_price':safe_price('gold') or 0,  'gold_chg': pct('gold'),
            'btc_price': safe_price('btc') or 0,   'btc_chg':  pct('btc'),
            'oil_price': safe_price('oil') or 0,   'oil_chg':  pct('oil'),
            'silver_price': safe_price('silver') or 0, 'silver_chg': pct('silver'),
            'copper_price': safe_price('copper') or 0, 'copper_chg': pct('copper'),
            'natgas_price': safe_price('natgas') or 0, 'natgas_chg': pct('natgas'),
            'eurusd': safe_price('eurusd') or 0,   'eurusd_chg': pct('eurusd'),
            'usdjpy': safe_price('usdjpy') or 0,   'usdjpy_chg': pct('usdjpy'),
            'lqd_chg': pct('lqd'),
            'hyg_chg': pct('hyg'),
        }
        md['spread'] = md['yield_10y'] - md['yield_3m']
        sp, sv = md['silver_price'], md.get('silver_price', 0)
        md['gold_silver_ratio'] = round(md['gold_price'] / sv, 1) if sv and sv > 0 else None
        return md
    except Exception as e:
        print(f"Warning: market data fetch failed — {e}")
        return None

# ── Fetch YTD changes ──────────────────────────────────────────────────────────

def fetch_ytd_changes():
    ytd = {}
    start = f"{date.today().year}-01-01"
    all_tickers = {**TICKERS, **EXTENDED_TICKERS, **SECTORS}
    for name, ticker in all_tickers.items():
        try:
            hist = yf.Ticker(ticker).history(start=start)
            if len(hist) >= 2:
                start_price = hist['Close'].iloc[0]
                current_price = hist['Close'].iloc[-1]
                ytd[ticker] = ((current_price - start_price) / start_price) * 100
            else:
                ytd[ticker] = None
        except:
            ytd[ticker] = None
    return ytd

def fmt_ytd(ytd_changes, ticker):
    val = ytd_changes.get(ticker)
    if val is None:
        return "—"
    sign = "+" if val >= 0 else ""
    arrow = "▲" if val >= 0 else "▼"
    return f"{sign}{val:.1f}% {arrow}"

# ── Fetch prices table ─────────────────────────────────────────────────────────

def fetch_prices(ytd_changes):
    rows = []
    for name, ticker in TICKERS.items():
        try:
            info = yf.Ticker(ticker).fast_info
            price = info.last_price
            prev  = info.previous_close
            ytd   = fmt_ytd(ytd_changes, ticker)
            if price and prev:
                change_pct = ((price - prev) / prev) * 100
                arrow = "▲" if change_pct >= 0 else "▼"
                sign  = "+" if change_pct >= 0 else ""
                if name in ("10-Year Treasury", "3-Month Treasury"):
                    change_bps = (price - prev) * 100
                    bps_sign = "+" if change_bps >= 0 else ""
                    rows.append(f"| {name} | {price:.3f}% | {bps_sign}{change_bps:.1f} bps {arrow} | {ytd} |")
                elif name == "VIX":
                    change_pts = price - prev
                    pts_sign = "+" if change_pts >= 0 else ""
                    rows.append(f"| {name} | {price:.2f} | {pts_sign}{change_pts:.2f} pts {arrow} | {ytd} |")
                elif name in ("Bitcoin", "Gold", "WTI Crude Oil"):
                    rows.append(f"| {name} | ${price:,.2f} | {sign}{change_pct:.2f}% {arrow} | {ytd} |")
                else:
                    rows.append(f"| {name} | {price:,.2f} | {sign}{change_pct:.2f}% {arrow} | {ytd} |")
            else:
                rows.append(f"| {name} | — | — | — |")
        except:
            rows.append(f"| {name} | — | — | — |")
    return rows

# ── Fetch extended markets table ──────────────────────────────────────────────

def fetch_extended_prices(md, ytd_changes):
    if not md:
        return []
    rows = []
    items = [
        ("Silver",      f"${md['silver_price']:,.2f}",   md['silver_chg'],  EXTENDED_TICKERS['Silver']),
        ("Copper",      f"${md['copper_price']:.3f}/lb",  md['copper_chg'],  EXTENDED_TICKERS['Copper']),
        ("Natural Gas", f"${md['natgas_price']:.3f}",    md['natgas_chg'],  EXTENDED_TICKERS['Natural Gas']),
        ("EUR/USD",     f"{md['eurusd']:.4f}",            md['eurusd_chg'],  EXTENDED_TICKERS['EUR/USD']),
        ("USD/JPY",     f"{md['usdjpy']:.2f}",            md['usdjpy_chg'],  EXTENDED_TICKERS['USD/JPY']),
        ("LQD (IG)",    "ETF",                            md['lqd_chg'],     EXTENDED_TICKERS['LQD (IG Bonds)']),
        ("HYG (HY)",    "ETF",                            md['hyg_chg'],     EXTENDED_TICKERS['HYG (HY Bonds)']),
    ]
    for name, price_str, chg, ticker in items:
        ytd = fmt_ytd(ytd_changes, ticker)
        if chg is not None:
            arrow = "▲" if chg >= 0 else "▼"
            sign  = "+" if chg >= 0 else ""
            rows.append(f"| {name} | {price_str} | {sign}{chg:.2f}% {arrow} | {ytd} |")
        else:
            rows.append(f"| {name} | {price_str} | — | {ytd} |")
    return rows

# ── Market Regime Box ──────────────────────────────────────────────────────────

def generate_regime_box(md):
    if not md:
        return ""

    # Risk appetite
    if md['sp_chg'] > 0.5 and md['vix_chg'] < 0:
        risk = "🟢 Risk-On"
    elif md['sp_chg'] < -0.5 and md['vix_chg'] > 0:
        risk = "🔴 Risk-Off"
    else:
        risk = "🟡 Mixed"

    # Yield curve
    if md['spread'] < 0:
        curve = "🔴 Inverted ⚠️"
    elif md['spread'] < 0.3:
        curve = "🟡 Flattening"
    else:
        curve = "🟢 Healthy"

    # Dollar
    if md['dxy_val'] < 100:
        dollar = "🟢 Weak (commodity tailwind)"
    elif md['dxy_val'] > 105:
        dollar = "🔴 Strong (commodity headwind)"
    else:
        dollar = "🟡 Neutral"

    # Vol regime
    if md['vix_val'] < 15:
        vol = "🟢 Complacent (buy protection)"
    elif md['vix_val'] < 20:
        vol = "🟢 Calm"
    elif md['vix_val'] < 30:
        vol = "🟡 Elevated"
    else:
        vol = "🔴 Fear / Crisis"

    # Credit proxy (HYG vs LQD — if HY selling off more than IG, credit stress)
    hyg, lqd = md.get('hyg_chg', 0), md.get('lqd_chg', 0)
    if hyg < -0.5 and hyg < lqd - 0.3:
        credit = "🟡 HY spreads widening — watch"
    elif hyg < -1.0:
        credit = "🔴 Credit stress signal"
    else:
        credit = "🟢 Stable"

    # Copper / growth proxy
    copper_chg = md.get('copper_chg', 0)
    if copper_chg > 0.5:
        growth = f"🟢 Expanding (copper +{copper_chg:.2f}%)"
    elif copper_chg < -0.5:
        growth = f"🔴 Slowing (copper {copper_chg:.2f}%)"
    else:
        growth = "🟡 Neutral"

    return (
        f"| Signal | Reading | Implication |\n"
        f"|---|---|---|\n"
        f"| Risk Appetite | {risk} | Equities {md['sp_chg']:+.2f}%, VIX {md['vix_chg']:+.2f} pts |\n"
        f"| Yield Curve | {curve} | 3M-10Y spread {md['spread']:+.3f}% |\n"
        f"| Dollar (DXY) | {dollar} | DXY {md['dxy_val']:.2f} ({md['dxy_chg']:+.2f}%) |\n"
        f"| Vol Regime | {vol} | VIX {md['vix_val']:.1f} |\n"
        f"| Credit | {credit} | HYG {hyg:+.2f}%, LQD {lqd:+.2f}% |\n"
        f"| Growth Proxy | {growth} | Copper = 'Dr. Copper' economic indicator |"
    )

# ── Fetch sector performance ───────────────────────────────────────────────────

def fetch_sectors(ytd_changes):
    rows = []
    for name, ticker in SECTORS.items():
        try:
            info = yf.Ticker(ticker).fast_info
            price = info.last_price
            prev  = info.previous_close
            ytd   = fmt_ytd(ytd_changes, ticker)
            if price and prev:
                chg = ((price - prev) / prev) * 100
                arrow = "▲" if chg >= 0 else "▼"
                sign  = "+" if chg >= 0 else ""
                rows.append(f"| {name} | {ticker} | {sign}{chg:.2f}% {arrow} | {ytd} |")
            else:
                rows.append(f"| {name} | {ticker} | — | {ytd} |")
        except:
            rows.append(f"| {name} | {ticker} | — | — |")
    return rows

# ── Fetch news ─────────────────────────────────────────────────────────────────

def fetch_yahoo_news():
    headlines = []
    try:
        headers = {"User-Agent": "Mozilla/5.0"}
        r = requests.get("https://finance.yahoo.com/topic/latest-news/", headers=headers, timeout=10)
        soup = BeautifulSoup(r.text, "html.parser")
        for tag in soup.find_all("h3", limit=10):
            text = tag.get_text(strip=True)
            if len(text) > 20:
                headlines.append(text)
        headlines = headlines[:7]
    except:
        pass
    return headlines

def fetch_morning_brew_news():
    headlines = []
    try:
        headers = {"User-Agent": "Mozilla/5.0"}
        r = requests.get("https://www.morningbrew.com/daily", headers=headers, timeout=10)
        soup = BeautifulSoup(r.text, "html.parser")
        for tag in soup.find_all(["h2", "h3"], limit=15):
            text = tag.get_text(strip=True)
            if len(text) > 20 and len(text) < 200:
                headlines.append(text)
        headlines = list(dict.fromkeys(headlines))[:5]
    except:
        pass
    return headlines

# ── Macro read ─────────────────────────────────────────────────────────────────

def macro_read(md):
    if not md:
        return ["- Market data unavailable for macro read"]

    sections = []
    sp_chg, ndq_chg, dji_chg = md['sp_chg'], md['ndq_chg'], md['dji_chg']
    vix_val, vix_chg = md['vix_val'], md['vix_chg']
    yield_10y, yield_3m, yield_chg, spread = md['yield_10y'], md['yield_3m'], md['yield_chg'], md['spread']
    dxy_val, dxy_chg = md['dxy_val'], md['dxy_chg']
    gold_price, gold_chg = md['gold_price'], md['gold_chg']
    oil_price, oil_chg = md['oil_price'], md['oil_chg']
    btc_price, btc_chg = md['btc_price'], md['btc_chg']

    # ── Equities ───────────────────────────────────────────────────────────────
    eq_lines = []
    if ndq_chg > sp_chg + 0.5:
        eq_lines.append(
            f"**Equities: Tech is leading today** — Nasdaq ({ndq_chg:+.2f}%) is outpacing the S&P 500 ({sp_chg:+.2f}%). "
            f"The Nasdaq is heavy in tech and growth companies (Apple, Nvidia, Microsoft, Meta), so when it leads, "
            f"it means investors are feeling confident and willing to buy riskier, high-growth names. "
            f"This is called a *risk-on* environment."
        )
    elif sp_chg > ndq_chg + 0.5:
        eq_lines.append(
            f"**Equities: Broad market leading** — S&P 500 ({sp_chg:+.2f}%) is outpacing the Nasdaq ({ndq_chg:+.2f}%). "
            f"When the S&P leads Nasdaq, it usually means investors are rotating into more stable, 'value' companies "
            f"(banks, energy, healthcare) instead of high-growth tech. This is called a *value rotation*."
        )
    else:
        eq_lines.append(
            f"**Equities: Balanced move** — S&P 500 ({sp_chg:+.2f}%) and Nasdaq ({ndq_chg:+.2f}%) are moving together. "
            f"No strong rotation signal — broad participation across sectors."
        )
    if dji_chg < 0 and ndq_chg > 0:
        eq_lines.append(
            f"The Dow ({dji_chg:+.2f}%) is red while Nasdaq is green — tech winning while traditional blue-chips "
            f"(Boeing, Caterpillar, Goldman) lag. Classic growth-over-value setup."
        )
    elif dji_chg > 0 and ndq_chg < 0:
        eq_lines.append(
            f"The Dow ({dji_chg:+.2f}%) is green while Nasdaq is red — money rotating out of growth/tech "
            f"into dividend-paying blue chips. Happens when rates rise or risk appetite fades."
        )
    sections.append("\n".join(eq_lines))

    # ── VIX ────────────────────────────────────────────────────────────────────
    if vix_val < 15:
        vix_feel = "very low — markets are complacent"
        vix_interp = (
            "Low VIX means options are cheap and investors aren't expecting big moves. "
            "When IV is low, options premiums are low — good time to buy protection cheaply. "
            "Some traders see very low VIX as a contrarian warning sign — complacency before a shock."
        )
    elif vix_val < 20:
        vix_feel = "normal range"
        vix_interp = (
            "VIX between 15–20 is the market's 'calm but alert' zone. "
            "Options are fairly priced — no extreme fear or complacency. "
            "This is the baseline you'll see on most ordinary trading days."
        )
    elif vix_val < 25:
        vix_feel = "elevated — some fear in the market"
        vix_interp = (
            "Elevated VIX means options are getting more expensive as traders buy protection. "
            "Implied volatility (the vol input in Black-Scholes) is rising — "
            "options sellers collect more premium, but directional moves are harder to predict."
        )
    elif vix_val < 35:
        vix_feel = "high — significant fear"
        vix_interp = (
            "High VIX signals real market stress. Implied volatility is elevated, "
            "making options expensive. Small changes in σ dramatically change option prices in Black-Scholes — "
            "this is the regime where your vol assumptions matter most."
        )
    else:
        vix_feel = "extreme — crisis territory"
        vix_interp = (
            "VIX above 35 is crisis-level fear (think 2008, COVID crash, 2022 inflation shock). "
            "Options pricing goes haywire — bid-ask spreads widen, models break down. "
            "Tail-risk hedges pay off here; vol sellers get wiped out."
        )

    vix_dir = "up" if vix_chg > 0 else "down"
    sections.append(
        f"**VIX (Fear Index) at {vix_val:.2f}** ({vix_feel}) — "
        f"The VIX measures the market's expectation of S&P 500 volatility over the next 30 days, "
        f"derived from options prices. Think of it as the market's 'anxiety meter.' "
        f"It's {vix_dir} {abs(vix_chg):.2f} points today. "
        f"{vix_interp} "
        f"Rule of thumb: VIX < 20 = calm, 20–30 = worried, > 30 = fearful."
    )

    # ── Yield curve ────────────────────────────────────────────────────────────
    if spread > 0.5:
        curve_shape = "normal (upward sloping)"
        curve_interp = (
            f"The 10-year yield ({yield_10y:.3f}%) is notably higher than the 3-month ({yield_3m:.3f}%), "
            f"which is the normal state — investors demand more return for locking up money longer. "
            f"A steep curve is generally a sign of economic optimism and healthy credit conditions."
        )
    elif spread > 0:
        curve_shape = "flat"
        curve_interp = (
            f"The 10-year ({yield_10y:.3f}%) and 3-month ({yield_3m:.3f}%) yields are close together. "
            f"A flat curve signals uncertainty — the market isn't sure if growth or recession is ahead. "
            f"Watch for whether it steepens (bullish) or inverts (warning sign)."
        )
    else:
        curve_shape = "INVERTED ⚠️"
        curve_interp = (
            f"The 3-month yield ({yield_3m:.3f}%) is HIGHER than the 10-year ({yield_10y:.3f}%), "
            f"which is abnormal and historically one of the most reliable recession predictors. "
            f"It signals investors expect the Fed to cut rates as the economy slows. "
            f"Every US recession since 1955 was preceded by an inverted yield curve."
        )

    sections.append(
        f"**Yield Curve: 3M at {yield_3m:.3f}% vs. 10Y at {yield_10y:.3f}% — spread: {spread:+.3f}%** ({curve_shape}) — "
        f"The yield curve plots interest rates across maturities. The 3M-10Y spread is the most-watched recession signal. "
        f"{curve_interp}"
    )

    # ── DXY ────────────────────────────────────────────────────────────────────
    if dxy_val > 105:
        dxy_feel = "strong"
        dxy_interp = (
            "A strong dollar hurts US multinationals (overseas earnings worth less when converted back), "
            "puts downward pressure on commodities (oil and gold priced in USD), "
            "and squeezes emerging market economies with dollar-denominated debt."
        )
    elif dxy_val > 100:
        dxy_feel = "neutral"
        dxy_interp = (
            "Dollar is in a neutral zone — not strong enough to significantly hurt multinationals, "
            "not weak enough to give commodities a major boost. Watch direction more than absolute level."
        )
    else:
        dxy_feel = "weak"
        dxy_interp = (
            "A weak dollar is a tailwind for commodities (gold, oil get cheaper to buy in other currencies → more demand), "
            "boosts earnings of US multinationals when foreign revenue is converted back, "
            "and attracts capital to emerging markets."
        )

    dxy_dir = "up" if dxy_chg > 0 else "down"
    sections.append(
        f"**Dollar Index (DXY) at {dxy_val:.2f}** ({dxy_feel}, {dxy_chg:+.2f}% today) — "
        f"DXY measures the US dollar against a basket of major currencies (euro, yen, pound, etc.). "
        f"It's the missing link that connects equities, commodities, and global markets. "
        f"Dollar is {dxy_dir} today. {dxy_interp}"
    )

    # ── Interest rates ─────────────────────────────────────────────────────────
    if yield_10y > 4.5:
        rate_feel, rate_interp = "elevated", (
            "High rates make borrowing expensive, slow growth, and make bonds more attractive vs. stocks. "
            "Tech/growth stocks are hit hardest — their value comes from future profits, "
            "which are worth less when discounted at a higher rate (lower NPV)."
        )
    elif yield_10y < 4.0:
        rate_feel, rate_interp = "relatively low", (
            "Lower rates support corporate investment and consumer spending, and push money into stocks. "
            "Growth stocks benefit most — future profits discounted at a lower rate → higher valuations."
        )
    else:
        rate_feel, rate_interp = "moderate", (
            "Rates aren't crushing growth, but aren't a strong tailwind either. "
            "Market is in 'wait and see' mode on the Fed."
        )

    bps_dir = "down" if yield_chg < 0 else "up"
    sections.append(
        f"**10-Year Treasury at {yield_10y:.3f}%** ({rate_feel}) — "
        f"The risk-free baseline every asset is priced against. "
        f"{rate_interp} "
        f"Today rates ticked {bps_dir} {abs(yield_chg):.1f} bps — "
        + ("mild tailwind for stocks, especially tech." if yield_chg < 0 else "mild pressure on growth stocks.")
    )

    # ── Gold ───────────────────────────────────────────────────────────────────
    if gold_price > 3000:
        gold_context = (
            f"**Gold at ${gold_price:,.0f}** ({gold_chg:+.2f}% today) — "
            f"Gold historically traded $1,800–2,000. At ${gold_price:,.0f} it reflects sustained macro anxiety. "
        )
        if gold_chg > 0 and sp_chg > 0:
            gold_context += "Both gold and stocks up = liquidity-driven, not fear-driven. Money flowing into everything."
        elif gold_chg > 0 and sp_chg < 0:
            gold_context += "Gold up, stocks down = classic flight to safety. Investors are nervous."
        else:
            gold_context += "Watch gold vs. VIX — both elevated together = real fear."
        sections.append(gold_context)

    # ── Oil ────────────────────────────────────────────────────────────────────
    oil_context = f"**Oil (WTI) at ${oil_price:,.2f}** ({oil_chg:+.2f}% today) — "
    if oil_chg < -1.5:
        oil_context += (
            "Sharp drop. Lower oil reduces inflation pressure → less reason for the Fed to keep rates high. "
            "Bad for energy stocks (XOM, CVX), good for airlines and consumers."
        )
    elif oil_chg > 1.5:
        oil_context += (
            "Sharp rise adds to inflation (gas, shipping, manufacturing costs). "
            "Gives the Fed less room to cut rates. Watch geopolitical headlines for supply disruption."
        )
    else:
        oil_context += "Relatively flat — no major supply/demand shock today."
    sections.append(oil_context)

    # ── Copper (Dr. Copper) ────────────────────────────────────────────────────
    copper_price = md.get('copper_price', 0)
    copper_chg   = md.get('copper_chg', 0)
    if copper_price > 0:
        if copper_chg > 1.0:
            copper_signal = "rising sharply — a bullish signal for global economic growth"
            copper_why = "Copper is used in construction, EVs, data centers, and electronics. Rising copper = rising global demand."
        elif copper_chg < -1.0:
            copper_signal = "falling sharply — a warning sign for global growth"
            copper_why = "Copper demand is a proxy for global industrial activity. A sharp drop often precedes slowing growth, especially in China."
        else:
            copper_signal = "relatively flat today"
            copper_why = "No strong growth signal from copper today — watch direction over the coming week."
        gsr = md.get('gold_silver_ratio')
        gsr_note = f" Gold/Silver ratio: {gsr:.1f}x (historical avg ~65x — {'silver cheap' if gsr > 80 else 'ratio normal' if gsr < 75 else 'elevated'})." if gsr else ""
        sections.append(
            f"**Copper ('Dr. Copper') at ${copper_price:.3f}/lb** ({copper_chg:+.2f}% today, {copper_signal}) — "
            f"{copper_why} "
            f"Also key for AI infrastructure: data centers and EV batteries require massive copper.{gsr_note}"
        )

    # ── FX ─────────────────────────────────────────────────────────────────────
    eurusd = md.get('eurusd', 0)
    usdjpy = md.get('usdjpy', 0)
    eurusd_chg = md.get('eurusd_chg', 0)
    usdjpy_chg = md.get('usdjpy_chg', 0)
    if eurusd > 0 and usdjpy > 0:
        usdjpy_note = ""
        if usdjpy > 155:
            usdjpy_note = (
                f" USD/JPY at {usdjpy:.2f} is elevated — BOJ intervention risk is real. "
                f"Japan's central bank has previously stepped in to defend the yen near these levels. "
                f"A sharp yen move would ripple through global carry trades."
            )
        elif usdjpy < 145:
            usdjpy_note = f" USD/JPY at {usdjpy:.2f} — yen strengthening, carry trades under pressure."
        else:
            usdjpy_note = f" USD/JPY at {usdjpy:.2f} — within normal range."

        eurusd_note = ""
        if eurusd_chg > 0.3:
            eurusd_note = f" EUR/USD rising ({eurusd:.4f}) — dollar weakening vs euro, usually commodity-positive."
        elif eurusd_chg < -0.3:
            eurusd_note = f" EUR/USD falling ({eurusd:.4f}) — dollar strengthening vs euro."
        else:
            eurusd_note = f" EUR/USD at {eurusd:.4f} — stable."

        sections.append(
            f"**FX Markets** — {eurusd_note}{usdjpy_note} "
            f"FX options priced using Garman-Kohlhagen (Black-Scholes with two risk-free rates). "
            f"Forward rate: F = S·e^((r_d - r_f)·T) — rate differentials drive currency forwards."
        )

    # ── Credit Proxy ───────────────────────────────────────────────────────────
    lqd_chg = md.get('lqd_chg', 0)
    hyg_chg = md.get('hyg_chg', 0)
    if lqd_chg != 0 or hyg_chg != 0:
        spread_signal = hyg_chg - lqd_chg
        if spread_signal < -0.3:
            credit_note = (
                f"HYG (high yield) is underperforming LQD (investment grade) by {abs(spread_signal):.2f}% — "
                f"credit spreads widening. Market pricing more default risk on junk bonds. "
                f"Watch CDS spreads for confirmation of credit stress."
            )
        elif spread_signal > 0.3:
            credit_note = (
                f"HYG outperforming LQD — credit spreads tightening. "
                f"Investors comfortable reaching for yield, a risk-on signal in credit markets."
            )
        else:
            credit_note = (
                f"LQD ({lqd_chg:+.2f}%) and HYG ({hyg_chg:+.2f}%) moving together — "
                f"no stress signal from credit markets today."
            )
        sections.append(
            f"**Credit Markets (proxy)** — {credit_note} "
            f"Credit spread = corporate yield − Treasury yield (same maturity). "
            f"Widening spreads = rising default risk = risk-off signal. "
            f"Altman Z-score: Z = 1.2X₁ + 1.4X₂ + 3.3X₃ + 0.6X₄ + 0.999X₅ — below 1.8 = distress zone."
        )

    # ── BTC ────────────────────────────────────────────────────────────────────
    btc_context = f"**Bitcoin at ${btc_price:,.0f}** ({btc_chg:+.2f}% today) — "
    if abs(btc_chg - ndq_chg) < 1.0:
        btc_context += "Tracking the Nasdaq closely — typical risk-on correlation intact."
    elif btc_chg > ndq_chg + 1.5:
        btc_context += "Outperforming Nasdaq — crypto-specific buying (ETF flows, regulatory news, or 'digital gold' demand)."
    elif btc_chg < ndq_chg - 1.5:
        btc_context += "Lagging Nasdaq — crypto-specific selling. Watch for regulatory headlines."
    else:
        btc_context += "Moving roughly in line with broader risk assets."
    sections.append(btc_context)

    # ── Big picture ────────────────────────────────────────────────────────────
    if sp_chg > 0 and ndq_chg > 0 and yield_chg <= 0 and vix_val < 20:
        summary = (
            "**Big picture today:** Clean risk-on — equities up, yields down, VIX calm. "
            "Ideal combo for growth stocks. No macro alarm bells."
        )
    elif sp_chg > 0 and vix_chg > 1:
        summary = (
            f"**Big picture today:** Stocks rising but VIX is also up ({vix_val:.1f}) — "
            "unusual combo that can signal hedging activity. Investors buying stocks *and* buying protection."
        )
    elif sp_chg < 0 and gold_chg > 0:
        summary = (
            "**Big picture today:** Risk-off — stocks falling, gold rising. Classic flight to safety. "
            "Watch for the catalyst: macro data, Fed speaker, or geopolitical news."
        )
    elif spread < 0:
        summary = (
            f"**Big picture today:** Inverted yield curve ({spread:+.3f}%) is the headline macro risk. "
            "Historically the single most reliable recession warning signal. Watch Fed commentary carefully."
        )
    elif sp_chg > 0 and gold_chg > 0:
        summary = (
            "**Big picture today:** Liquidity-driven — both stocks and gold up. "
            "Signals ample liquidity rather than pure optimism. Keep watching."
        )
    else:
        summary = (
            f"**Big picture today:** Mixed signals — S&P ({sp_chg:+.2f}%), VIX ({vix_val:.1f}), "
            f"Spread ({spread:+.3f}%). No dominant theme; market may be waiting on a catalyst."
        )
    sections.append(summary)

    return sections

# ── Say This Today ─────────────────────────────────────────────────────────────

def say_this_today(md):
    if not md:
        return "> *Could not generate talking point — refresh data and try again.*"
    try:
        sp_chg, ndq_chg = md['sp_chg'], md['ndq_chg']
        gold_chg, oil_chg = md['gold_chg'], md['oil_chg']
        yield_10y, vix_val, spread = md['yield_10y'], md['vix_val'], md['spread']

        if ndq_chg > sp_chg + 0.5:
            equity_take = f"markets are risk-on today with tech leading — Nasdaq up {ndq_chg:+.2f}%"
        elif sp_chg > ndq_chg + 0.5:
            equity_take = f"we're seeing a value rotation — S&P up {sp_chg:+.2f}% but Nasdaq lagging"
        elif sp_chg > 0:
            equity_take = f"it's a broad-based rally — S&P up {sp_chg:+.2f}%"
        else:
            equity_take = f"markets are pulling back — S&P {sp_chg:+.2f}%"

        if spread < 0:
            rate_take = f"the yield curve is inverted ({spread:+.3f}%), which historically signals recession risk"
        elif vix_val > 25:
            rate_take = f"VIX is elevated at {vix_val:.1f}, showing real fear in options markets"
        elif oil_chg < -2:
            rate_take = f"oil is down {oil_chg:.1f}% which takes pressure off inflation and gives the Fed more room to cut"
        elif gold_chg > 1:
            rate_take = f"gold is up {gold_chg:+.2f}%, reflecting sustained macro uncertainty"
        else:
            rate_take = f"the 10-year Treasury is at {yield_10y:.2f}% with rates holding steady"

        return (
            f"> \"So {equity_take}. The interesting thing is {rate_take} — "
            f"something I'm watching closely given how much it affects options pricing and valuation.\""
        )
    except:
        return "> *Could not generate talking point — refresh data and try again.*"

# ── News → Quant Angle (dynamic, per headline) ─────────────────────────────────

def classify_headline(headline, md):
    h = headline.lower()

    if any(w in h for w in ['earnings', 'eps', 'q1', 'q2', 'q3', 'q4', 'revenue', 'beat', 'miss', 'results', 'guidance', 'profit', 'quarterly']):
        vix_note = f"VIX at {md['vix_val']:.1f} — {'options cheap, straddles affordable pre-event' if md['vix_val'] < 20 else 'IV already elevated, straddles expensive'}."
        return (
            f"→ *Earnings event* — classic IV expansion before announcement, vol crush after.\n"
            f"  Straddle breakeven = strike ± (call + put premium); profitable if move exceeds breakeven.\n"
            f"  Factor decomposition: R = α + β·R_market + ε — big beat = high idiosyncratic α.\n"
            f"  {vix_note}"
        )

    if any(w in h for w in ['fed', 'fomc', 'rate cut', 'rate hike', 'inflation', 'cpi', 'pce', 'powell', 'basis point', 'interest rate']):
        direction = "falling" if md['yield_chg'] < 0 else "rising"
        curve_note = "no recession signal" if md['spread'] > 0 else "⚠️ inverted — recession signal active"
        return (
            f"→ *Rate/Fed event* — 10Y at {md['yield_10y']:.3f}% and {direction} today ({md['yield_chg']:+.1f} bps).\n"
            f"  Bond price change ≈ -D·Δy + ½·Convexity·(Δy)² — duration risk is the key metric.\n"
            f"  Growth stocks most sensitive: higher discount rate → lower NPV of future cash flows.\n"
            f"  Yield curve spread: {md['spread']:+.3f}% ({curve_note})."
        )

    if any(w in h for w in ['acqui', 'merger', 'deal', 'buyout', 'takeover', 'combine']):
        return (
            f"→ *M&A event* — target stock typically spikes toward deal price on announcement.\n"
            f"  Merger arbitrage: buy target, short acquirer; profit = spread if deal closes.\n"
            f"  IV on target collapses post-announcement (deal price acts as ceiling).\n"
            f"  Risk: deal falls through → sharp drop; size position using CVaR = E[loss | loss > VaR]."
        )

    if any(w in h for w in ['sec', 'lawsuit', 'antitrust', 'regulation', 'fine', 'penalty', 'trial', 'court', 'sued', 'ftc', 'doj']):
        return (
            f"→ *Regulatory/legal risk* — hard to price linearly; shows up in options put skew.\n"
            f"  Elevated put premiums on affected names = market pricing unresolved downside tail.\n"
            f"  Credit lens: Altman Z-score Z = 1.2X₁ + 1.4X₂ + 3.3X₃ + 0.6X₄ + 0.999X₅.\n"
            f"  VaR widens when σ rises from uncertainty: VaR = σ·Z_α·√h·P — recalculate exposure."
        )

    if any(w in h for w in ['oil', 'crude', 'wti', 'brent', 'opec', 'pipeline', 'refin', 'hormuz', 'energy supply']):
        curve_type = "backwardation (supply tight, front month premium)" if md['oil_chg'] > 1 else "contango pressure (supply easing)"
        return (
            f"→ *Oil/energy* — WTI at ${md['oil_price']:.2f} ({md['oil_chg']:+.2f}% today).\n"
            f"  Futures pricing: Ft = St·e^((r+d)·T) — spot move shifts entire futures curve.\n"
            f"  Curve structure: {curve_type}.\n"
            f"  Inflation channel: oil → CPI → Fed policy → rates → equity valuations."
        )

    if any(w in h for w in ['gold', 'silver', 'platinum', 'precious metal', 'safe-haven', 'haven']):
        if md['gold_chg'] > 0 and md['sp_chg'] > 0:
            corr = "positive today (liquidity-driven, not fear)"
        elif md['gold_chg'] > 0 and md['sp_chg'] < 0:
            corr = "negative today (flight to safety — classic)"
        else:
            corr = "mixed"
        return (
            f"→ *Precious metals* — Gold at ${md['gold_price']:,.0f} ({md['gold_chg']:+.2f}% today).\n"
            f"  Gold-equity correlation: {corr}.\n"
            f"  Cost of carry: Ft = St·e^(r·T) (storage ~offset by lease rate, minimal carry cost).\n"
            f"  Gold vs. VIX: VIX at {md['vix_val']:.1f} — {'fear confirmed' if md['vix_val'] > 20 and md['gold_chg'] > 0 else 'no panic signal yet'}."
        )

    if any(w in h for w in ['ai', 'artificial intelligence', 'chip', 'semiconductor', 'gpu', 'nvidia', 'data center', 'llm']):
        return (
            f"→ *AI/tech theme* — factor model: R_i = α + β_market·R_m + β_tech·R_XLK + ε.\n"
            f"  High tech beta day — sector factor dominant; individual stock-picking less rewarded.\n"
            f"  AI capex boom → rising depreciation → watch forward earnings estimate revisions.\n"
            f"  NLP signal risk: AI-written corporate language degrades sentiment-based alpha models."
        )

    if any(w in h for w in ['bitcoin', 'crypto', 'btc', 'ethereum', 'blockchain', 'digital asset']):
        spread_btc = md['btc_chg'] - md['ndq_chg']
        signal = "decoupling — crypto-specific driver" if abs(spread_btc) > 1.5 else "tracking equities normally"
        return (
            f"→ *Crypto* — BTC at ${md['btc_price']:,.0f} ({md['btc_chg']:+.2f}% today).\n"
            f"  BTC vs Nasdaq spread: {spread_btc:+.2f}% ({signal}).\n"
            f"  Options pricing: Black-Scholes applies but σ is extreme (often 60-100%+ annualized).\n"
            f"  VIX at {md['vix_val']:.1f} — cross-asset vol environment {'calm' if md['vix_val'] < 20 else 'elevated'}."
        )

    if any(w in h for w in ['dividend', 'buyback', 'share repurchase', 'payout', 'distribution', 'yield']):
        competitive = "competitive vs. bonds" if md['yield_10y'] < 4.5 else "less competitive — bonds offer similar yield"
        return (
            f"→ *Income/value event* — dividend yield vs. risk-free rate comparison key.\n"
            f"  10Y at {md['yield_10y']:.3f}% — dividend stocks {competitive}.\n"
            f"  Gordon Growth Model: P = D/(r-g) — rate changes directly affect intrinsic value.\n"
            f"  Buybacks reduce float → EPS accretion; shows as idiosyncratic α in factor model."
        )

    if any(w in h for w in ['ipo', 'public offering', 'debut', 'listing', 'went public']):
        return (
            f"→ *IPO event* — well-documented underpricing: avg first-day pop ~15-20%.\n"
            f"  Banks price conservatively to reward institutional clients; retail gets after-market price.\n"
            f"  Post-IPO vol is very high — IV elevated, options expensive in first 30 days.\n"
            f"  No historical beta available — estimate from comparable public company betas."
        )

    if any(w in h for w in ['gdp', 'recession', 'economic growth', 'slowdown', 'contraction', 'expansion']):
        curve_note = f"spread {md['spread']:+.3f}% — {'no inversion' if md['spread'] > 0 else '⚠️ inverted'}"
        return (
            f"→ *Macro/growth signal* — yield curve is the primary recession predictor ({curve_note}).\n"
            f"  VaR = σ·Z_α·√h·P — recession risk widens σ across all assets; recalculate.\n"
            f"  Stress test: apply 2008-style GDP shock to portfolio; Monte Carlo across growth scenarios.\n"
            f"  GARCH(1,1): σ²_t = ω + α·ε²_(t-1) + β·σ²_(t-1) — vol tends to persist in downturns."
        )

    if any(w in h for w in ['dollar', 'dxy', 'currency', 'forex', 'fx', 'yen', 'euro', 'pound', 'exchange rate', 'tariff', 'trade']):
        direction = "weak — commodity tailwind, EM inflows" if md['dxy_val'] < 100 else "strong — commodity headwind, EM pressure"
        return (
            f"→ *FX/macro event* — DXY at {md['dxy_val']:.2f} ({md['dxy_chg']:+.2f}%), dollar {direction}.\n"
            f"  FX forward: F = S·e^((r_d - r_f)·T) — interest rate differential drives forward prices.\n"
            f"  Currency options: Garman-Kohlhagen (Black-Scholes with two risk-free rates).\n"
            f"  Tariff/trade news → supply chain cost shock → margin compression → earnings risk."
        )

    # Default
    return (
        f"→ *General market story* — monitor for factor exposure changes.\n"
        f"  Baseline: VIX {md['vix_val']:.1f}, spread {md['spread']:+.3f}%, 10Y {md['yield_10y']:.3f}%.\n"
        f"  Apply VaR = σ·Z_α·√h·P if sizing decisions involved."
    )


def analyze_news_quant_angles(yahoo_headlines, brew_headlines, md):
    if not md:
        return "*Market data unavailable — cannot generate quant angles.*"

    # Analyze Yahoo headlines (most finance-relevant); skip generic Brew headlines
    relevant = yahoo_headlines[:5]
    if not relevant:
        return "*No headlines fetched to analyze.*"

    entries = []
    for h in relevant:
        angle = classify_headline(h, md)
        entries.append(f"**\"{h}\"**\n{angle}")

    return "\n\n".join(entries)

# ── Quant/Finance Lens (dynamic) ───────────────────────────────────────────────

def generate_quant_lens(md):
    if not md:
        return "- *Market data unavailable.*"

    lines = []

    # VIX signal
    if md['vix_val'] < 15:
        lines.append(f"- **VIX {md['vix_val']:.1f} (very low)**: options premiums compressed — σ input in Black-Scholes is at the low end; cheap to buy protection right now")
    elif md['vix_val'] < 20:
        lines.append(f"- **VIX {md['vix_val']:.1f} (normal)**: options fairly priced — no vol dislocation; straddles priced at fair value")
    elif md['vix_val'] < 30:
        lines.append(f"- **VIX {md['vix_val']:.1f} (elevated)**: options expensive — implied vol (σ in Black-Scholes) rising; options sellers collecting larger premium")
    else:
        lines.append(f"- **VIX {md['vix_val']:.1f} (HIGH — fear regime)**: vol crush potential when fear resolves; delta-hedging costs elevated; models stress-tested")

    # Yield curve signal
    if md['spread'] < 0:
        lines.append(f"- **Yield curve INVERTED ({md['spread']:+.3f}%)**: historically predicts recession within 6-18 months — most important macro signal right now; duration risk elevated")
    elif md['spread'] < 0.3:
        lines.append(f"- **Yield curve flattening ({md['spread']:+.3f}%)**: watch closely — flattening before inversion is the warning stage; floating-rate instruments outperform")
    else:
        lines.append(f"- **Yield curve healthy ({md['spread']:+.3f}%)**: normal upward slope — no recession signal; bond price change ≈ -D·Δy + ½·Convexity·(Δy)²")

    # DXY signal
    if md['dxy_val'] < 100:
        lines.append(f"- **DXY {md['dxy_val']:.2f} (weak dollar)**: commodity tailwind active — gold and oil priced in USD, so weak dollar supports prices; EM capital inflows likely")
    elif md['dxy_val'] > 105:
        lines.append(f"- **DXY {md['dxy_val']:.2f} (strong dollar)**: headwind for commodities and US multinational earnings; hedge FX exposure with forwards: F = S·e^((r_d-r_f)·T)")
    else:
        lines.append(f"- **DXY {md['dxy_val']:.2f} (neutral)**: dollar not a dominant factor today — watch direction more than absolute level")

    # Rate signal
    if abs(md['yield_chg']) > 5:
        direction = "drop" if md['yield_chg'] < 0 else "spike"
        lines.append(f"- **Rates moved {md['yield_chg']:+.1f} bps today**: significant {direction} — reprices all duration-sensitive assets; tech/growth most affected via DCF discount rate")
    else:
        lines.append(f"- **10Y at {md['yield_10y']:.3f}%**: {'moderate — risk-free baseline stable today' if 4.0 <= md['yield_10y'] <= 4.5 else 'watch level closely — affects NPV of all future cash flows'}")

    # Dominant regime signal
    if md['sp_chg'] > 0 and md['vix_chg'] < 0:
        lines.append(f"- **Regime: risk-on** — equities up, VIX down; momentum factor likely outperforming; GARCH vol forecast low → VaR estimates tight")
    elif md['sp_chg'] < 0 and md['vix_chg'] > 0:
        lines.append(f"- **Regime: risk-off** — equities down, VIX up; run Monte Carlo stress test; protective puts on S&P reduce portfolio VaR = σ·Z_α·√h·P")
    elif md['gold_chg'] > 1 and md['sp_chg'] > 0:
        lines.append(f"- **Regime: liquidity-driven** — both gold and equities rising; not a fear signal; watch for vol spike if liquidity drains suddenly")

    # Credit signal
    hyg, lqd = md.get('hyg_chg', 0), md.get('lqd_chg', 0)
    if hyg < lqd - 0.4:
        lines.append(f"- **Credit stress signal**: HYG underperforming LQD by {abs(hyg-lqd):.2f}% — high-yield spreads widening; recalculate VaR = σ·Z_α·√h·P with higher σ")
    else:
        lines.append(f"- **Credit stable**: HYG ({hyg:+.2f}%) and LQD ({lqd:+.2f}%) aligned — no spread widening; Altman Z-score monitoring not triggered")

    # Copper regime
    copper_chg = md.get('copper_chg', 0)
    if copper_chg > 1.0:
        lines.append(f"- **Dr. Copper bullish ({copper_chg:+.2f}%)**: global growth signal positive; factor model → cyclical sectors (XLI, XLB, XLY) should outperform")
    elif copper_chg < -1.0:
        lines.append(f"- **Dr. Copper bearish ({copper_chg:+.2f}%)**: industrial demand falling; China slowdown risk; defensives (XLU, XLP) likely to outperform")

    return "\n".join(lines)

# ── To Watch (dynamic) ─────────────────────────────────────────────────────────

def generate_to_watch(md):
    if not md:
        return "- *Market data unavailable.*"

    bullets = []
    today = date.today()

    # FOMC proximity check
    upcoming_fomc = [d for d in FOMC_DATES_2026 if (d - today).days >= 0]
    if upcoming_fomc:
        days_to_fomc = (upcoming_fomc[0] - today).days
        fomc_str = upcoming_fomc[0].strftime("%b %d")
        if days_to_fomc <= 14:
            bullets.append(f"- **⚠️ FOMC in {days_to_fomc} days ({fomc_str})** — Fed rate decision imminent; any surprise = major vol event; current rate 4.25–4.50%")
        else:
            bullets.append(f"- **FOMC on {fomc_str}** ({days_to_fomc} days away) — Fed funds at 4.25–4.50%; watch for early signals in Fed speaker commentary")

    # Yield curve watch
    if md['spread'] < 0:
        bullets.append(f"- **⚠️ Inverted curve ({md['spread']:+.3f}%)** — active recession signal; watch for steepening as the key reversal sign")
    elif md['spread'] < 0.3:
        bullets.append(f"- **Yield curve flattening ({md['spread']:+.3f}%)** — approaching danger zone; inversion below 0% = recession signal triggered")
    else:
        bullets.append(f"- **Yield curve spread {md['spread']:+.3f}%** — healthy; watch for narrowing as early warning of regime change")

    # VIX watch
    if md['vix_val'] > 25:
        bullets.append(f"- **⚠️ VIX elevated at {md['vix_val']:.1f}** — fear regime active; options expensive; consider protective puts or vol-selling strategies")
    elif md['vix_chg'] > 1.5:
        bullets.append(f"- **VIX rising ({md['vix_val']:.1f}, +{md['vix_chg']:.1f} pts today)** — fear building; watch for sustained break above 20; σ in Black-Scholes rising")
    else:
        bullets.append(f"- **VIX calm at {md['vix_val']:.1f}** — complacency can reverse fast; watch for spike above 20 as first warning")

    # Oil / geopolitical
    if md['oil_chg'] > 2:
        bullets.append(f"- **⚠️ Oil spiking (${md['oil_price']:.2f}, {md['oil_chg']:+.2f}%)** — inflation risk rising; watch Fed response; supply chain disruption likely geopolitical")
    elif md['oil_chg'] < -2:
        bullets.append(f"- **Oil falling (${md['oil_price']:.2f}, {md['oil_chg']:+.2f}%)** — inflation pressure easing; positive for Fed flexibility; energy stocks (XLE) under pressure")
    else:
        bullets.append(f"- **Oil at ${md['oil_price']:.2f}** — stable today; watch Strait of Hormuz/OPEC headlines for supply shock triggers")

    # Earnings season flag (Q1 earnings: roughly Apr-May)
    if today.month in [4, 5]:
        bullets.append(f"- **Q1 earnings season** — large single-day moves create options opportunities; watch implied vol before key reports (MSFT, GOOGL, META, AMZN all reporting)")

    # Gold / macro anxiety
    if md['gold_price'] > 4000:
        bullets.append(f"- **Gold at ${md['gold_price']:,.0f}** — historically extreme level (norm: $1,800–2,000); sustained elevation signals macro anxiety; watch gold-equity correlation")

    # DXY watch
    if abs(md['dxy_chg']) > 0.5:
        direction = "weakening" if md['dxy_chg'] < 0 else "strengthening"
        bullets.append(f"- **Dollar {direction} (DXY {md['dxy_val']:.2f}, {md['dxy_chg']:+.2f}%)** — {'commodity tailwind, EM inflows' if md['dxy_chg'] < 0 else 'commodity headwind, multinational earnings pressure'}")

    # USD/JPY BOJ watch
    usdjpy = md.get('usdjpy', 0)
    if usdjpy > 155:
        bullets.append(f"- **⚠️ USD/JPY at {usdjpy:.2f}** — BOJ intervention zone; yen weakness = carry trade risk; watch BOJ statements closely")
    elif usdjpy > 150:
        bullets.append(f"- **USD/JPY {usdjpy:.2f}** — approaching BOJ sensitivity level (~155); monitor for jawboning")

    # Copper / growth watch
    copper_chg = md.get('copper_chg', 0)
    copper_price = md.get('copper_price', 0)
    if abs(copper_chg) > 1.5:
        direction = "rising" if copper_chg > 0 else "falling"
        bullets.append(f"- **Copper {direction} sharply ({copper_chg:+.2f}%)** — 'Dr. Copper' growth signal; {'bullish global demand, AI infra buildout' if copper_chg > 0 else 'global slowdown warning, watch China PMI'}")

    # Credit watch
    hyg, lqd = md.get('hyg_chg', 0), md.get('lqd_chg', 0)
    if hyg < lqd - 0.5:
        bullets.append(f"- **⚠️ Credit spreads widening** (HYG {hyg:+.2f}% vs LQD {lqd:+.2f}%) — high yield underperforming IG; potential risk-off signal; watch CDS markets")

    return "\n".join(bullets)

# ── Write briefing ─────────────────────────────────────────────────────────────

def write_briefing():
    now = datetime.now().strftime("%B %d, %Y — %I:%M %p CT")

    print("Fetching market data...")
    md = fetch_market_data()

    print("Fetching YTD changes...")
    ytd_changes = fetch_ytd_changes()

    print("Fetching price table...")
    price_rows = fetch_prices(ytd_changes)

    print("Fetching extended markets...")
    extended_rows = fetch_extended_prices(md, ytd_changes)

    print("Building regime box...")
    regime_box = generate_regime_box(md)

    print("Fetching sector data...")
    sector_rows = fetch_sectors(ytd_changes)

    print("Fetching Yahoo Finance news...")
    yahoo_news = fetch_yahoo_news()

    print("Fetching Morning Brew news...")
    brew_news = fetch_morning_brew_news()

    print("Building macro read...")
    macro = macro_read(md)

    print("Building talking point...")
    talking_pt = say_this_today(md)

    print("Analyzing headlines...")
    news_quant = analyze_news_quant_angles(yahoo_news, brew_news, md)

    print("Building quant lens...")
    quant_lens = generate_quant_lens(md)

    print("Building to watch...")
    to_watch = generate_to_watch(md)

    price_table    = "\n".join(price_rows)
    extended_table = "\n".join(extended_rows) if extended_rows else ""
    sector_table   = "\n".join(sector_rows)
    macro_section  = "\n\n".join(macro)

    yahoo_section = (
        "### Yahoo Finance\n" + "\n".join(f"{i+1}. {h}" for i, h in enumerate(yahoo_news))
        if yahoo_news else "### Yahoo Finance\n*Could not fetch headlines.*"
    )
    brew_section = (
        "### Morning Brew\n" + "\n".join(f"{i+1}. {h}" for i, h in enumerate(brew_news))
        if brew_news else "### Morning Brew\n*Could not fetch headlines — site may require login.*"
    )

    content = f"""# Daily Market Briefing
**Last updated:** {now}
> Run `python3 ~/Claude/update_market_briefing.py` to refresh

---

## Say This Today
*Drop this into any interview or networking conversation:*

{talking_pt}

---

## Market Regime

{regime_box}

---

## Markets At a Glance

| Asset | Price | Change | YTD |
|---|---|---|---|
{price_table}

---

## Extended Markets

| Asset | Price | Change | YTD |
|---|---|---|---|
{extended_table}

---

## Sector Breakdown

| Sector | ETF | Change | YTD |
|---|---|---|---|
{sector_table}

---

## Macro Read

{macro_section}

---

## Top Stories

{yahoo_section}

{brew_section}

---

## News → Quant Angle

{news_quant}

---

## Quant/Finance Lens

{quant_lens}

---

## To Watch

{to_watch}

---
*Sources: Yahoo Finance (yfinance API), Morning Brew. Auto-updated via ~/Claude/update_market_briefing.py*
"""

    repo_root = Path(__file__).parent.parent
    output_path = repo_root / "assets" / "market_briefing.md"
    with open(output_path, "w") as f:
        f.write(content)
    print(f"✅ Market briefing updated: {output_path}")

if __name__ == "__main__":
    write_briefing()
