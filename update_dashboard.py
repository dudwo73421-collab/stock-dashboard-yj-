# -*- coding: utf-8 -*-
"""
대시보드 보조 지표 자동 갱신 스크립트 (GitHub Actions에서 매일 실행됨)

index.html 안의 <!--SUPP:섹션:START--> ~ <!--SUPP:섹션:END--> 사이를
야후 파이낸스 일봉 데이터로 계산한 최신 값으로 갈아끼운다.

계산 지표:
  일간          : 직전 거래일 종가 대비 현재 종가
  52주 고점대비 : 최근 52주(252거래일) 최고 종가 대비 현재 종가
  사상최고 대비 : 상장 이후 전체 기간 최고 종가 대비 현재 종가
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
import io
import json
import re
import datetime
import math
import time
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
        ("MAGS", "MAGS", "roundhillinvestments.com", "MAGS", True),
        ("SOXX", "SOXX", "ishares.com", "SOXX", True),
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


def compute(close: pd.Series, rate: bool, ath: float | None = None):
    """보조지표 계산. ath는 상장 이후 전체 기간의 최고 종가(사상 최고).

    "고점대비"를 두 가지로 나눠서 낸다.
      - 52주 고점대비 : 최근 252거래일(약 1년) 종가 중 최고값 대비
      - 사상최고 대비 : 상장 이후 전체 종가 중 최고값 대비
    둘을 합쳐 놓으면 1년보다 더 전에 고점을 찍고 크게 무너진 종목(예: 유나이티드
    헬스는 2024-11 $609 → 이후 급락)이 실제보다 덜 빠진 것처럼 보인다. 그래서
    분리한다. ath를 못 받아온 경우에는 만들어 채우지 않고 None을 돌려준다.
    """
    close = close.dropna()
    if len(close) < 30:
        raise ValueError("not enough data")
    last = float(close.iloc[-1])

    day = (last / float(close.iloc[-2]) - 1) * 100 if len(close) >= 2 else None

    high52 = float(close.tail(252).max())
    drawdown = (last / high52 - 1) * 100

    ath_dd = None
    if ath is not None and ath > 0:
        # 전체 기간 최고값은 최근 1년 최고값보다 낮을 수 없다. 낮게 나오면
        # 전체 기간 시세를 제대로 못 받은 것이므로 값을 쓰지 않는다.
        ath_dd = (last / max(ath, high52) - 1) * 100

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
    return day, drawdown, ath_dd, week, ytd, (streak, direction), rsi


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


def make_row(name, label, logo, sym, rate, closes, aths=None):
    aths = aths or {}
    logo_html = (f'<img class="supp-logo" src="https://logo.clearbit.com/{logo}" '
                 f"onerror=\"this.style.display='none'\">") if logo else ""
    name_td = f'<td>{logo_html}{name}<span class="supp-ticker">{label}</span></td>'
    try:
        close = closes[sym]
        day, dd52, ddath, week, ytd, sd, rsi = compute(close, rate, aths.get(sym))
        day_cell = pct_cell(day)
        dd_cell = pct_cell(dd52)
        ath_cell = pct_cell(ddath)
        wk_cell = pct_cell(week)
        ytd_cell = pct_cell(ytd)
        st_cell = streak_cell(sd)
        rsi_cell = f"<td>{rsi:.1f}</td>"
        return (f"          <tr>{name_td}{day_cell}{dd_cell}{ath_cell}{wk_cell}"
                f"{ytd_cell}{st_cell}{rsi_cell}</tr>")
    except Exception as e:
        print(f"  [warn] {sym}: {e}", file=sys.stderr)
        nc = '<td class="needchk">확인 필요</td>'
        return f"          <tr>{name_td}{nc * 7}</tr>"


# ---------------------------------------------------------------- 공포·탐욕 지수

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0 Safari/537.36")


def get_json(url, timeout=20, extra_headers=None, retries=3):
    """JSON을 받아온다. 실패하면 잠깐 쉬었다가 다시 시도한다.

    CNN 쪽은 브라우저가 아닌 요청을 걸러내서 418을 돌려주는 때가 있다. 그래서
    브라우저가 실제로 보내는 헤더(Referer/Origin/sec-fetch-*)를 같이 붙인다.
    끝까지 실패하면 예외를 던지고, 호출부에서 "확인 필요"로 처리한다.
    """
    headers = {
        "User-Agent": UA,
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "en-US,en;q=0.9",
        "Accept-Encoding": "identity",
        "Connection": "close",
    }
    if extra_headers:
        headers.update(extra_headers)
    last = None
    for i in range(retries):
        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return json.loads(r.read().decode("utf-8", "replace"))
        except Exception as e:
            last = e
            if i < retries - 1:
                time.sleep(2 * (i + 1))
    raise last


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


# CNN은 자기 사이트에서 온 요청만 받아준다. 이 헤더가 없으면 HTTP 418로 막힌다.
# (2026-08-05 Actions 로그: "[warn] 미국 주식 (CNN) 공포탐욕지수: HTTP Error 418")
CNN_HEADERS = {
    "Referer": "https://edition.cnn.com/",
    "Origin": "https://edition.cnn.com",
    "Sec-Fetch-Site": "cross-site",
    "Sec-Fetch-Mode": "cors",
    "Sec-Fetch-Dest": "empty",
}


def cnn_fng():
    d = get_json("https://production.dataviz.cnn.io/index/fearandgreed/graphdata",
                 extra_headers=CNN_HEADERS)["fear_and_greed"]
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
BIGTECH = [
    ("아마존", "AMZN", "amazon.com"),
    ("알파벳", "GOOGL", "abc.xyz"),
    ("마이크로소프트", "MSFT", "microsoft.com"),
    ("메타", "META", "meta.com"),
    ("엔비디아", "NVDA", "nvidia.com"),
    ("애플", "AAPL", "apple.com"),
    ("테슬라", "TSLA", "tesla.com"),
    ("오라클", "ORCL", "oracle.com"),
]

# 야후가 이 항목을 부르는 이름이 종목·시점에 따라 다르다. 순서대로 찾는다.
CAPEX_ROWS = ["Capital Expenditure", "CapitalExpenditure",
              "Capital Expenditures", "Purchase Of PPE", "PurchaseOfPPE"]

QUARTERS = 8  # 화면에 보여줄 최근 분기 수 (실적 카드와 맞춘다)


def quarter_label(ts):
    """2026-06-30 -> '26 2Q'. 회계연도가 아니라 기간 종료일 기준 달력 분기다."""
    q = (ts.month - 1) // 3 + 1
    return f"{ts.year % 100:02d} {q}Q"


OCF_ROWS = ["Operating Cash Flow", "OperatingCashFlow",
            "Cash Flow From Continuing Operating Activities",
            "Total Cash From Operating Activities"]

FCF_ROWS = ["Free Cash Flow", "FreeCashFlow"]


def _cf_row(cf, names):
    row = next((r for r in names if r in cf.index), None)
    return None if row is None else cf.loc[row].dropna()


def fetch_cash(ticker):
    """(CAPEX, 잉여현금흐름) 두 목록. 각각 [(분기라벨, 금액USD)] 오래된 것부터.

    잉여현금흐름은 야후가 항목으로 직접 주면 그 값을 쓰고, 없으면
    영업활동현금흐름에서 CAPEX를 뺀다. 두 값이 다 있는 분기만 계산한다
    (한쪽이 비면 0으로 채우지 않고 그 분기를 건너뛴다).
    """
    cf = yf.Ticker(ticker).quarterly_cashflow
    if cf is None or cf.empty:
        raise ValueError("빈 현금흐름표")

    cap = _cf_row(cf, CAPEX_ROWS)
    if cap is None or cap.empty:
        raise ValueError(f"CAPEX 항목 없음 (있는 항목 예: {list(cf.index)[:3]})")
    # 현금흐름표에서 지출은 음수로 들어온다. 크기만 쓴다.
    cap = cap.abs().sort_index()

    fcf = _cf_row(cf, FCF_ROWS)
    if fcf is not None and not fcf.empty:
        fcf = fcf.sort_index()
        fcf_list = [(quarter_label(ts), float(v)) for ts, v in fcf.items()][-QUARTERS:]
    else:
        ocf = _cf_row(cf, OCF_ROWS)
        if ocf is None or ocf.empty:
            fcf_list = []
        else:
            ocf = ocf.sort_index()
            fcf_list = [(quarter_label(ts), float(ocf[ts]) - float(cap[ts]))
                        for ts in ocf.index if ts in cap.index][-QUARTERS:]

    cap_list = [(quarter_label(ts), float(v)) for ts, v in cap.items()][-QUARTERS:]
    return cap_list, fcf_list


def bil(v):
    return f"${v / 1e9:.1f}B"


def pct_span(v):
    if v is None:
        return '<span class="needchk">확인 필요</span>'
    cls = "up" if v > 0 else ("down" if v < 0 else "flat")
    return f'<span class="{cls}">{v:+.1f}%</span>'




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


# 꺾은선 그래프 크기(SVG 좌표계). 실제 화면 폭은 CSS가 100%로 늘려준다.
CH_W, CH_H = 320.0, 100.0
CH_L, CH_R, CH_T, CH_B = 16.0, 16.0, 16.0, 16.0   # 위쪽은 값 글씨, 아래쪽은 분기 글씨 자리


def short(v, kind):
    """표식 옆에 붙일 짧은 숫자. 단위는 위의 큰 숫자에 이미 적혀 있다."""
    if kind == "pct":
        return f"{v:.1f}"
    if kind == "count":
        return f"{v / 1e3:.0f}"
    b = v / 1e9
    return f"{b:.0f}" if abs(b) >= 100 else f"{b:.1f}"


def fin_chart(vals, labs, fmt, kind):
    """표식이 있는 꺾은선. 값이 없는 분기는 선을 잇지 않고 비워 둔다."""
    known = [v for v in vals if v is not None]
    if not known:
        return '<div class="fin-nochart needchk">그릴 값이 없습니다</div>'

    lo, hi = min(known), max(known)
    if hi == lo:
        hi, lo = hi + 1, lo - 1
    pad = (hi - lo) * 0.12
    lo, hi = lo - pad, hi + pad
    # 세로축은 값의 범위에 맞춰 자동으로 잡는다. 0부터 그리지 않으므로 기울기만
    # 보고 크기를 판단하면 안 된다. 그래서 표식마다 실제 숫자를 같이 찍는다.

    n = len(vals)
    def px(i):
        return CH_L if n == 1 else CH_L + i * (CH_W - CH_L - CH_R) / (n - 1)
    def py(v):
        return CH_H - CH_B - (v - lo) / (hi - lo) * (CH_H - CH_T - CH_B)

    parts = []
    if any(v < 0 for v in known) and lo < 0 < hi:   # 적자 분기가 있을 때만 0선을 그린다
        parts.append(f'<line class="fin-zero" x1="0" y1="{py(0):.1f}" '
                     f'x2="{CH_W:.0f}" y2="{py(0):.1f}"/>')

    # 값이 끊긴 구간은 선을 잇지 않는다(없는 걸 이어 그리면 거짓말이 된다)
    seg = []
    for i, v in enumerate(vals):
        if v is None:
            if len(seg) > 1:
                parts.append(f'<polyline class="fin-line" points="{" ".join(seg)}"/>')
            seg = []
        else:
            seg.append(f"{px(i):.1f},{py(v):.1f}")
    if len(seg) > 1:
        parts.append(f'<polyline class="fin-line" points="{" ".join(seg)}"/>')

    for i, (v, lab) in enumerate(zip(vals, labs)):
        x = px(i)
        if v is None:
            parts.append(f'<text class="fin-xlab" x="{x:.1f}" y="{CH_H - 3:.1f}">{lab}</text>')
            continue
        y = py(v)
        last = " is-last" if i == n - 1 else ""
        parts.append(f'<circle class="fin-dot{last}" cx="{x:.1f}" cy="{y:.1f}" r="2.6">'
                     f'<title>{lab} {fmt(v)}</title></circle>')
        parts.append(f'<text class="fin-plab{last}" x="{x:.1f}" y="{y - 6:.1f}">'
                     f'{short(v, kind)}</text>')
        parts.append(f'<text class="fin-xlab" x="{x:.1f}" y="{CH_H - 3:.1f}">{lab}</text>')

    return (f'<svg class="fin-chart" viewBox="0 0 {CH_W:.0f} {CH_H:.0f}" '
            f'preserveAspectRatio="xMidYMid meet" role="img">' + "".join(parts) + "</svg>")


def fin_metric(label, vals, labs, fmt, chg_html, kind="money", chg_label="전년 동기 대비"):
    cur = vals[-1] if vals else None
    val_html = (f'<div class="fin-mval">{fmt(cur)}</div>' if cur is not None
                else '<div class="fin-mval needchk">확인 필요</div>')
    return ('            <div class="fin-metric">\n'
            f'              <div class="fin-mlabel">{label}</div>\n'
            f'              {val_html}\n'
            f'              <div class="fin-mchg">{chg_label} {chg_html}</div>\n'
            f'              {fin_chart(vals, labs, fmt, kind)}\n'
            '            </div>')


def yoy(vals):
    """전년 동기(4분기 전) 대비 증감률. 5개 분기가 없거나 값이 비면 None."""
    if len(vals) < 5 or vals[-1] is None or vals[-5] is None or not vals[-5]:
        return None
    return (vals[-1] / vals[-5] - 1) * 100


def fin_item(name, ticker, logo, series, cash):
    """cash는 fetch_cash 결과((CAPEX목록, FCF목록)) 또는 None."""
    labs = [q for q, _, _ in series]
    revs = [r for _, r, _ in series]
    ops = [o for _, _, o in series]
    mgs = [o / r * 100 for _, r, o in series]

    mg_pp = (mgs[-1] - mgs[-5]) if len(mgs) >= 5 else None

    # CAPEX는 현금흐름표라 분기 수가 손익계산서와 다를 수 있다.
    # 분기 라벨을 열쇠로 맞춰 붙이고, 없는 분기는 None으로 둔다(0으로 채우지 않는다).
    if cash:
        capex, fcflist = cash
        cmap, fmap = dict(capex), dict(fcflist)
        caps = [cmap.get(q) for q in labs]
        fcfs = [fmap.get(q) for q in labs]
        cap_chg = pct_span(yoy(caps))
        fcf_chg = pct_span(yoy(fcfs))
    else:
        caps = fcfs = [None] * len(labs)
        cap_chg = fcf_chg = '<span class="needchk">확인 필요</span>'

    logo_html = (f'<img class="supp-logo" src="https://logo.clearbit.com/{logo}" '
                 f"onerror=\"this.style.display='none'\">")
    tesla_html = tesla_extra_block(ticker, labs)
    return (
        '          <details class="fin-item">\n'
        f'            <summary class="fin-head">{logo_html}{name}'
        f'<span class="supp-ticker">{ticker}</span>'
        f'<span class="fin-q">{labs[-1]} 기준</span>'
        '<span class="fin-more">자세히 보기</span></summary>\n'
        '            <div class="fin-body">\n'
        '            <div class="fin-metrics">\n'
        + fin_metric("매출", revs, labs, bil, pct_span(yoy(revs))) + "\n"
        + fin_metric("영업이익", ops, labs, bil, pct_span(yoy(ops))) + "\n"
        + fin_metric("영업이익률", mgs, labs, lambda v: f"{v:.1f}%",
                     pp_span(mg_pp), kind="pct") + "\n"
        + fin_metric("설비투자(CAPEX)", caps, labs, bil, cap_chg) + "\n"
        + fin_metric("잉여현금흐름(FCF)", fcfs, labs, bil, fcf_chg) + "\n"
        '            </div>\n'
        + (tesla_html + "\n" if tesla_html else "")
        + cloud_block(ticker, labs) + "\n"
        + earncall_block(ticker, labs) + "\n"
        '            </div>\n'
        '          </details>'
    )


def fin_item_fail(name, ticker, logo, why):
    logo_html = (f'<img class="supp-logo" src="https://logo.clearbit.com/{logo}" '
                 f"onerror=\"this.style.display='none'\">")
    return ('          <div class="fin-item">\n'
            f'            <div class="fin-head">{logo_html}{name}'
            f'<span class="supp-ticker">{ticker}</span></div>\n'
            f'            <div class="fin-fail needchk">확인 필요 — {why}</div>\n'
            '          </div>')



# --------------------------------------------------- 클라우드(데이터센터 대여) 부문
#
# 부문별 매출은 야후 무료 데이터에 없다. 회사가 실적 발표에서만 공개하기 때문에
# 여기에 손으로 적어 둔다. 이 표는 자동으로 갱신되지 않는다.
#
# - 분기 라벨은 "기간 종료일 기준 달력 분기"다. 손익계산서 라벨과 규칙이 같으므로
#   회계연도가 다른 오라클(5월 결산)·마이크로소프트(6월 결산)도 같은 칸에 맞춰진다.
# - 새 분기 실적이 나오면 아래 표에 한 줄씩 손으로 추가해야 한다. 추가하지 않으면
#   화면에 "손익 최신 분기보다 이전 값"이라고 뜬다. 옛 값을 조용히 최신인 척
#   보여주지 않기 위한 장치다.
# - 마이크로소프트는 Azure 단독 매출 금액을 공개하지 않는다. 성장률(%)만 발표하므로
#   Azure만 mode="growth"로 두고 금액 자리를 비운다. 없는 금액을 만들어 내지 않는다.
# - 단위는 달러다(백만 달러 표기를 10억 단위 그래프가 쓰도록 1e6을 곱해 둔다).

_M = 1e6   # 아래 표는 백만 달러 단위로 적는다


CLOUD_SEG = {
    "AMZN": {
        "label": "AWS",
        "mode": "money",
        "rev": {"24 3Q": 27452, "24 4Q": 28786, "25 1Q": 29267, "25 2Q": 30873,
                "25 3Q": 33006, "25 4Q": 35579, "26 1Q": 37587, "26 2Q": 42232},
        "opi": {"24 3Q": 10447, "24 4Q": 10632, "25 1Q": 11547, "25 2Q": 10160,
                "25 3Q": 11434, "25 4Q": 12465, "26 1Q": 14161, "26 2Q": 16621},
        "src": "https://ir.aboutamazon.com/quarterly-results/",
        "srctxt": "아마존 실적 발표 세그먼트 표",
    },
    "GOOGL": {
        "label": "구글 클라우드",
        "mode": "money",
        "rev": {"24 3Q": 11353, "24 4Q": 11955, "25 1Q": 12260, "25 2Q": 13624,
                "25 3Q": 15157, "25 4Q": 17664, "26 1Q": 20028, "26 2Q": 24768},
        "opi": {"24 3Q": 1947, "24 4Q": 2093, "25 1Q": 2177, "25 2Q": 2826,
                "25 3Q": 3594, "25 4Q": 5313, "26 1Q": 6598, "26 2Q": 8814},
        "src": "https://abc.xyz/investor/",
        "srctxt": "알파벳 실적 발표 세그먼트 표",
    },
    "ORCL": {
        # 오라클은 회계연도가 5월에 끝난다. FY26 4분기(3~5월)가 달력 26 2Q에 들어간다.
        "label": "오라클 클라우드 인프라(OCI)",
        "mode": "money",
        "rev": {"24 3Q": 2154, "24 4Q": 2434, "25 1Q": 2652, "25 2Q": 2995,
                "25 3Q": 3347, "25 4Q": 4079, "26 1Q": 4888, "26 2Q": 5787},
        "opi": None,          # 오라클은 클라우드 부문 영업이익을 따로 공시하지 않는다
        "extra": "같은 분기 클라우드 전체(IaaS+SaaS) 매출 99.1억 달러, "
                 "수주잔고(RPO) 6,380억 달러",
        "src": "https://investor.oracle.com/",
        "srctxt": "오라클 실적 발표",
    },
    "MSFT": {
        "label": "Azure",
        "mode": "growth",
        # 마이크로소프트는 회계연도가 6월에 끝난다. FY26 4분기(4~6월)가 달력 26 2Q다.
        "growth": {"24 3Q": 33, "24 4Q": 31, "25 1Q": 33, "25 2Q": 39,
                   "25 3Q": 40, "25 4Q": 39, "26 1Q": 40, "26 2Q": 43},
        "src": "https://www.microsoft.com/en-us/investor/earnings/",
        "srctxt": "마이크로소프트 실적 발표",
    },
}


def cloud_block(ticker, labs):
    """손익 카드 아래에 붙는 클라우드 부문 줄. 해당 없는 종목이면 빈 문자열."""
    c = CLOUD_SEG.get(ticker)
    if not c:
        return ""

    if c["mode"] == "growth":
        src_map = c["growth"]
        vals = [src_map.get(q) for q in labs]
        gap = None
        if len(vals) >= 5 and vals[-1] is not None and vals[-5] is not None:
            gap = vals[-1] - vals[-5]
        metrics = fin_metric("Azure 성장률(전년 동기 대비)", vals, labs,
                             lambda v: f"{v:.0f}%", pp_span(gap), kind="pct",
                             chg_label="1년 전 성장률과 비교")
        caveat = ("마이크로소프트는 Azure 매출 <b>금액</b>을 공개하지 않습니다. "
                  "발표되는 성장률만 옮겨 적었습니다.")
    else:
        src_map = c["rev"]
        revs = [None if src_map.get(q) is None else src_map[q] * _M for q in labs]
        metrics = fin_metric(f'{c["label"]} 매출', revs, labs, bil, pct_span(yoy(revs)))
        if c.get("opi"):
            opis = [None if c["opi"].get(q) is None else c["opi"][q] * _M for q in labs]
            metrics += "\n" + fin_metric(f'{c["label"]} 영업이익', opis, labs,
                                         bil, pct_span(yoy(opis)))
        caveat = c.get("extra", "")

    # 이 표에 값이 들어 있는 마지막 분기. 손익 최신 분기보다 뒤처지면 그렇다고 적는다.
    have = [q for q in labs if src_map.get(q) is not None]
    if not have:
        return ('            <div class="fin-cloud">\n'
                f'              <div class="fin-cloud-head">클라우드 부문 — {c["label"]}</div>\n'
                '              <div class="fin-cloud-note needchk">확인 필요 — '
                '이 분기 구간의 공시 값이 아직 표에 없습니다</div>\n'
                '            </div>')

    stale = ("" if have[-1] == labs[-1] else
             f'<span class="needchk">손익 최신 분기({labs[-1]})보다 이전 값</span> · ')
    note = (f'{stale}기준 {have[-1]} · 회사 공시를 손으로 옮겨 적은 값이라 '
            f'자동 갱신되지 않습니다 · '
            f'<a href="{c["src"]}" target="_blank" rel="noopener">{c["srctxt"]}</a>')
    if caveat:
        note = caveat + " · " + note

    return ('            <div class="fin-cloud">\n'
            f'              <div class="fin-cloud-head">클라우드(데이터센터 대여) 부문 — '
            f'{c["label"]}</div>\n'
            '              <div class="fin-cmetrics">\n' + metrics + "\n"
            '              </div>\n'
            f'              <div class="fin-cloud-note">{note}</div>\n'
            '            </div>')


# --------------------------------------------------------- 테슬라 전용 — 인도량 · FSD 이익
#
# 인도량은 테슬라 공식 "분기 생산·인도" 보도자료 숫자를 그대로 옮겨 적었다(자동화 불가 —
# 야후에 없음). FSD 이익은 테슬라가 어디에도 공시하지 않는다: 10-Q의 이연수익 항목은
# FSD·커넥티비티·무료 슈퍼차저·OTA 업데이트가 전부 섞인 값이라 "FSD만의 값"이 아니고,
# 실적콜에서도 가입자 수만 언급할 뿐 매출/이익 금액은 밝히지 않는다. 그래서 지어내지
# 않고 확인 필요로 둔다 — 인터넷에 도는 "FSD 연매출 5.46억 달러" 같은 수치는 테슬라가
# 발표한 값이 아니라 외부 블로그의 추정 계산이라 쓰지 않았다.
TESLA_DELIVERIES = {
    "24 3Q": 462890, "24 4Q": 495570, "25 1Q": 336681, "25 2Q": 384122,
    "25 3Q": 497099, "25 4Q": 418227, "26 1Q": 358023, "26 2Q": 480126,
}
TESLA_DELIVERY_SRC = "https://ir.tesla.com/#quarterly-disclosure"


def cnt(v):
    return f"{v:,.0f}대"


def tesla_extra_block(ticker, labs):
    if ticker != "TSLA":
        return ""
    dels = [TESLA_DELIVERIES.get(q) for q in labs]
    have = [q for q in labs if TESLA_DELIVERIES.get(q) is not None]
    stale = ("" if (have and have[-1] == labs[-1]) else
             f'<span class="needchk">손익 최신 분기({labs[-1]})보다 이전 값</span> · ')
    metrics = fin_metric("분기 인도량", dels, labs, cnt, pct_span(yoy(dels)), kind="count")
    metrics += "\n" + fin_metric(
        "FSD(완전자율주행) 이익", [None] * len(labs), labs, cnt,
        '<span class="needchk">확인 필요</span>', kind="count")
    note = (f'{stale}인도량 기준 {have[-1] if have else "확인 필요"} · 테슬라 공식 분기 생산·인도 '
            f'보도자료를 손으로 옮겨 적은 값이라 자동 갱신되지 않습니다 · '
            f'<a href="{TESLA_DELIVERY_SRC}" target="_blank" rel="noopener">테슬라 인도량 발표</a>'
            ' · FSD 이익은 테슬라가 별도로 공시하지 않습니다(이연수익 항목은 FSD·커넥티비티·'
            '슈퍼차저·OTA가 섞인 값이라 FSD 단독 수치가 아님) — 그래서 확인 필요로 둡니다.')
    return ('            <div class="fin-cloud">\n'
            '              <div class="fin-cloud-head">테슬라 전용 지표 — 인도량 · FSD</div>\n'
            '              <div class="fin-cmetrics">\n' + metrics + "\n"
            '              </div>\n'
            f'              <div class="fin-cloud-note">{note}</div>\n'
            '            </div>')


# --------------------------------------------------------------- 어닝콜 요약 (수동 관리)
#
# 실적발표 콜(어닝콜)에서 경영진이 밝힌 가이던스·전략 코멘트 등은 손익계산서 숫자에
# 안 나오므로 손으로 요약해 둔다. 각 종목 카드를 펼치면 맨 아래에 붙는다. 새 분기 콜이
# 끝나면 이 표를 새로 채워야 하고, 안 채우면 "이전 어닝콜"이라고 화면에 표시된다.
# ("직접 인용"=원문 그대로 옮긴 발언, "요약"=콜 내용을 손으로 정리한 내용)
EARNCALL = {
    "AMZN": {"q": "26 2Q", "date": "2026-07-30",
        "guide": '2026년 CAPEX 가이던스 <b>$200B → $220B 상향</b> · 발표 다음날 주가 +15.3%',
        "lines": [
            ("quote", '앤디 재시: "2026년 현금 CAPEX로 약 2,200억 달러를 쓰게 될 것으로 봅니다."'),
            ("quote", '재시: "2026년 수요를 전부 감당할 만큼의 용량은 확보하지 못할 것입니다."'),
            ("summary", "상향의 주된 이유로 메모리 가격 상승을 지목했습니다."),
        ],
        "src": "https://www.investing.com/news/transcripts/earnings-call-transcript-amazon-tops-q2-2026-estimates-as-aws-growth-accelerates-93CH-4826442",
        "srctxt": "Investing.com 실적 콜 요약"},
    "GOOGL": {"q": "26 2Q", "date": "2026-07-22",
        "guide": '2026년 가이던스 <b>$180~190B → $195~205B 상향</b> · 발표 다음날 주가 −7.1%',
        "lines": [
            ("summary", "CFO 아나트 아슈케나지는 투자 확대에 따른 감가상각비 부담이 커진다는 점을 짚었습니다."),
            ("quote", 'CEO 순다르 피차이: AI 기회는 아직 "아주 초기 국면(very early innings)"이라고 표현했습니다.'),
            ("summary", "상장 이후 처음으로 잉여현금흐름이 마이너스로 돌아섰습니다."),
        ],
        "src": "https://www.investing.com/news/transcripts/earnings-call-transcript-alphabet-beats-q2-2026-estimates-shares-fall-on-capex-surge-93CH-4807140",
        "srctxt": "Investing.com 실적 콜 요약"},
    "MSFT": {"q": "26 2Q", "date": "2026-07-29",
        "guide": '2026년(달력) CAPEX 전망 <b>약 $190B → 약 $175B</b>. 단, 투자를 줄인 게 아니라 '
                 '<b>서버 내용연수를 15년→25년으로 바꾼 회계 변경</b> 영향입니다 · '
                 '다음 분기는 "500억 달러 이상" 안내 · 주가 약 +8%',
        "lines": [
            ("summary", "사티아 나델라는 올해 신규 데이터센터 31곳을 열어 총 88곳이 된다고 밝혔습니다."),
            ("quote", 'CFO 에이미 후드: "수요 환경이 바뀌면, 가장 큰 비중을 차지하는 항목의 속도를 늦추면 됩니다."'),
            ("summary", "2분기 실제 집행액은 현금 기준 $35.8B, 금융리스 포함 $41.0B입니다."),
        ],
        "src": "https://www.investing.com/news/transcripts/earnings-call-transcript-microsoft-q4-2026-beats-forecasts-stock-jumps-8-93CH-4822020",
        "srctxt": "Investing.com 실적 콜 요약"},
    "META": {"q": "26 2Q", "date": "2026-07-29",
        "guide": '2026년 가이던스 <b>$125~145B → $130~145B</b>. 상단은 그대로고 하단만 올라간 '
                 '<b>범위 축소</b>입니다(일부 언론의 "대폭 상향" 표현은 부정확) · 주가 약 −7~10%',
        "lines": [
            ("quote", '마크 저커버그: "그 위에 지능을 쌓아 올릴 수 있는데 단기 이익을 위해 연산 자원을 '
                      '전부 파는 건 어리석은 일입니다."'),
            ("summary", "잉여현금흐름이 $784M까지 줄었고, $24.9B 규모 회사채를 발행했습니다."),
            ("summary", "자사주 매입을 중단했습니다."),
        ],
        "src": "https://www.investing.com/news/transcripts/earnings-call-transcript-meta-misses-eps-in-q2-2026-as-stock-sinks-after-hours-93CH-4821910",
        "srctxt": "Investing.com 실적 콜 요약"},
    "NVDA": {"q": "26 2Q", "date": "2026-05-20",
        "guide": '자체 CAPEX 가이던스는 제시하지 않습니다(설비를 직접 짓는 회사가 아니라 고객사 '
                 '투자의 수혜 쪽입니다) · 해당 분기 집행액 $1.757B',
        "lines": [
            ("quote", '젠슨 황: "인류 역사상 가장 큰 인프라 확장인 AI 팩토리 구축이 놀라운 속도로 '
                      '가속되고 있습니다."'),
            ("summary", "중국向 H200 관련 매출은 가이던스에서 완전히 배제했습니다 — 수입 허용 여부가 불확실합니다."),
            ("summary", "이 어닝콜은 7월 실적 시즌이 아니라 5월 발표분(엔비디아 회계상 FY27 1분기)이라 "
                        "시점이 다릅니다 — 8월 26일 발표 후 갱신이 필요합니다."),
        ],
        "src": "https://www.fool.com/earnings/call-transcripts/2026/05/20/nvidia-nvda-q1-2027-earnings-transcript/",
        "srctxt": "The Motley Fool 실적 콜 전문"},
    "AAPL": {"q": "26 2Q", "date": "2026-07-30",
        "guide": 'CAPEX 가이던스를 제시하지 않습니다 · 9개월 누계 $6.799B로 전년 동기 $9.473B보다 '
                 '<b>감소</b> · 주가 약 −6.7%',
        "lines": [
            ("quote", '팀 쿡: "우리는 운영비를 늘려왔고 AI 전반에 더 많이 쓰고 있습니다. 꽤 많이요."'),
            ("summary", "다른 빅테크와 달리 자체 데이터센터 대신 외부 클라우드를 많이 쓰는 구조라 "
                        "CAPEX 규모 자체가 작습니다."),
            ("summary", "이번이 팀 쿡 CEO의 마지막 실적콜이었습니다 — 후임 CEO 존 터너스에게 신뢰를 표명했습니다."),
        ],
        "src": "https://sixcolors.com/post/2026/07/one-last-time-this-is-tim-transcript-of-apples-q3-2026-financial-call/",
        "srctxt": "Six Colors 실적 콜 전문"},
    "TSLA": {"q": "26 2Q", "date": "2026-07-22",
        "guide": '2026년 CAPEX 가이던스 <b>$25B 이상 유지</b>(변경 없음) · 2분기 집행액 $5.8B로 '
                 '전년 대비 +142%',
        "lines": [
            ("quote", '일론 머스크: "너무 낭비가 되지 않는 선에서, 쓸 수 있는 한 최대한 빨리 CAPEX를 '
                      '집행해야 합니다."'),
            ("quote", 'CFO 바이바브 타네자: "올해는 대규모 CAPEX의 해입니다."'),
            ("summary", "로보택시는 6개 도시에서 38만 마일 이상 무감독 주행, \"주목할 만한 사고 0건\"을 "
                        "기록했습니다 — 머스크는 확장 속도보다 신뢰성을 우선한다고 강조했습니다."),
        ],
        "src": "https://www.investing.com/news/transcripts/earnings-call-transcript-tesla-q2-2026-revenue-beats-eps-misses-as-stock-falls-93CH-4807216",
        "srctxt": "Investing.com 실적 콜 요약"},
    "ORCL": {"q": "26 2Q", "date": "2026-06-10",
        "guide": 'FY27 매출 성장률 가이던스 <b>고정환율 기준 +34%</b> · 1분기 클라우드 매출 성장률 '
                 '58~64% 제시',
        "lines": [
            ("summary", "잔여계약이행의무(RPO)가 전년비 363% 급증한 6,380억 달러로 사상 최대치를 "
                        "기록했습니다 — 4분기에만 670억 달러 규모의 AI 인프라 계약을 체결했습니다."),
            ("summary", "FY27 순현금 CapEx 지출은 약 700억 달러로 예상되며, GPU 가동률 97.5%·갱신율 "
                        "92%를 기록했습니다."),
        ],
        "src": "https://www.investing.com/news/transcripts/earnings-call-transcript-oracle-q4-2026-earnings-beat-expectations-despite-stock-dip-93CH-4736322",
        "srctxt": "Investing.com 실적 콜 요약"},
}

EARNCALL_DISCLAIMER = ("아마존·알파벳·마이크로소프트·메타는 회사 원문에 직접 접근하지 못해 제3자 "
                       "녹취를 거친 인용입니다 — 중요한 판단에는 출처의 회사 IR 원문을 확인하세요.")


def earncall_block(ticker, labs):
    e = EARNCALL.get(ticker)
    if not e:
        return ('            <div class="fin-earncall">\n'
                '              <div class="fin-cloud-head">어닝콜 요약</div>\n'
                '              <div class="fin-cloud-note needchk">확인 필요 — '
                '아직 요약을 정리하지 못했습니다</div>\n'
                '            </div>')
    stale = ("" if (labs and e["q"] == labs[-1]) else
             f'<span class="needchk">손익 최신 분기({labs[-1] if labs else "확인 필요"})보다 '
             '이전 어닝콜입니다</span> · ')
    lines_html = "".join(
        f'<li><span class="call-tag{" quote" if tag == "quote" else ""}">'
        f'{"직접 인용" if tag == "quote" else "요약"}</span> {text}</li>'
        for tag, text in e["lines"]
    )
    return ('            <div class="fin-earncall">\n'
            f'              <div class="fin-cloud-head">어닝콜 요약 — {e["q"]} ({e["date"]} 발표)</div>\n'
            f'              <div class="call-guide">{e["guide"]}</div>\n'
            f'              <ul class="call-lines">{lines_html}</ul>\n'
            f'              <div class="fin-cloud-note">{stale}자동 갱신되지 않는 수기 요약입니다. '
            f'{EARNCALL_DISCLAIMER} · '
            f'<a href="{e["src"]}" target="_blank" rel="noopener">{e["srctxt"]}</a></div>\n'
            '            </div>')


def build_fin():
    items, ok, cok = [], 0, 0
    for name, ticker, logo in BIGTECH:
        # 현금흐름표는 따로 받는다. 이쪽이 실패해도 매출·영업이익은 그대로 보여준다.
        try:
            cash = fetch_cash(ticker)
            cok += 1
        except Exception as e:
            print(f"  [warn] 현금흐름 {ticker}: {e}", file=sys.stderr)
            cash = None
        try:
            items.append(fin_item(name, ticker, logo, fetch_fin(ticker), cash))
            ok += 1
        except Exception as e:
            print(f"  [warn] 재무 {ticker}: {e}", file=sys.stderr)
            items.append(fin_item_fail(name, ticker, logo, "분기 손익계산서를 못 받아왔습니다"))
    print(f"  fin {ok}/{len(BIGTECH)} (cash {cok}/{len(BIGTECH)})")
    return '        <div class="fin-grid">\n' + "\n".join(items) + "\n        </div>"

# ------------------------------------------------------------- 주요 지수 카드

# (표시이름, 짧은라벨, 야후심볼, 트레이딩뷰심볼, 소수점자리)
# 2년물 금리·하이일드 스프레드는 야후에 없어 FRED(세인트루이스 연은) 공개 CSV에서 받는다.
# 심볼 자리에 "FRED:xxx"를 적어두면 fetch_fred()가 별도로 받아 closes 딕셔너리에 합쳐준다.
INDEXES = [
    ("S&amp;P500", "SPX", "^GSPC", "FOREXCOM:SPXUSD", 2),
    ("나스닥 종합", "IXIC", "^IXIC", "NASDAQ:IXIC", 2),
    ("다우존스", "DJI", "^DJI", "FOREXCOM:DJI", 2),
    ("VIX 공포지수", "VIX", "^VIX", "TVC:VIX", 2),
    ("코스피", "KOSPI", "^KS11", "KRX:KOSPI", 2),
    ("코스닥", "KOSDAQ", "^KQ11", "KRX:KOSDAQ", 2),
    ("원달러 환율", "USDKRW", "KRW=X", "FX_IDC:USDKRW", 2),
    ("미 10년물 금리", "US10Y", "^TNX", "TVC:US10Y", 3),
    # "매크로·심리" 탭에서 이미 쓰고 있는 것과 같은 심볼(2년물 국채 수익률 선물)로 맞춘다.
    ("미 2년물 금리", "US02Y", "2YY=F", "TVC:US02Y", 3),
    ("달러 인덱스", "DXY", "DX-Y.NYB", "TVC:DXY", 2),
    ("하이일드 스프레드", "HY OAS", "FRED:BAMLH0A0HYM2", "FRED:BAMLH0A0HYM2", 2),
]

FRED_SYMS = [sym for _, _, sym, _, _ in INDEXES if sym.startswith("FRED:")]


def _fred_get(url, timeout):
    req = urllib.request.Request(url, headers={
        "User-Agent": UA,
        "Accept": "text/csv,text/plain,*/*",
        "Accept-Language": "en-US,en;q=0.9",
        # 압축을 안 받으면 응답이 커져서 느린 회선에서 더 잘 끊긴다
        "Accept-Encoding": "identity",
        "Connection": "close",
    })
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read().decode("utf-8", "replace")


def _fred_parse_csv(raw):
    """fredgraph.csv 형식: 첫 줄이 헤더, 결측치는 "."."""
    df = pd.read_csv(io.StringIO(raw))
    if df.shape[1] < 2:
        raise ValueError("CSV 열 부족")
    date_col, val_col = df.columns[0], df.columns[1]
    df[date_col] = pd.to_datetime(df[date_col], errors="coerce")
    df[val_col] = pd.to_numeric(df[val_col], errors="coerce")
    df = df.dropna(subset=[date_col, val_col]).set_index(date_col).sort_index()
    return df[val_col]


def _fred_parse_txt(raw):
    """fred.stlouisfed.org/data/{id}.txt 형식: 설명 블록 뒤에 "날짜  값" 줄이 이어진다."""
    dates, vals = [], []
    for line in raw.splitlines():
        m = re.match(r"^\s*(\d{4}-\d{2}-\d{2})\s+(\S+)\s*$", line)
        if m:
            dates.append(m.group(1))
            vals.append(m.group(2))
    if not dates:
        raise ValueError("txt에서 날짜 줄을 못 찾음")
    s = pd.Series(pd.to_numeric(vals, errors="coerce"),
                  index=pd.to_datetime(dates)).dropna().sort_index()
    return s


def fetch_fred(series_id):
    """FRED(세인트루이스 연은) 공개 데이터에서 일별 시계열을 받는다. API 키가 필요 없다.

    휴장일·미발표일은 값이 "."로 들어오는데, 이런 결측치는 만들어 채우지 않고
    그냥 건너뛴다(dropna). 끝까지 못 받으면 예외를 던지고, 호출부에서 "확인 필요"로
    처리한다 — 값을 지어내지 않는다.

    2026-08-05 Actions 로그에서 "The read operation timed out"으로 하이일드 스프레드가
    비어 있었다. 차단(403)이 아니라 응답이 느려서 끊긴 것이라, 다음 세 가지를 넣었다.
      1) cosd로 최근 5년만 요청해서 응답 크기를 줄인다 (전체는 1996년부터라 훨씬 크다)
      2) 시간 제한을 늘려가며 재시도한다
      3) csv가 계속 느리면 같은 값을 주는 /data/{id}.txt 주소로 갈아탄다
    전체 소요가 DEADLINE을 넘기면 더 붙잡지 않고 포기한다 (Actions를 오래 세워두지 않으려고).
    """
    cosd = (datetime.date.today() - datetime.timedelta(days=5 * 365)).isoformat()
    routes = [
        (f"https://fred.stlouisfed.org/graph/fredgraph.csv?id={series_id}&cosd={cosd}",
         _fred_parse_csv, "csv(5년)"),
        (f"https://fred.stlouisfed.org/data/{series_id}.txt",
         _fred_parse_txt, "txt"),
        (f"https://fred.stlouisfed.org/graph/fredgraph.csv?id={series_id}",
         _fred_parse_csv, "csv(전체)"),
    ]
    DEADLINE = 150  # 초
    started = time.monotonic()
    errors = []
    attempt = 0
    for timeout in (20, 40, 60):
        for url, parse, tag in routes:
            if time.monotonic() - started > DEADLINE:
                errors.append(f"{DEADLINE}초 초과로 중단")
                break
            attempt += 1
            try:
                s = parse(_fred_get(url, timeout))
                if s.empty:
                    raise ValueError("빈 시계열")
                if attempt > 1:
                    print(f"  FRED {series_id}: {attempt}번째 시도({tag}, {timeout}초)에서 성공")
                return s
            except Exception as e:
                errors.append(f"{tag}/{timeout}s {type(e).__name__}: {e}")
        else:
            if time.monotonic() - started < DEADLINE:
                time.sleep(3)
            continue
        break
    raise RuntimeError(f"{attempt}회 재시도 실패 — " + " | ".join(errors[-3:]))


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


# --------------------------------------------------- 거시 이벤트 (FOMC·BOJ·한은·테슬라 인도량)
#
# 회사별 실적일과 달리 이 날짜들은 야후에 없어서 손으로 적어 둔다. 전부 각 기관
# 공식 발표 기준이며, 미국(FOMC)·일본(BOJ)은 한국시간(KST)으로 환산했다.
#   - FOMC: 회의 이틀째 현지시각 오후 2시(14:00 ET) 발표 → 서머타임(EDT, UTC-4)이면
#     KST로 다음날 03:00, 이미 해제된 12월(EST, UTC-5)이면 다음날 04:00.
#   - BOJ: 일본도 한국과 같은 UTC+9라 환산이 필요 없다. 회의 이틀째 발표.
#   - 한국은행: 이미 KST.
#   - 테슬라 인도량: 공식 사전 예고가 없다. 최근 분기(26년 1·2분기)가 전부 분기
#     마감 이틀 뒤(4/2, 7/2)에 나온 걸 근거로 다음 분기도 같은 패턴일 거라 "예상"
#     표시한다(별표 처리, 확정 아님).
# 새해로 넘어가면(특히 FOMC 1월 회의 전) 다음 해 일정을 새로 찾아 추가해야 한다 —
# 안 그러면 그 달은 조용히 칩이 안 뜨는 것뿐이라(에러가 안 남) 놓치기 쉽다.
MACRO_EVENTS = [
    # (날짜, 칩에 쓸 짧은 라벨, 확정 여부)
    (datetime.date(2026, 8, 27), "한은 금통위", True),
    (datetime.date(2026, 9, 17), "FOMC", True),
    (datetime.date(2026, 9, 18), "BOJ", True),
    (datetime.date(2026, 10, 2), "테슬라 인도량*", False),
    (datetime.date(2026, 10, 22), "한은 금통위", True),
    (datetime.date(2026, 10, 29), "FOMC", True),
    (datetime.date(2026, 10, 30), "BOJ", True),
    (datetime.date(2026, 11, 26), "한은 금통위", True),
    (datetime.date(2026, 12, 10), "FOMC", True),
    (datetime.date(2026, 12, 18), "BOJ", True),
]


def build_earn_cal(rows):
    """이번 달과 다음 달 달력을 그린다. 칩은 짧은 라벨만, 미확정이면 * 를 붙인다.

    회사 실적(주황 칩)과 FOMC·BOJ·한은·테슬라 인도량 같은 거시 이벤트(파란 칩)를
    같은 칸에 같이 그린다.
    """
    import calendar as _cal
    by_day = {}
    for d, _name, short, confirmed in rows:
        by_day.setdefault(d, []).append((short + ("" if confirmed else "*"), "earn"))
    for d, short, confirmed in MACRO_EVENTS:
        by_day.setdefault(d, []).append((short if confirmed else short, "macro"))

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
            chips = "".join(
                f'<div class="cal-chip{" macro" if kind == "macro" else ""}">{c}</div>'
                for c, kind in by_day.get(d, [])
            )
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
        ({sym for rows in SECTIONS.values() for _, _, _, sym, _ in rows}
         | {sym for _, _, sym, _, _ in INDEXES}      # 개요 탭 주요 지수 카드
         | {KR_BOND_ETF})                            # 한국 심리지수 계산용
        - set(FRED_SYMS)   # FRED 심볼은 야후가 아니라 fetch_fred()로 따로 받는다
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

    # 사상 최고가(전체 기간 최고 종가)는 위의 15개월치로는 알 수 없어서 따로 받는다.
    # 여기서 실패해도 표 전체가 죽으면 안 되므로, 실패하면 aths를 비워 두고
    # "사상최고 대비" 칸만 확인 필요로 남긴다 — 값을 만들어 채우지 않는다.
    print("downloading all-time history for 사상최고...")
    aths = {}
    try:
        hist = yf.download(all_syms, period="max", interval="1d",
                           auto_adjust=True, progress=False, group_by="ticker",
                           threads=True)
        for sym in all_syms:
            try:
                s = (hist[sym]["Close"] if isinstance(hist.columns, pd.MultiIndex)
                     else hist["Close"]).dropna()
                if not s.empty:
                    aths[sym] = float(s.max())
            except Exception:
                pass
        print(f"  사상최고 확보 {len(aths)}/{len(all_syms)}")
    except Exception as e:
        print(f"  [warn] 전체 기간 시세 실패: {e}", file=sys.stderr)

    print(f"downloading {len(FRED_SYMS)} FRED series...")
    for sym in FRED_SYMS:
        try:
            closes[sym] = fetch_fred(sym.split(":", 1)[1])
        except Exception as e:
            print(f"  [warn] no data for {sym}: {e}", file=sys.stderr)

    with open(html_path, encoding="utf-8") as f:
        html = f.read()

    ok_count = 0
    for section, rows in SECTIONS.items():
        body = "\n".join(make_row(*row, closes, aths) for row in rows)
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
          f"{len(closes)}/{len(all_syms) + len(FRED_SYMS)} symbols fetched, "
          f"idx={'ok' if idx_ok else 'MARKER MISSING'}, "
          f"earn={'ok' if ecal_ok and elist_ok else 'MARKER MISSING'}({len(earn_rows)}건), "
          f"fng={'ok' if fng_ok else 'MARKER MISSING'}, "
          f"yield={'ok' if yld_ok else 'MARKER MISSING'}, "
          f"fin={'ok' if fin_ok else 'MARKER MISSING'}, date={today}")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "index.html")
