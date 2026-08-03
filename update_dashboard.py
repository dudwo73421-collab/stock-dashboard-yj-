# -*- coding: utf-8 -*-
"""
대시보드 보조 지표 자동 갱신 스크립트 (GitHub Actions에서 매일 실행됨)

index.html 안의 <!--SUPP:섹션:START--> ~ <!--SUPP:섹션:END--> 사이를
야후 파이낸스 일봉 데이터로 계산한 최신 값으로 갈아끼운다.

계산 지표:
  일간      : 직전 거래일 종가 대비 현재 종가
  고점대비  : 최근 52주(252거래일) 고가 종가 대비 현재 종가
  주간      : 5거래일 전 종가 대비
  26년 YTD  : 전년도 마지막 종가 대비
  연속      : 연속 상승/하락 일수
  RSI(14)   : Wilder 방식

또 <!--FNG:START--> ~ <!--FNG:END--> 사이에 공포·탐욕 지수 두 개를 갈아끼운다.
  미국 주식 : CNN Fear & Greed Index
  암호화폐  : alternative.me Crypto Fear & Greed Index
둘 중 하나만 실패해도 그쪽만 "확인 필요"로 표시하고 나머지는 정상 표기한다.

가격은 액면분할·배당이 보정된 수정주가(auto_adjust=True)를 쓴다.
날짜 표기는 한국시간 기준이다.
데이터를 못 받아온 종목은 값을 지어내지 않고 "확인 필요"로 표기한다.
"""
import sys
import json
import re
import datetime
import math
import urllib.request

import pandas as pd
import yfinance as yf

KST = datetime.timezone(datetime.timedelta(hours=9))

# (표시이름, 티커라벨, 로고도메인 또는 None, 야후심볼, 기술등급 계산 여부)
SECTIONS = {
    "us30": [
        ("엔비디아", "NVDA", "nvidia.com", "NVDA", True),
        ("애플", "AAPL", "apple.com", "AAPL", True),
        ("알파벳", "GOOGL", "abc.xyz", "GOOGL", True),
        ("마이크로소프트", "MSFT", "microsoft.com", "MSFT", True),
        ("아마존", "AMZN", "amazon.com", "AMZN", True),
        ("TSMC", "TSM", "tsmc.com", "TSM", True),
        ("브로드컴", "AVGO", "broadcom.com", "AVGO", True),
        ("스페이스X", "SPCX", "spacex.com", "SPCX", True),
        ("메타", "META", "meta.com", "META", True),
        ("테슬라", "TSLA", "tesla.com", "TSLA", True),
        ("버크셔해서웨이", "BRK.B", "berkshirehathaway.com", "BRK-B", True),
        ("일라이릴리", "LLY", "lilly.com", "LLY", True),
        ("마이크론", "MU", "micron.com", "MU", True),
        ("JP모건", "JPM", "jpmorganchase.com", "JPM", True),
        ("월마트", "WMT", "walmart.com", "WMT", True),
        ("AMD", "AMD", "amd.com", "AMD", True),
        ("ASML", "ASML", "asml.com", "ASML", True),
        ("비자", "V", "visa.com", "V", True),
        ("엑슨모빌", "XOM", "exxonmobil.com", "XOM", True),
        ("존슨앤존슨", "JNJ", "jnj.com", "JNJ", True),
        ("마스터카드", "MA", "mastercard.com", "MA", True),
        ("인텔", "INTC", "intel.com", "INTC", True),
        ("애브비", "ABBV", "abbvie.com", "ABBV", True),
        ("시스코", "CSCO", "cisco.com", "CSCO", True),
        ("뱅크오브아메리카", "BAC", "bankofamerica.com", "BAC", True),
        ("어플라이드머티리얼즈", "AMAT", "appliedmaterials.com", "AMAT", True),
        ("코스트코", "COST", "costco.com", "COST", True),
        ("캐터필러", "CAT", "caterpillar.com", "CAT", True),
        ("쉐브론", "CVX", "chevron.com", "CVX", True),
        ("유나이티드헬스", "UNH", "unitedhealthgroup.com", "UNH", True),
        ("램리서치", "LRCX", "lamresearch.com", "LRCX", True),
        ("GE에어로스페이스", "GE", "geaerospace.com", "GE", True),
        ("HSBC", "HSBC", "hsbc.com", "HSBC", True),
        ("코카콜라", "KO", "coca-colacompany.com", "KO", True),
        ("P&amp;G", "PG", "pg.com", "PG", True),
        ("모건스탠리", "MS", "morganstanley.com", "MS", True),
        ("홈디포", "HD", "homedepot.com", "HD", True),
        ("오라클", "ORCL", "oracle.com", "ORCL", True),
        ("골드만삭스", "GS", "goldmansachs.com", "GS", True),
        ("머크", "MRK", "merck.com", "MRK", True),
        ("필립모리스", "PM", "pmi.com", "PM", True),
        ("노바티스", "NVS", "novartis.com", "NVS", True),
        ("팔란티어", "PLTR", "palantir.com", "PLTR", True),
        ("넷플릭스", "NFLX", "netflix.com", "NFLX", True),
        ("로열뱅크오브캐나다", "RY", "rbc.com", "RY", True),
        ("RTX", "RTX", "rtx.com", "RTX", True),
        ("델테크놀로지스", "DELL", "dell.com", "DELL", True),
        ("ARM", "ARM", "arm.com", "ARM", True),
        ("KLA", "KLAC", "kla.com", "KLAC", True),
        ("GE버노바", "GEV", "gevernova.com", "GEV", True),
    ],
    "kr10": [
        ("삼성전자", "005930", "samsung.com", "005930.KS", True),
        ("SK하이닉스", "000660", "skhynix.com", "000660.KS", True),
        ("SK스퀘어", "402340", "sksquare.com", "402340.KS", True),
        ("현대차", "005380", "hyundai.com", "005380.KS", True),
        ("삼성전기", "009150", "samsungsem.com", "009150.KS", True),
        ("LG에너지솔루션", "373220", "lgensol.com", "373220.KS", True),
        ("삼성바이오로직스", "207940", "samsungbiologics.com", "207940.KS", True),
        ("KB금융", "105560", "kbfg.com", "105560.KS", True),
        ("삼성생명", "032830", "samsunglife.com", "032830.KS", True),
        ("삼성물산", "028260", "samsungcnt.com", "028260.KS", True),
        ("기아", "000270", "kia.com", "000270.KS", True),
        ("HD현대중공업", "329180", "hd.com", "329180.KS", True),
        ("신한지주", "055550", "shinhangroup.com", "055550.KS", True),
        ("한화에어로스페이스", "012450", "hanwhaaerospace.com", "012450.KS", True),
        ("현대모비스", "012330", "mobis.co.kr", "012330.KS", True),
        ("두산에너빌리티", "034020", "doosanenerbility.com", "034020.KS", True),
        ("셀트리온", "068270", "celltrion.com", "068270.KS", True),
        ("SK", "034730", "sk.com", "034730.KS", True),
        ("하나금융지주", "086790", "hanafn.com", "086790.KS", True),
        ("네이버", "035420", "navercorp.com", "035420.KS", True),
    ],
    # 같은 지수를 따라가는 ETF는 대표 하나만 남기고 나머지는 그 옆에 작게 병기한다.
    # (IVV·SPY는 VOO와 같은 S&P500, VUG는 QQQ와 보유 종목이 크게 겹친다)
    "etf": [
        ("VOO", 'VOO<span class="supp-dupe">동일 IVV·SPY</span>', "vanguard.com", "VOO", True),
        ("VTI", "VTI", "vanguard.com", "VTI", True),
        ("QQQ", 'QQQ<span class="supp-dupe">유사 VUG</span>', "invesco.com", "QQQ", True),
        ("VEA", "VEA", "vanguard.com", "VEA", True),
        ("IEFA", "IEFA", "ishares.com", "IEFA", True),
        ("VTV", "VTV", "vanguard.com", "VTV", True),
        ("BND", "BND", "vanguard.com", "BND", True),
        ("XLK", "XLK", "ssga.com", "XLK", True),
        ("XLF", "XLF", "ssga.com", "XLF", True),
        ("XLV", "XLV", "ssga.com", "XLV", True),
        ("XLY", "XLY", "ssga.com", "XLY", True),
        ("XLP", "XLP", "ssga.com", "XLP", True),
        ("XLE", "XLE", "ssga.com", "XLE", True),
        ("XLI", "XLI", "ssga.com", "XLI", True),
        ("XLB", "XLB", "ssga.com", "XLB", True),
        ("XLU", "XLU", "ssga.com", "XLU", True),
    ],
    "macro": [
        ("VIX", "VIX", None, "^VIX", False),
        ("美10년물", "US10Y", None, "^TNX", False),
        ("美2년물", "US02Y", None, "2YY=F", False),
        ("달러인덱스", "DXY", None, "DX-Y.NYB", False),
        ("WTI 원유", "USOIL", None, "CL=F", True),
        ("금", "GOLD", None, "GC=F", True),
        ("비트코인", "BTC", "bitcoin.org", "BTC-USD", True),
        ("원달러 환율", "USDKRW", None, "KRW=X", True),
    ],
}

