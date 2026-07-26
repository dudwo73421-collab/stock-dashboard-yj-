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
데이터를 못 받아온 종목은 값을 지어내지 않고 "확인 필요"로 표기한다.
"""
import sys
import datetime
import math

import pandas as pd
import yfinance as yf

# (표시이름, 티커라벨, 로고도메인 또는 None, 야후심볼, 기술등급 계산 여부)
SECTIONS = {
    "us30": [
        ("엔비디아", "NVDA", "nvidia.com", "NVDA", True),
        ("애플", "AAPL", "apple.com", "AAPL", True),
        ("마이크로소프트", "MSFT", "microsoft.com", "MSFT", True),
        ("알파벳", "GOOGL", "abc.xyz", "GOOGL", True),
        ("아마존", "AMZN", "amazon.com", "AMZN", True),
        ("메타", "META", "meta.com", "META", True),
        ("테슬라", "TSLA", "tesla.com", "TSLA", True),
        ("TSMC", "TSM", "tsmc.com", "TSM", True),
        ("브로드컴", "AVGO", "broadcom.com", "AVGO", True),
        ("버크셔해서웨이", "BRK.B", "berkshirehathaway.com", "BRK-B", True),
        ("일라이릴리", "LLY", "lilly.com", "LLY", True),
        ("마이크론", "MU", "micron.com", "MU", True),
        ("JP모건", "JPM", "jpmorganchase.com", "JPM", True),
        ("월마트", "WMT", "walmart.com", "WMT", True),
        ("AMD", "AMD", "amd.com", "AMD", True),
        ("비자", "V", "visa.com", "V", True),
        ("ASML", "ASML", "asml.com", "ASML", True),
        ("엑슨모빌", "XOM", "exxonmobil.com", "XOM", True),
        ("존슨앤존슨", "JNJ", "jnj.com", "JNJ", True),
        ("인텔", "INTC", "intel.com", "INTC", True),
        ("마스터카드", "MA", "mastercard.com", "MA", True),
        ("애브비", "ABBV", "abbvie.com", "ABBV", True),
        ("시스코", "CSCO", "cisco.com", "CSCO", True),
        ("어플라이드머티리얼즈", "AMAT", "appliedmaterials.com", "AMAT", True),
        ("코스트코", "COST", "costco.com", "COST", True),
        ("캐터필러", "CAT", "caterpillar.com", "CAT", True),
        ("램리서치", "LRCX", "lamresearch.com", "LRCX", True),
        ("쉐브론", "CVX", "chevron.com", "CVX", True),
        ("오라클", "ORCL", "oracle.com", "ORCL", True),
        ("ARM", "ARM", "arm.com", "ARM", True),
    ],
    "kr10": [
        ("삼성전자", "005930", "samsung.com", "005930.KS", True),
        ("SK하이닉스", "000660", "skhynix.com", "000660.KS", True),
        ("LG에너지솔루션", "373220", "lgensol.com", "373220.KS", True),
        ("삼성바이오로직스", "207940", "samsungbiologics.com", "207940.KS", True),
        ("현대차", "005380", "hyundai.com", "005380.KS", True),
        ("KB금융", "105560", "kbfg.com", "105560.KS", True),
        ("삼성물산", "028260", "samsungcnt.com", "028260.KS", True),
        ("삼성생명", "032830", "samsunglife.com", "032830.KS", True),
        ("삼성전기", "009150", "samsungsem.com", "009150.KS", True),
        ("SK스퀘어", "402340", "sksquare.com", "402340.KS", True),
    ],
    "etf": [
        ("VOO", "VOO", "vanguard.com", "VOO", True),
        ("IVV", "IVV", "ishares.com", "IVV", True),
        ("SPY", "SPY", "ssga.com", "SPY", True),
        ("VTI", "VTI", "vanguard.com", "VTI", True),
        ("QQQ", "QQQ", "invesco.com", "QQQ", True),
        ("VEA", "VEA", "vanguard.com", "VEA", True),
        ("VUG", "VUG", "vanguard.com", "VUG", True),
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


def main(html_path):
    all_syms = sorted({sym for rows in SECTIONS.values() for _, _, _, sym, _ in rows})
    print(f"downloading {len(all_syms)} symbols...")
    data = yf.download(all_syms, period="15mo", interval="1d",
                       auto_adjust=False, progress=False, group_by="ticker", threads=True)

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

    today = datetime.date.today().isoformat()
    ds, de = "<!--SUPPDATE-->", "<!--/SUPPDATE-->"
    i, j = html.find(ds), html.find(de)
    if i != -1 and j != -1:
        html = html[: i + len(ds)] + f"{today} (자동)" + html[j:]

    with open(html_path, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"updated {ok_count}/{len(SECTIONS)} sections, "
          f"{len(closes)}/{len(all_syms)} symbols fetched, date={today}")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "index.html")