RATING_LABEL = {4: ("Strong Buy", "up"), 3: ("Buy", "up"), 2: ("Neutral", "needchk"),
                1: ("Sell", "down"), 0: ("Strong Sell", "down")}


def rsi14(close: pd.Series) -> float:
    delta = close.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.ewm(alpha=1 / 14, min_periods=14).mean()
    avg_loss = loss.ewm(alpha=1 / 14, min_periods=14).mean()
    rs = avg_gain / avg_loss
    val = 100 - (100 / (1 + rs))
    return float(val.iloc[-1])


def compute(close: pd.Series, rate: bool):
    close = close.dropna()
    if len(close) < 30:
        raise ValueError("not enough data")
    last = float(close.iloc[-1])

    day = (last / float(close.iloc[-2]) - 1) * 100 if len(close) >= 2 else None

    high52 = float(close.tail(252).max())
    drawdown = (last / high52 - 1) * 100

    week = (last / float(close.iloc[-6]) - 1) * 100 if len(close) >= 6 else None

    this_year = close.index[-1].year
    prev = close[close.index.year < this_year]
    ytd = (last / float(prev.iloc[-1]) - 1) * 100 if len(prev) else None

    # 연속 상승/하락
    diffs = close.diff().dropna()
    streak, direction = 0, 0
    for d in reversed(diffs.tolist()):
        s = 1 if d > 0 else (-1 if d < 0 else 0)
        if streak == 0:
            if s == 0:
                break
            direction, streak = s, 1
        elif s == direction:
            streak += 1
        else:
            break

    rsi = rsi14(close)

    rating = None
    if rate and len(close) >= 200:
        ma20 = float(close.tail(20).mean())
        ma50 = float(close.tail(50).mean())
        ma200 = float(close.tail(200).mean())
        score = int(last > ma20) + int(last > ma50) + int(last > ma200) + int(ma50 > ma200)
        rating = RATING_LABEL[score]
    return day, drawdown, week, ytd, (streak, direction), rsi


def pct_cell(v):
    if v is None or (isinstance(v, float) and math.isnan(v)):
        return '<td class="needchk">확인 필요</td>'
    cls = "up" if v > 0 else ("down" if v < 0 else "needchk")
    return f'<td class="{cls}">{v:+.2f}%</td>'


def streak_cell(sd):
    streak, direction = sd
    if streak == 0:
        return '<td class="needchk">보합</td>'
    if direction > 0:
        return f'<td class="up">{streak}일 상승</td>'
    return f'<td class="down">{streak}일 하락</td>'


def make_row(name, label, logo, sym, rate, closes):
    logo_html = (f'<img class="supp-logo" src="https://logo.clearbit.com/{logo}" '
                 f"onerror=\"this.style.display='none'\">") if logo else ""
    name_td = f'<td>{logo_html}{name}<span class="supp-ticker">{label}</span></td>'
    try:
        close = closes[sym]
        day, drawdown, week, ytd, sd, rsi = compute(close, rate)
        day_cell = pct_cell(day)
        dd_cell = pct_cell(drawdown)
        wk_cell = pct_cell(week)
        ytd_cell = pct_cell(ytd)
        st_cell = streak_cell(sd)
        rsi_cell = f"<td>{rsi:.1f}</td>"
        return (f"          <tr>{name_td}{day_cell}{dd_cell}{wk_cell}{ytd_cell}"
                f"{st_cell}{rsi_cell}</tr>")
    except Exception as e:
        print(f"  [warn] {sym}: {e}", file=sys.stderr)
        nc = '<td class="needchk">확인 필요</td>'
        return f"          <tr>{name_td}{nc}{nc}{nc}{nc}{nc}{nc}</tr>"


# ---------------------------------------------------------------- 공포·탐욕 지수

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0 Safari/537.36")


def get_json(url, timeout=20):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))


def fng_class(score):
    """숫자를 색상 클래스로. 50 미만이면 공포(파랑), 초과면 탐욕(빨강)."""
    if score < 45:
        return "fng-fear"
    if score > 55:
        return "fng-greed"
    return "fng-neutral"


def fng_item_html(label, score, rating, asof, prev_line):
    """값이 있을 때의 카드 한 칸."""
    cls = fng_class(score)
    return (
        '          <div class="fng-item">\n'
        f'            <div class="fng-head"><span class="fng-label">{label}</span>'
        f'<span class="fng-rating {cls}">{rating}</span></div>\n'
        f'            <div class="fng-score">{score}</div>\n'
        f'            <div class="fng-bar"><div class="fng-mark" style="left:{score}%"></div></div>\n'
        '            <div class="fng-scale"><span>0 극도의 공포</span><span>50 중립</span>'
        '<span>극도의 탐욕 100</span></div>\n'
        f'            <div class="fng-prev">{asof}<br>{prev_line}</div>\n'
        '          </div>'
    )


def fng_item_fail(label, note):
    """값을 못 받아왔을 때. 숫자를 지어내지 않는다."""
    return (
        '          <div class="fng-item">\n'
        f'            <div class="fng-head"><span class="fng-label">{label}</span>'
        '<span class="fng-rating needchk">확인 필요</span></div>\n'
        '            <div class="fng-score needchk">확인 필요</div>\n'
        '            <div class="fng-bar"></div>\n'
        '            <div class="fng-scale"><span>0 극도의 공포</span><span>50 중립</span>'
        '<span>극도의 탐욕 100</span></div>\n'
        f'            <div class="fng-prev">{note}</div>\n'
        '          </div>'
    )


CNN_KO = [(25, "극도의 공포"), (45, "공포"), (56, "중립"), (76, "탐욕"), (101, "극도의 탐욕")]


def cnn_fng():
    d = get_json("https://production.dataviz.cnn.io/index/fearandgreed/graphdata")["fear_and_greed"]
    score = int(round(float(d["score"])))
    rating = next(ko for bound, ko in CNN_KO if score < bound)

    def n(key):
        try:
            return str(int(round(float(d[key]))))
        except Exception:
            return "확인 필요"

    # CNN이 주는 시각은 UTC. 미국장 마감일이므로 그 날짜를 그대로 쓴다.
    asof = str(d.get("timestamp", ""))[:10] or "확인 필요"
    prev = (f"전일 {n('previous_close')} · 1주 전 {n('previous_1_week')} · "
            f"1달 전 {n('previous_1_month')} · 1년 전 {n('previous_1_year')}")
    return fng_item_html("미국 주식 (CNN)", score, rating,
                         f"{asof} 미국장 마감 기준", prev)


CRYPTO_KO = {"Extreme Fear": "극도의 공포", "Fear": "공포", "Neutral": "중립",
             "Greed": "탐욕", "Extreme Greed": "극도의 탐욕"}


def crypto_fng():
    rows = get_json("https://api.alternative.me/fng/?limit=8")["data"]
    cur = rows[0]
    score = int(cur["value"])
    # 영어 등급을 그대로 한국어로 옮긴다. 구간을 임의로 다시 나누지 않는다.
    rating = CRYPTO_KO.get(cur["value_classification"], cur["value_classification"])
    asof = datetime.datetime.fromtimestamp(int(cur["timestamp"]), KST).date().isoformat()

    def at(i):
        return rows[i]["value"] if len(rows) > i else "확인 필요"

    prev = f"전일 {at(1)} · 1주 전 {at(7)}"
    return fng_item_html("암호화폐 (alternative.me)", score, rating,
                         f"{asof} 기준 (매일 09:00 KST 갱신)", prev)


def build_fng(closes=None):
    items = []
    for label, fn, note in (
        ("미국 주식 (CNN)", cnn_fng, "CNN에서 값을 받아오지 못했습니다"),
        ("암호화폐 (alternative.me)", crypto_fng, "alternative.me에서 값을 받아오지 못했습니다"),
    ):
        try:
            items.append(fn())
        except Exception as e:
            print(f"  [warn] {label} 공포탐욕지수: {e}", file=sys.stderr)
            items.append(fng_item_fail(label, note))
    # 한국은 공개 API가 없어서 야후 데이터로 직접 계산한다 (build_fng_kr 주석 참고).
    items.append(build_fng_kr(closes or {}))
    return '        <div class="fng-grid">\n' + "\n".join(items) + "\n        </div>"


# ------------------------------------------------------------- 빅테크 CAPEX

# (표시이름, 티커, 로고도메인)
M7 = [
    ("아마존", "AMZN", "amazon.com"),
    ("알파벳", "GOOGL", "abc.xyz"),
    ("마이크로소프트", "MSFT", "microsoft.com"),
    ("메타", "META", "meta.com"),
    ("엔비디아", "NVDA", "nvidia.com"),
    ("애플", "AAPL", "apple.com"),
    ("테슬라", "TSLA", "tesla.com"),
]

# 야후가 이 항목을 부르는 이름이 종목·시점에 따라 다르다. 순서대로 찾는다.
CAPEX_ROWS = ["Capital Expenditure", "CapitalExpenditure",
              "Capital Expenditures", "Purchase Of PPE", "PurchaseOfPPE"]

QUARTERS = 6  # 화면에 보여줄 최근 분기 수


def quarter_label(ts):
    """2026-06-30 -> '26 2Q'. 회계연도가 아니라 기간 종료일 기준 달력 분기다."""
    q = (ts.month - 1) // 3 + 1
    return f"{ts.year % 100:02d} {q}Q"


def fetch_capex(ticker):
    """[(분기라벨, 금액USD), ...] 오래된 것부터. 실패하면 예외를 던진다."""
    cf = yf.Ticker(ticker).quarterly_cashflow
    if cf is None or cf.empty:
        raise ValueError("빈 현금흐름표")
    row = next((r for r in CAPEX_ROWS if r in cf.index), None)
    if row is None:
        raise ValueError(f"CAPEX 항목 없음 (있는 항목 예: {list(cf.index)[:3]})")
    s = cf.loc[row].dropna()
    if s.empty:
        raise ValueError("CAPEX 값이 전부 비어 있음")
    # 현금흐름표에서 지출은 음수로 들어온다. 크기만 쓴다.
    s = s.abs().sort_index()
    s = s[-QUARTERS:]
    return [(quarter_label(ts), float(v)) for ts, v in s.items()]


def bil(v):
    return f"${v / 1e9:.1f}B"


def pct_span(v):
    if v is None:
        return '<span class="needchk">확인 필요</span>'
    cls = "up" if v > 0 else ("down" if v < 0 else "flat")
    return f'<span class="{cls}">{v:+.1f}%</span>'


def capex_item(name, ticker, logo, series):
    peak = max(v for _, v in series)
    bars = []
    for i, (lab, v) in enumerate(series):
        h = max(3, round(v / peak * 100)) if peak > 0 else 3
        last = " is-last" if i == len(series) - 1 else ""
        bars.append(f'<div class="capex-bar"><div class="capex-fill{last}" '
                    f'style="height:{h}%" title="{lab} {bil(v)}"></div>'
                    f'<div class="capex-xlab">{lab}</div></div>')

    def change(back):
        if len(series) <= back:
            return None
        base = series[-1 - back][1]
        return (series[-1][1] / base - 1) * 100 if base else None

    logo_html = (f'<img class="supp-logo" src="https://logo.clearbit.com/{logo}" '
                 f"onerror=\"this.style.display='none'\">")
    return (
        '          <div class="capex-item">\n'
        f'            <div class="capex-head">{logo_html}{name}'
        f'<span class="supp-ticker">{ticker}</span></div>\n'
        f'            <div class="capex-latest">{bil(series[-1][1])}'
        f'<span class="capex-q">{series[-1][0]}</span></div>\n'
        f'            <div class="capex-bars">{"".join(bars)}</div>\n'
        f'            <div class="capex-delta">전분기 대비 {pct_span(change(1))} · '
        f'1년 전 대비 {pct_span(change(4))}</div>\n'
        '          </div>'
    )


def capex_item_fail(name, ticker, logo, why):
    logo_html = (f'<img class="supp-logo" src="https://logo.clearbit.com/{logo}" '
                 f"onerror=\"this.style.display='none'\">")
    return (
        '          <div class="capex-item">\n'
        f'            <div class="capex-head">{logo_html}{name}'
        f'<span class="supp-ticker">{ticker}</span></div>\n'
        '            <div class="capex-latest needchk">확인 필요</div>\n'
        f'            <div class="capex-delta">{why}</div>\n'
        '          </div>'
    )


def build_capex():
    items, ok = [], 0
    for name, ticker, logo in M7:
        try:
            items.append(capex_item(name, ticker, logo, fetch_capex(ticker)))
            ok += 1
        except Exception as e:
            print(f"  [warn] CAPEX {ticker}: {e}", file=sys.stderr)
            items.append(capex_item_fail(name, ticker, logo, "분기 현금흐름표를 못 받아왔습니다"))
    print(f"  capex {ok}/{len(M7)}")
    return '        <div class="capex-grid">\n' + "\n".join(items) + "\n        </div>"


# ------------------------------------------------- 빅테크 매출 / 영업이익 / 이익률
#
# 야후 분기 손익계산서에서 매출과 영업이익을 받아 이익률까지 계산한다.
# - 성장률은 전년 동기 대비(YoY)다. 4분기 전 값과 비교하므로 최소 5개 분기가 있어야 한다.
# - 이익률은 % 자체가 값이므로 증감을 %가 아니라 %p로 적는다.
#   (12% -> 15%는 "3%p 상승"이지 "3% 상승"이 아니다. 이 둘을 섞으면 숫자가 거짓말이 된다)
# - 매출이 0이거나 없는 분기는 이익률을 계산하지 않고 건너뛴다.
# - 야후 무료 데이터는 보통 5~8분기만 준다. 모자라면 있는 만큼만 그린다.

FIN_QUARTERS = 8

# 야후가 항목을 부르는 이름이 종목·시점마다 다르다. 순서대로 찾는다.
REV_ROWS = ["Total Revenue", "TotalRevenue", "Operating Revenue", "OperatingRevenue"]
OPI_ROWS = ["Operating Income", "OperatingIncome",
            "Total Operating Income As Reported", "TotalOperatingIncomeAsReported"]


def _pick_row(df, names):
    row = next((r for r in names if r in df.index), None)
    return None if row is None else df.loc[row].dropna()


def fetch_fin(ticker):
    """[(분기라벨, 매출, 영업이익), ...] 오래된 것부터. 실패하면 예외."""
    inc = yf.Ticker(ticker).quarterly_income_stmt
    if inc is None or inc.empty:
        raise ValueError("빈 손익계산서")
    rev = _pick_row(inc, REV_ROWS)
    opi = _pick_row(inc, OPI_ROWS)
    if rev is None or rev.empty:
        raise ValueError(f"매출 항목 없음 (있는 항목 예: {list(inc.index)[:3]})")
    if opi is None or opi.empty:
        raise ValueError("영업이익 항목 없음")
    out = []
    for ts in sorted(set(rev.index) & set(opi.index)):
        r, o = float(rev[ts]), float(opi[ts])
        if r <= 0:
            continue          # 매출이 없으면 이익률을 계산할 수 없다
        out.append((quarter_label(ts), r, o))
    if not out:
        raise ValueError("매출·영업이익이 같이 있는 분기가 없음")
    return out[-FIN_QUARTERS:]


def pp_span(v):
    """%p 증감. 표시가 소수 한 자리이므로 반올림한 값으로 색을 정한다."""
    if v is None:
        return '<span class="needchk">확인 필요</span>'
    d = round(v, 1) + 0.0
    cls = "up" if d > 0 else ("down" if d < 0 else "flat")
    return f'<span class="{cls}">{d:+.1f}%p</span>'


def fin_bars(vals, labs, fmt):
    """막대 8개. 값이 음수면 아래쪽 색으로 구분한다."""
    peak = max((abs(v) for v in vals if v is not None), default=0)
    out = []
    for i, (v, lab) in enumerate(zip(vals, labs)):
        if v is None:
            out.append('<div class="fin-bar"><div class="fin-fill is-na" '
                       f'style="height:3%" title="{lab} 확인 필요"></div>'
                       f'<div class="fin-xlab">{lab}</div></div>')
            continue
        h = max(3, round(abs(v) / peak * 100)) if peak > 0 else 3
        cls = " is-neg" if v < 0 else (" is-last" if i == len(vals) - 1 else "")
        out.append(f'<div class="fin-bar"><div class="fin-fill{cls}" '
                   f'style="height:{h}%" title="{lab} {fmt(v)}"></div>'
                   f'<div class="fin-xlab">{lab}</div></div>')
    return "".join(out)


def fin_metric(label, vals, labs, fmt, chg_html):
    cur = vals[-1]
    val_html = (f'<div class="fin-mval">{fmt(cur)}</div>' if cur is not None
                else '<div class="fin-mval needchk">확인 필요</div>')
    return ('            <div class="fin-metric">\n'
            f'              <div class="fin-mlabel">{label}</div>\n'
            f'              {val_html}\n'
            f'              <div class="fin-mchg">전년 동기 대비 {chg_html}</div>\n'
            f'              <div class="fin-bars">{fin_bars(vals, labs, fmt)}</div>\n'
            '            </div>')


def fin_item(name, ticker, logo, series):
    labs = [q for q, _, _ in series]
    revs = [r for _, r, _ in series]
    ops = [o for _, _, o in series]
    mgs = [o / r * 100 for _, r, o in series]

    def yoy(vals):
        # 4분기 전과 비교한다. 데이터가 5개 미만이면 계산하지 않는다.
        if len(vals) < 5:
            return None
        base = vals[-5]
        return (vals[-1] / base - 1) * 100 if base else None

    mg_pp = (mgs[-1] - mgs[-5]) if len(mgs) >= 5 else None

    logo_html = (f'<img class="supp-logo" src="https://logo.clearbit.com/{logo}" '
                 f"onerror=\"this.style.display='none'\">")
    return (
        '          <div class="fin-item">\n'
        f'            <div class="fin-head">{logo_html}{name}'
        f'<span class="supp-ticker">{ticker}</span>'
        f'<span class="fin-q">{labs[-1]} 기준</span></div>\n'
        '            <div class="fin-metrics">\n'
        + fin_metric("매출", revs, labs, bil, pct_span(yoy(revs))) + "\n"
        + fin_metric("영업이익", ops, labs, bil, pct_span(yoy(ops))) + "\n"
        + fin_metric("영업이익률", mgs, labs, lambda v: f"{v:.1f}%", pp_span(mg_pp)) + "\n"
        '            </div>\n'
        '          </div>'
    )


def fin_item_fail(name, ticker, logo, why):
    logo_html = (f'<img class="supp-logo" src="https://logo.clearbit.com/{logo}" '
                 f"onerror=\"this.style.display='none'\">")
    return ('          <div class="fin-item">\n'
            f'            <div class="fin-head">{logo_html}{name}'
            f'<span class="supp-ticker">{ticker}</span></div>\n'
            f'            <div class="fin-fail needchk">확인 필요 — {why}</div>\n'
            '          </div>')


def build_fin():
    items, ok = [], 0
    for name, ticker, logo in M7:
        try:
            items.append(fin_item(name, ticker, logo, fetch_fin(ticker)))
            ok += 1
        except Exception as e:
            print(f"  [warn] 재무 {ticker}: {e}", file=sys.stderr)
            items.append(fin_item_fail(name, ticker, logo, "분기 손익계산서를 못 받아왔습니다"))
    print(f"  fin {ok}/{len(M7)}")
    return '        <div class="fin-grid">\n' + "\n".join(items) + "\n        </div>"

# ------------------------------------------------------------- 주요 지수 카드

# (표시이름, 짧은라벨, 야후심볼, 트레이딩뷰심볼, 소수점자리)
INDEXES = [
    ("S&amp;P500", "SPX", "^GSPC", "FOREXCOM:SPXUSD", 2),
    ("나스닥 종합", "IXIC", "^IXIC", "NASDAQ:IXIC", 2),
    ("다우존스", "DJI", "^DJI", "FOREXCOM:DJI", 2),
    ("VIX 공포지수", "VIX", "^VIX", "TVC:VIX", 2),
    ("코스피", "KOSPI", "^KS11", "KRX:KOSPI", 2),
    ("코스닥", "KOSDAQ", "^KQ11", "KRX:KOSDAQ", 2),
    ("원달러 환율", "USDKRW", "KRW=X", "FX_IDC:USDKRW", 2),
    ("미 10년물 금리", "US10Y", "^TNX", "TVC:US10Y", 3),
]


def num(v, digits):
    return f"{v:,.{digits}f}"


def idx_card(name, label, tvsym, last, prev, digits):
    """지수 카드 하나. 클릭하면 차트가 펼쳐지도록 <details>로 감싼다."""
    chg = last - prev
    pct = (last / prev - 1) * 100 if prev else 0.0
    cls = "up" if chg > 0 else ("down" if chg < 0 else "flat")
    sign = "+" if chg > 0 else ""
    return (
        '          <details class="idx-card">\n'
        '            <summary class="idx-sum">\n'
        f'              <div class="idx-name">{name}<span class="idx-sym">{label}</span></div>\n'
        f'              <div class="idx-val">{num(last, digits)}</div>\n'
        f'              <div class="idx-chg {cls}">{sign}{pct:.2f}%'
        f'<span class="idx-abs">{sign}{num(chg, digits)}</span></div>\n'
        '              <span class="idx-more">차트 보기</span>\n'
        '            </summary>\n'
        f'            <div class="idx-chart" data-tvsym="{tvsym}"></div>\n'
        '          </details>'
    )


def idx_card_fail(name, label, tvsym):
    return (
        '          <details class="idx-card">\n'
        '            <summary class="idx-sum">\n'
        f'              <div class="idx-name">{name}<span class="idx-sym">{label}</span></div>\n'
        '              <div class="idx-val needchk">확인 필요</div>\n'
        '              <div class="idx-chg needchk">시세를 못 받아왔습니다</div>\n'
        '              <span class="idx-more">차트 보기</span>\n'
        '            </summary>\n'
        f'            <div class="idx-chart" data-tvsym="{tvsym}"></div>\n'
        '          </details>'
    )


def build_idx(closes):
    cards, ok = [], 0
    for name, label, sym, tvsym, digits in INDEXES:
        try:
            s = closes[sym].dropna()
            if len(s) < 2:
                raise ValueError("데이터 부족")
            cards.append(idx_card(name, label, tvsym,
                                  float(s.iloc[-1]), float(s.iloc[-2]), digits))
            ok += 1
        except Exception as e:
            print(f"  [warn] 지수 {sym}: {e}", file=sys.stderr)
            cards.append(idx_card_fail(name, label, tvsym))
    print(f"  지수 {ok}/{len(INDEXES)}")
    return '        <div class="idx-grid">\n' + "\n".join(cards) + "\n        </div>"


# --------------------------------------------------- 한국 시장심리 지수 (자체 산출)
#
# 중요: 이건 CNN 공포탐욕지수의 한국판이 아니다. 그런 지수를 무료 공개 API로 주는
# 곳이 없어서(확인함), 야후 파이낸스로 받을 수 있는 값만 가지고 직접 계산한다.
# 계산식을 전부 아래에 적어두었고, 화면에도 "자체 산출"이라고 밝힌다.
# 하나라도 계산이 안 되면 지어내지 않고 "확인 필요"로 표시한다.

KR_BOND_ETF = "148070.KS"   # KOSEF 국고채10년 — 안전자산 선호 계산용


def scale(v, lo, hi):
    """lo~hi 구간을 0~100으로. 범위를 벗어나면 0 또는 100으로 자른다."""
    if hi == lo:
        return 50.0
    return max(0.0, min(100.0, (v - lo) / (hi - lo) * 100))


def kr_sentiment(closes):
    """(점수, 세부항목 dict) 반환. 계산 불가하면 예외."""
    ks = closes["^KS11"].dropna()
    if len(ks) < 260:
        raise ValueError("코스피 데이터가 1년치가 안 됨")
    last = float(ks.iloc[-1])

    # 1) 모멘텀 30% — 125일 이동평균 대비 이격도. -10%~+10%를 0~100으로.
    ma125 = float(ks.tail(125).mean())
    momentum = scale((last / ma125 - 1) * 100, -10, 10)

    # 2) 변동성 30% — 20일 실현변동성이 최근 1년 중 몇 번째인지(백분위).
    #    변동성이 높을수록 공포이므로 뒤집는다.
    ret = ks.pct_change().dropna()
    vol20 = ret.rolling(20).std().dropna()
    if len(vol20) < 200:
        raise ValueError("변동성 계산 구간 부족")
    recent = vol20.tail(252)
    pctile = float((recent < float(vol20.iloc[-1])).mean()) * 100
    volatility = 100 - pctile

    # 3) 주가강도 20% — 최근 52주 고가~저가 사이에서 현재 위치.
    win = ks.tail(252)
    strength = scale(last, float(win.min()), float(win.max()))

    # 4) 안전자산 선호 20% — 코스피 20일 수익률에서 국고채ETF 20일 수익률을 뺀 값.
    #    주식이 채권보다 잘 갈수록 위험선호(=탐욕).
    bond = closes[KR_BOND_ETF].dropna()
    if len(bond) < 21:
        raise ValueError("국고채 ETF 데이터 부족")
    ks_20 = (last / float(ks.iloc[-21]) - 1) * 100
    bd_20 = (float(bond.iloc[-1]) / float(bond.iloc[-21]) - 1) * 100
    haven = scale(ks_20 - bd_20, -10, 10)

    score = momentum * 0.30 + volatility * 0.30 + strength * 0.20 + haven * 0.20
    parts = {"모멘텀": momentum, "변동성": volatility,
             "주가강도": strength, "안전자산 선호": haven}
    return score, parts


def build_fng_kr(closes):
    try:
        score, parts = kr_sentiment(closes)
        s = int(round(score))
        rating = next(ko for bound, ko in CNN_KO if s < bound)
        asof = str(closes["^KS11"].dropna().index[-1])[:10]
        detail = " · ".join(f"{k} {v:.0f}" for k, v in parts.items())
        return fng_item_html("한국 주식 (자체 산출)", s, rating,
                             f"{asof} 코스피 종가 기준",
                             f"{detail}<br>공식 지수가 아니라 공개 데이터로 직접 계산한 값입니다")
    except Exception as e:
        print(f"  [warn] 한국 심리지수: {e}", file=sys.stderr)
        return fng_item_fail("한국 주식 (자체 산출)", "계산에 필요한 데이터를 못 받아왔습니다")


# ------------------------------------------------------ 미 국채 금리 / 장단기차
#
# ^TNX(10년물)와 2YY=F(2년물)는 이미 macro 섹션에서 받아오므로 그 값을 다시 쓴다.
# 둘 다 "연 몇 %"로 들어온다. 금리 얘기에서 흔히 쓰는 bp(베이시스포인트)는
# 0.01%p이므로, 0.52%p = 52bp다. 화면에는 %p와 bp를 같이 적는다.
# 두 값 중 하나라도 없으면 금리차를 계산하지 않고 "확인 필요"로 둔다.

Y10 = "^TNX"
Y02 = "2YY=F"


def ago(s, days):
    """days 거래일 전 값. 데이터가 모자라면 None."""
    if len(s) > days:
        return float(s.iloc[-1 - days])
    return None


def yld_item(label, val, prev, m1, y1, unit="%"):
    if val is None:
        return ('          <div class="yld-item">\n'
                f'            <div class="yld-label">{label}</div>\n'
                '            <div class="yld-val needchk">확인 필요</div>\n'
                '            <div class="yld-sub">값을 못 받아왔습니다</div>\n'
                '          </div>')
    if prev is None:
        chg_html = '<span class="yld-chg needchk">전일 대비 확인 필요</span>'
    else:
        # 표시는 소수 둘째 자리까지다. 반올림하면 0인데 색만 오르내리면 거짓말이 되므로
        # 반올림한 값으로 색을 정한다.
        d = round(val - prev, 2) + 0.0
        cls = "up" if d > 0 else ("down" if d < 0 else "flat")
        chg_html = f'<span class="yld-chg {cls}">전일 대비 {d:+.2f}%p</span>'
    hist = " · ".join(
        f"{tag} {v:.2f}{unit}" if v is not None else f"{tag} 확인 필요"
        for tag, v in (("1개월 전", m1), ("1년 전", y1)))
    return ('          <div class="yld-item">\n'
            f'            <div class="yld-label">{label}</div>\n'
            f'            <div class="yld-val">{val:.2f}{unit}</div>\n'
            f'            <div class="yld-sub">{chg_html}</div>\n'
            f'            <div class="yld-hist">{hist}</div>\n'
            '          </div>')


def build_yield(closes):
    def pick(sym):
        try:
            s = closes[sym].dropna()
            if len(s) < 2:
                return None, None, None, None
            return float(s.iloc[-1]), ago(s, 1), ago(s, 21), ago(s, 252)
        except Exception as e:
            print(f"  [warn] 금리 {sym}: {e}", file=sys.stderr)
            return None, None, None, None

    t10, p10, m10, y10 = pick(Y10)
    t02, p02, m02, y02 = pick(Y02)

    items = [yld_item("미 10년물", t10, p10, m10, y10),
             yld_item("미 2년물", t02, p02, m02, y02)]

    if t10 is None or t02 is None:
        items.append(yld_item("장단기 금리차 (10년 − 2년)", None, None, None, None))
        state = '<span class="needchk">두 금리를 다 받아와야 계산할 수 있습니다</span>'
    else:
        sp = t10 - t02
        spp = (p10 - p02) if (p10 is not None and p02 is not None) else None
        spm = (m10 - m02) if (m10 is not None and m02 is not None) else None
        spy = (y10 - y02) if (y10 is not None and y02 is not None) else None
        items.append(yld_item("장단기 금리차 (10년 − 2년)", sp, spp, spm, spy, unit="%p"))
        if sp < 0:
            state = ('<b class="down">역전 상태</b> — 2년물이 10년물보다 '
                     f'{abs(sp) * 100:.0f}bp 높습니다')
        else:
            state = ('<b class="up">역전 아님</b> — 10년물이 2년물보다 '
                     f'{sp * 100:.0f}bp 높습니다')
        print(f"  금리 10Y={t10:.2f} 2Y={t02:.2f} 차={sp:+.2f}%p")

    return ('        <div class="yld-grid">\n' + "\n".join(items) + "\n        </div>\n"
            f'        <div class="yld-state">{state}</div>')


# --------------------------------------------------------- 실적 캘린더 (자동)
#
# 야후 파이낸스의 실적 발표일을 그대로 가져온다. 두 가지는 야후가 주지 않으므로
# 지어내지 않고 아예 표시하지 않는다:
#   1) 장전/장후 시간대 — 야후 API에 해당 항목이 없다.
#   2) "회사 공식 발표"인지 여부 — 다만 calendar가 날짜를 두 개(기간)로 주면
#      아직 확정되지 않은 추정 구간이라는 뜻이라, 그때만 "예상"으로 표시한다.

EARN_WINDOW = 70        # 오늘부터 며칠치까지 보여줄지
EARN_MAX = 40           # 목록에 넣을 최대 개수

WEEKDAYS_KO = ["일", "월", "화", "수", "목", "금", "토"]


def earn_targets():
    """실적일을 조회할 (표시이름, 짧은라벨, 야후심볼) 목록."""
    out = []
    for section in ("us30", "kr10"):
        for name, label, _dom, sym, _r in SECTIONS[section]:
            # 표 라벨에 HTML이 섞여 있을 수 있으니 태그를 떼어낸다
            short = re.sub(r"<[^>]+>", "", label).strip()
            # 한국 종목의 라벨은 "005930" 같은 숫자 코드라 달력 칩으로는 못 알아본다.
            # 이럴 땐 회사 이름을 쓴다.
            if short.isdigit():
                short = name
            out.append((name, short, sym))
    return out


def fetch_earnings(sym):
    """(날짜, 확정여부) 또는 None. 오늘 이후 가장 가까운 발표일 하나만."""
    t = yf.Ticker(sym)
    today = datetime.datetime.now(KST).date()

    # 1순위: calendar — 날짜가 1개면 확정, 2개면 추정 구간
    try:
        cal = t.calendar
        dates = cal.get("Earnings Date") if isinstance(cal, dict) else None
        if dates:
            ds = sorted({d.date() if hasattr(d, "date") else d for d in dates})
            future = [d for d in ds if d >= today]
            if future:
                return future[0], len(ds) == 1
    except Exception as e:
        print(f"  [warn] {sym} calendar: {e}", file=sys.stderr)

    # 2순위: get_earnings_dates — 확정 여부를 알 수 없으므로 미확정으로 본다
    try:
        df = t.get_earnings_dates(limit=12)
        # .empty는 열이 없으면 행이 있어도 True라서, 인덱스 길이로 판단한다
        if df is not None and len(df.index):
            for ts in sorted(df.index):
                d = ts.date()
                if d >= today:
                    return d, False
    except Exception as e:
        print(f"  [warn] {sym} earnings_dates: {e}", file=sys.stderr)
    return None


def collect_earnings():
    today = datetime.datetime.now(KST).date()
    limit = today + datetime.timedelta(days=EARN_WINDOW)
    rows, miss = [], []
    for name, short, sym in earn_targets():
        try:
            got = fetch_earnings(sym)
        except Exception as e:
            print(f"  [warn] {sym}: {e}", file=sys.stderr)
            got = None
        if not got:
            miss.append(short)
            continue
        d, confirmed = got
        if d > limit:
            continue
        rows.append((d, name, short, confirmed))
    rows.sort(key=lambda r: (r[0], r[2]))
    print(f"  실적일 {len(rows)}건 수집, {len(miss)}종목 미확인")
    return rows[:EARN_MAX], miss


def build_earn_list(rows):
    if not rows:
        return ('        <div class="earn-empty">앞으로 '
                f'{EARN_WINDOW}일 안에 잡힌 발표일을 하나도 받아오지 못했습니다 (확인 필요)</div>')
    out = []
    for d, name, short, confirmed in rows:
        tag = "확정" if confirmed else "예상일 (미확정)"
        wd = WEEKDAYS_KO[(d.weekday() + 1) % 7]
        out.append(
            '        <div class="earn-row">\n'
            f'          <div><div class="earn-name">{short if short == name else short + " " + name}</div>'
            f'<div class="earn-tag">{tag}</div></div>\n'
            f'          <div class="earn-date">{d.isoformat()} ({wd})</div>\n'
            '        </div>'
        )
    return "\n".join(out)


def build_earn_cal(rows):
    """이번 달과 다음 달 달력을 그린다. 칩은 짧은 라벨만, 미확정이면 * 를 붙인다."""
    import calendar as _cal
    by_day = {}
    for d, _name, short, confirmed in rows:
        by_day.setdefault(d, []).append(short + ("" if confirmed else "*"))

    today = datetime.datetime.now(KST).date()
    months, y, m = [], today.year, today.month
    for _ in range(2):
        cells = []
        first_wd = (datetime.date(y, m, 1).weekday() + 1) % 7    # 일요일 시작
        ndays = _cal.monthrange(y, m)[1]
        prev_days = _cal.monthrange(y - 1, 12)[1] if m == 1 else _cal.monthrange(y, m - 1)[1]
        for i in range(first_wd):
            n = prev_days - first_wd + i + 1
            cells.append(f'<div class="cal-cell empty"><div class="cal-daynum">{n}</div></div>')
        for day in range(1, ndays + 1):
            d = datetime.date(y, m, day)
            chips = "".join(f'<div class="cal-chip">{c}</div>' for c in by_day.get(d, []))
            cls = "cal-cell today" if d == today else "cal-cell"
            cells.append(f'<div class="{cls}"><div class="cal-daynum">{day}</div>{chips}</div>')
        while len(cells) % 7:
            cells.append('<div class="cal-cell empty"></div>')
        head = "".join(f'<div class="cal-weekday">{w}</div>' for w in WEEKDAYS_KO)
        weeks = ["".join(cells[i:i + 7]) for i in range(0, len(cells), 7)]
        body = "\n            ".join(weeks)
        months.append(
            '        <div class="cal-month">\n'
            f'          <div class="cal-month-title">{y}년 {m}월</div>\n'
            '          <div class="cal-grid">\n'
            f'            {head}\n'
            f'            {body}\n'
            '          </div>\n'
            '        </div>'
        )
        m = 1 if m == 12 else m + 1
        y = y + 1 if m == 1 else y
    return "\n".join(months)


def splice(html, marker, body):
    start, end = f"<!--{marker}:START-->", f"<!--{marker}:END-->"
    i, j = html.find(start), html.find(end)
    if i == -1 or j == -1:
        print(f"  [error] markers for {marker} not found", file=sys.stderr)
        return html, False
    return html[: i + len(start)] + "\n" + body + "\n      " + html[j:], True


def main(html_path):
    all_syms = sorted(
        {sym for rows in SECTIONS.values() for _, _, _, sym, _ in rows}
        | {sym for _, _, sym, _, _ in INDEXES}       # 개요 탭 주요 지수 카드
        | {KR_BOND_ETF}                              # 한국 심리지수 계산용
    )
    print(f"downloading {len(all_syms)} symbols...")
    # auto_adjust=True : 액면분할·배당을 보정한 수정주가로 받는다.
    # (보정 안 된 원주가를 쓰면 분할일이 하루 만에 -50% 폭락한 것처럼 계산된다)
    data = yf.download(all_syms, period="15mo", interval="1d",
                       auto_adjust=True, progress=False, group_by="ticker", threads=True)

    closes = {}
    for sym in all_syms:
        try:
            s = data[sym]["Close"] if isinstance(data.columns, pd.MultiIndex) else data["Close"]
            if s.dropna().empty:
                raise ValueError("empty")
            closes[sym] = s
        except Exception as e:
            print(f"  [warn] no data for {sym}: {e}", file=sys.stderr)

    with open(html_path, encoding="utf-8") as f:
        html = f.read()

    ok_count = 0
    for section, rows in SECTIONS.items():
        body = "\n".join(make_row(*row, closes) for row in rows)
        start = f"<!--SUPP:{section}:START-->"
        end = f"<!--SUPP:{section}:END-->"
        i, j = html.find(start), html.find(end)
        if i == -1 or j == -1:
            print(f"  [error] markers for {section} not found", file=sys.stderr)
            continue
        html = html[: i + len(start)] + "\n" + body + "\n          " + html[j:]
        ok_count += 1

    print("building index cards...")
    html, idx_ok = splice(html, "IDX", build_idx(closes))

    print("fetching fear & greed...")
    html, fng_ok = splice(html, "FNG", build_fng(closes))

    print("building yield curve...")
    html, yld_ok = splice(html, "YIELD", build_yield(closes))

    print("fetching earnings dates...")
    earn_rows, earn_miss = collect_earnings()
    html, ecal_ok = splice(html, "EARNCAL", build_earn_cal(earn_rows))
    html, elist_ok = splice(html, "EARNLIST", build_earn_list(earn_rows))
    miss_txt = ("받아오지 못한 종목: " + ", ".join(earn_miss)) if earn_miss else "전 종목 조회 성공"
    em_s, em_e = "<!--EARNMISS-->", "<!--/EARNMISS-->"
    i, j = html.find(em_s), html.find(em_e)
    if i != -1 and j != -1:
        html = html[: i + len(em_s)] + miss_txt + html[j:]

    print("fetching big-tech capex...")
    html, capex_ok = splice(html, "CAPEX", build_capex())

    print("fetching big-tech financials...")
    html, fin_ok = splice(html, "FIN", build_fin())

    # 깃허브 서버는 UTC로 돌아가므로, 한국시간 기준 날짜로 찍는다.
    # (UTC 21:37 실행 = 한국 다음날 06:37 → UTC 날짜를 쓰면 하루 밀려 보인다)
    today = datetime.datetime.now(KST).date().isoformat()
    ds, de = "<!--SUPPDATE-->", "<!--/SUPPDATE-->"
    i, j = html.find(ds), html.find(de)
    if i != -1 and j != -1:
        html = html[: i + len(ds)] + f"{today} (자동)" + html[j:]

    with open(html_path, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"updated {ok_count}/{len(SECTIONS)} sections, "
          f"{len(closes)}/{len(all_syms)} symbols fetched, "
          f"idx={'ok' if idx_ok else 'MARKER MISSING'}, "
          f"earn={'ok' if ecal_ok and elist_ok else 'MARKER MISSING'}({len(earn_rows)}건), "
          f"fng={'ok' if fng_ok else 'MARKER MISSING'}, "
          f"yield={'ok' if yld_ok else 'MARKER MISSING'}, "
          f"capex={'ok' if capex_ok else 'MARKER MISSING'}, "
          f"fin={'ok' if fin_ok else 'MARKER MISSING'}, date={today}")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "index.html")
