# -*- coding: utf-8 -*-
"""
대시보드 보조 지표 자동 갱신 스크립트 (GitHub Actions에서 매일 실행됨)

index.html 안의 <!--SUPP:섹션:START--> ~ <!--SUPP:섹션:END--> 사이를
야후 파이낸스 일봉 데이터로 계산한 최신 값으로 갈아끼운다.

계산 지표 (열 순서 = 화면 순서, 기간이 이어지도록 일간→주간→YTD를 붙여 놓았다):
  일간          : 직전 거래일 종가 대비 현재 종가
  주간          : 5거래일 전 종가 대비
  26년 YTD      : 전년도 마지막 종가 대비
  52주 고점대비 : 최근 52주(252거래일) 최고 종가 대비 현재 종가
  사상최고 대비 : 상장 이후 전체 기간 최고 종가 대비 현재 종가
  연속      : 연속 상승/하락 일수
  RSI(14)   : Wilder 방식
  이평선    : 5·20·60·120일 이동평균선 위(▲)/아래(▼), 데이터 부족은 –

개요 탭 지수 카드(<!--IDX-->)를 펼치면 같은 지표가 나온다 — 없어진 매크로·심리
탭의 표가 하던 역할이다.

또 <!--FNG:START--> ~ <!--FNG:END--> 사이에 공포·탐욕 지수 두 개를 갈아끼운다.
  미국 주식 : CNN Fear & Greed Index
  암호화폐  : alternative.me Crypto Fear & Greed Index
둘 중 하나만 실패해도 그쪽만 "확인 필요"로 표시하고 나머지는 정상 표기한다.

가격은 액면분할·배당이 보정된 수정주가(auto_adjust=True)를 쓴다.
날짜 표기는 한국시간 기준이다.
데이터를 못 받아온 종목은 값을 지어내지 않고 "확인 필요"로 표기한다.
"""
import sys
import os
import io
import json
import re
import datetime
import math
import time
import urllib.request

import pandas as pd
import yfinance as yf

try:
    from zoneinfo import ZoneInfo
except Exception:                      # 파이썬 3.8 이하에서도 죽지는 않게
    ZoneInfo = None

KST = datetime.timezone(datetime.timedelta(hours=9))

# 사상최고 값을 저장해 두는 파일. 저장소 루트에 같이 커밋된다.
# 전체 기간(period="max") 조회는 102종목이라 4분 가까이 걸려서, 2시간마다 돌 때마다
# 매번 받으면 야후 쪽에 부담이 크다. 그래서 하루 한 번만 새로 받고, 나머지 실행에서는
# 저장된 값과 최근 15개월치 중 큰 값을 쓴다 — 15개월 창이 하루 간격보다 훨씬 넓으니
# 이렇게 이어붙여도 값이 새지 않는다(근사가 아니라 정확히 같은 값).
ATH_CACHE = "ath_cache.json"

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
        # ── 2026-08-15 TOP60 확장: 샌디스크(당시 미국 49위, 약 $240B)까지 보이게
        #    시총 45~60위 구간에서 빠져 있던 종목을 채웠다. 출처: companiesmarketcap.com
        ("샌디스크", "SNDK", "sandisk.com", "SNDK", True),
        ("웰스파고", "WFC", "wellsfargo.com", "WFC", True),
        ("텍사스인스트루먼트", "TXN", "ti.com", "TXN", True),
        ("아리스타네트웍스", "ANET", "arista.com", "ANET", True),
        ("씨티그룹", "C", "citigroup.com", "C", True),
        ("아메리칸익스프레스", "AXP", "americanexpress.com", "AXP", True),
        ("암젠", "AMGN", "amgen.com", "AMGN", True),
        ("크라우드스트라이크", "CRWD", "crowdstrike.com", "CRWD", True),
        ("IBM", "IBM", "ibm.com", "IBM", True),
        ("써모피셔", "TMO", "thermofisher.com", "TMO", True),
        # ── 2026-08-31 TOP75 확장. 미국 시총 1~75위를 다 채웠다(외국 기업 6개는
        #    그대로 두고 "해외" 표시를 붙였다). 출처 companiesmarketcap USA 목록,
        #    2026-08-28 종가 기준. 팔로알토네트웍스(39위)는 확장이 아니라 그동안
        #    빠져 있던 것을 메운 것이다.
        ("팔로알토네트웍스", "PANW", "paloaltonetworks.com", "PANW", True),
        ("세일즈포스", "CRM", "salesforce.com", "CRM", True),
        ("버라이즌", "VZ", "verizon.com", "VZ", True),
        ("마벨", "MRVL", "marvell.com", "MRVL", True),
        ("애보트", "ABT", "abbott.com", "ABT", True),
        ("티모바일", "TMUS", "t-mobile.com", "TMUS", True),
        ("앰페놀", "APH", "amphenol.com", "APH", True),
        ("펩시코", "PEP", "pepsico.com", "PEP", True),
        ("찰스슈왑", "SCHW", "schwab.com", "SCHW", True),
        ("블랙록", "BLK", "blackrock.com", "BLK", True),
        ("맥도날드", "MCD", "mcdonalds.com", "MCD", True),
        ("디즈니", "DIS", "thewaltdisneycompany.com", "DIS", True),
        ("유니온퍼시픽", "UNP", "up.com", "UNP", True),
        ("길리어드", "GILD", "gilead.com", "GILD", True),
        ("AT&amp;T", "T", "att.com", "T", True),
        ("서던코퍼", "SCCO", "southerncoppercorp.com", "SCCO", True),
        ("퀄컴", "QCOM", "qualcomm.com", "QCOM", True),
        ("아나로그디바이스", "ADI", "analog.com", "ADI", True),
        ("웰타워", "WELL", "welltower.com", "WELL", True),
        ("넥스트에라에너지", "NEE", "nexteraenergy.com", "NEE", True),
        ("블랙스톤", "BX", "blackstone.com", "BX", True),
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
}
# 매크로·심리 탭은 없앴다(2026-08-08, 영재님 요청). 달러인덱스·원달러·WTI·브렌트·금·
# 비트코인은 개요 탭의 지수 카드(INDEXES)로 옮겨서, 카드를 누르면 일간·주간·YTD 같은
# 보조지표가 차트와 같이 펼쳐진다. 국채 금리 카드와 경제 캘린더도 개요 탭으로 갔다.

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
    v = float(val.iloc[-1])
    # 14일 내내 종가가 같으면(거래정지·상한가 고정 등) 0/0이라 nan이 나온다.
    # 그대로 두면 화면에 "nan"이라고 찍히므로 없는 값으로 돌려준다.
    return v if math.isfinite(v) else None


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

    # 252거래일(약 1년)이 안 되는 종목은 "52주 고점/저점"을 계산하지 않는다.
    # 상장한 지 두 달 된 종목의 46일치 최고가를 "52주 고점"이라고 적으면 거짓이다.
    # 이평선(mas)이 데이터가 모자라면 "–"로 두는 것과 같은 원칙.
    full_year = len(close) >= 252
    win = close.tail(252)
    high52 = float(win.max()) if full_year else None
    low52 = float(win.min()) if full_year else None
    drawdown = (last / high52 - 1) * 100 if high52 else None
    # 52주 저점 대비 상승률 — 고점대비만 있으면 "바닥에서 얼마나 올라왔나"가 안 보인다
    up52 = (last / low52 - 1) * 100 if low52 else None

    ath_dd = None
    if ath is not None and ath > 0:
        # 전체 기간 최고값은 최근 1년 최고값보다 낮을 수 없다. 낮게 나오면
        # 전체 기간 시세를 제대로 못 받은 것이므로 큰 쪽을 쓴다.
        base = max(ath, high52) if high52 else max(ath, float(win.max()))
        ath_dd = (last / base - 1) * 100

    week = (last / float(close.iloc[-6]) - 1) * 100 if len(close) >= 6 else None

    # YTD 기준은 "실행한 날의 연도"가 아니라 "이 시세의 마지막 거래일 연도"다.
    # 1월 1일 한국시간에 돌리면 미국 시세는 아직 작년이라, KST 연도로 라벨을 붙이면
    # 작년 한 해 수익률에 새해 연도가 붙는다.
    this_year = int(close.index[-1].year)
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

    # 이동평균선 위/아래. 5·20·60·120일선 각각에 대해 현재 종가가 위면 True.
    # 상장한 지 얼마 안 돼 데이터가 모자라는 선은 None으로 두고 화면에 "–"로 표시한다.
    mas = [(n, (last > float(close.tail(n).mean())) if len(close) >= n else None)
           for n in (5, 20, 60, 120)]

    rating = None
    if rate and len(close) >= 200:
        ma20 = float(close.tail(20).mean())
        ma50 = float(close.tail(50).mean())
        ma200 = float(close.tail(200).mean())
        score = int(last > ma20) + int(last > ma50) + int(last > ma200) + int(ma50 > ma200)
        rating = RATING_LABEL[score]
    return (day, drawdown, ath_dd, week, ytd, (streak, direction), rsi, mas,
            up52, this_year, low52, high52)


def pick_valuation(info):
    """야후 info에서 PER·선행PER·PBR·ROE·부채비율을 뽑는다.

    단위 주의 — yfinance는 판(version)에 따라 같은 항목을 비율로도, %로도 준다.
    지어내는 것보다 안 쓰는 게 낫다는 원칙에 따라, 상식 범위를 벗어나는 값은
    받아들이지 않고 그 칸을 비워 "확인 필요"로 남긴다.
      - returnOnEquity : 보통 비율(0.35 = 35%). 절댓값이 10을 넘으면 이미 %로 온
        것으로 보고 그대로 쓴다. 그래도 ±1000%를 넘으면 버린다.
      - debtToEquity   : 보통 %(154.2 = 154%). 5 미만이면 비율로 온 것으로 본다
        (부채비율이 5% 미만인 상장사는 사실상 없다시피 하므로).
    """
    out = {}

    def num(key):
        v = info.get(key)
        return float(v) if isinstance(v, (int, float)) and math.isfinite(v) else None

    for k, src in (("trailing", "trailingPE"), ("forward", "forwardPE"),
                   ("pbr", "priceToBook")):
        v = num(src)
        if v is not None:
            out[k] = v

    roe = num("returnOnEquity")
    if roe is not None:
        roe = roe if abs(roe) > 10 else roe * 100     # 비율로 왔으면 %로 바꾼다
        if abs(roe) <= 1000:
            out["roe"] = roe

    de = num("debtToEquity")
    if de is not None and de >= 0:
        de = de * 100 if de < 5 else de               # 비율로 왔으면 %로 바꾼다
        if de <= 100000:
            out["de"] = de
    return out


def ratio_cell(v, unit="배", digits=1, hi=None, tip=None):
    """PBR처럼 배수로 읽는 값. 음수는 배수로 비교할 수 없어 숫자로 적지 않는다."""
    if v is None or (isinstance(v, float) and math.isnan(v)):
        return '<td class="needchk">확인 필요</td>'
    if v <= 0:
        return '<td class="na" title="자본이 마이너스라 배수로 비교할 수 없습니다">해당 없음</td>'
    if hi and v > hi:
        return f'<td class="na" title="{v:,.0f}{unit} — 배수가 의미를 잃는 구간입니다">{hi:,.0f}{unit} 초과</td>'
    t = f' title="{tip}"' if tip else ""
    return f"<td{t}>{v:,.{digits}f}{unit}</td>"


def pct_val_cell(v, digits=1, tip=None, color=False):
    """ROE·부채비율처럼 이미 %인 값."""
    if v is None or (isinstance(v, float) and math.isnan(v)):
        return '<td class="needchk">확인 필요</td>'
    cls = ""
    if color:
        cls = ' class="up"' if v > 0 else (' class="down"' if v < 0 else "")
    t = f' title="{tip}"' if tip else ""
    return f"<td{cls}{t}>{v:,.{digits}f}%</td>"


def range_cell(low, high, last):
    """52주 저점~고점 사이 현재 위치. 숫자 두 개를 막대 하나로 합쳐 보여준다.
    0%면 52주 저점, 100%면 52주 신고가."""
    if low is None or high is None or high <= low:
        return '<td class="needchk">확인 필요</td>'
    pos = (last - low) / (high - low) * 100
    pos = max(0.0, min(100.0, pos))
    return ('<td class="rng-td" title="52주 저점 대비 현재 위치 — '
            f'0%가 52주 최저 종가, 100%가 52주 최고 종가입니다">'
            f'<span class="rng"><i style="left:{pos:.1f}%"></i></span>'
            f'<b class="rng-v">{pos:.0f}%</b></td>')


# 펼친 표 13칸이 라벨/값 쌍으로 쭉 나열되니 뭐가 뭔지 안 읽힌다는 지적(2026-08-17).
# 성격이 같은 것끼리 네 묶음으로 나누고, 묶음 제목 줄을 사이에 넣는다.
# 이 제목 칸도 진짜 <td>라서 <thead>에 짝이 되는 <th>가 있어야 열 수가 맞는다.
SUPP_GROUPS = ["가격 위치", "밸류에이션 · 재무", "거래", "기술 지표"]


def grp_cell(title):
    return f'<td class="supp-grp">{title}</td>'


def rsi_cell(v):
    if v is None:
        return '<td class="needchk">확인 필요</td>'
    return f"<td>{v:.1f}</td>"


def na_cell(why):
    """해당 없음 — 못 받아온 것("확인 필요")과 구분한다. ETF의 PER 같은 경우."""
    return f'<td class="na" title="{why}">–</td>'


def per_cell(v):
    """PER. 적자면 야후가 값을 아예 안 주거나 음수를 주는데, 음수 PER은 배수로
    비교할 수 있는 값이 아니라 숫자로 적지 않고 "적자"로 표시한다."""
    if v is None or (isinstance(v, float) and math.isnan(v)):
        return '<td class="needchk">확인 필요</td>'
    if v <= 0:
        return '<td class="na" title="순이익이 적자라 PER을 배수로 비교할 수 없습니다">적자</td>'
    if v > 400:
        return (f'<td class="na" title="{v:,.0f}배 — 이익이 거의 0에 가까워 '
                '배수가 의미를 잃는 구간입니다">400배 초과</td>')
    return f"<td>{v:,.1f}배</td>"


def is_intraday(sym, bar_date):
    """그 종목의 마지막 봉이 아직 진행 중인 장의 것인지."""
    if sym.endswith((".KS", ".KQ")):
        tz, ch, cm = "Asia/Seoul", 15, 30
    else:
        tz, ch, cm = "America/New_York", 16, 0
    try:
        now = datetime.datetime.now(ZoneInfo(tz))
        return bar_date == now.date() and (now.hour, now.minute) < (ch, cm)
    except Exception:
        return False


def turnover_cell(v, cur, intraday=False):
    """거래대금. 원/달러 단위를 섞지 않도록 통화 기호를 같이 적는다."""
    if v is None or (isinstance(v, float) and math.isnan(v)) or v <= 0:
        return '<td class="needchk">확인 필요</td>'
    if cur == "KRW":
        txt = (f"{v / 1e12:.2f}조원" if v >= 1e12 else f"{v / 1e8:,.0f}억원")
    else:
        txt = (f"${v / 1e9:.2f}B" if v >= 1e9 else f"${v / 1e6:,.0f}M")
    # 화면에는 "$145M"/"$1.50B"처럼 단위를 줄여 적지만, 그대로 두면 정렬·스크리너가
    # 글자에서 숫자만 뽑아 145 > 1.50 으로 뒤집힌다. 원값을 data-v에 같이 심는다.
    # (원화와 달러를 한 표에서 섞어 비교하지는 않는다 — 표는 시장별로 나뉘어 있다)
    if intraday:
        return (f'<td class="na" data-v="{v:.0f}" '
                f'title="장이 아직 안 끝나서 확정 거래대금이 아닙니다">'
                f'{txt} <span class="live-tag">장중</span></td>')
    return f'<td data-v="{v:.0f}">{txt}</td>'


def volmul_cell(v, intraday=False):
    """평소(최근 20거래일 중앙값) 대비 거래량 배수. 2배가 넘으면 뭔가 있었다는 뜻이라
    색으로 표시하고, 그 아래는 담담하게 숫자만 둔다."""
    if intraday:
        # 진행 중인 거래량을 20일 중앙값과 비교하면 오전엔 항상 "0.1배"가 나온다.
        # 그건 거래가 죽은 게 아니라 아직 안 쌓인 것이라, 숫자를 내지 않는다.
        return na_cell("장이 끝나야 평소 대비 배수를 낼 수 있습니다")
    if v is None or (isinstance(v, float) and math.isnan(v)) or v <= 0:
        return '<td class="needchk">확인 필요</td>'
    cls = "vol-hot" if v >= 2 else ("vol-warm" if v >= 1.5 else "")
    tip = "최근 20거래일 거래량 중앙값 대비"
    return f'<td class="{cls}" title="{tip}">{v:.2f}배</td>'


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


# ETF 제목행에 붙는 한눈 라벨 — "기술주·전력주"처럼 짧은 우리말 분류(2026-08-09 요청).
# 정확한 지수 이름은 카드 아래 상세 설명(ETF_DESC)에 그대로 남아 있다.
ETF_TAG = {
    "VOO": "미국 대형주", "VTI": "미국 전체주", "QQQ": "나스닥 기술주",
    "VEA": "해외 선진국주", "IEFA": "해외 선진국주", "VTV": "가치주",
    "BND": "채권", "XLK": "기술주", "XLF": "금융주", "XLV": "제약·바이오주",
    "XLY": "경기소비주", "XLP": "필수소비주", "XLE": "에너지주", "XLI": "산업주",
    "XLB": "소재주", "XLU": "전력주", "MAGS": "빅테크주", "SOXX": "반도체주",
}

# ETF 카드 안에 넣는 한 줄 설명. 원래 ETF 탭 하단의 별도 설명 카드에 있던 내용을
# 각 카드 안으로 옮겼다(2026-08-08 영재님 요청). 섹터 9종의 문구는 그 카드에서
# 그대로 가져왔고, 나머지는 어느 지수를 따라가는지만 사실대로 적었다.
ETF_DESC = {
    "VOO": "<b>S&amp;P500</b> — 미국 대형주 500곳을 시가총액대로 담는 대표 지수 ETF. IVV·SPY와 같은 지수.",
    "VTI": "<b>미국 전체</b> — 대형주부터 소형주까지 미국 상장주 전체를 담는다.",
    "QQQ": "<b>나스닥100</b> — 나스닥 대형 기술주 중심. 성장주 장세에 강세 · 금리 급등엔 약세.",
    "VEA": "<b>선진국(미국 제외)</b> — 유럽·일본 등 선진국 주식. 달러 약세엔 상대적 강세.",
    "IEFA": "<b>선진국(북미 제외)</b> — 유럽·일본·호주 등. VEA와 담는 종목이 많이 겹친다.",
    "VTV": "<b>대형 가치주</b> — 배당·금융·헬스케어 비중이 큰 가치주 모음. 하락장에서 상대적으로 방어적.",
    "BND": "<b>미국 채권 전체</b> — 국채·회사채를 두루 담는 채권 ETF. 금리 하락엔 강세 · 금리 상승엔 약세.",
    "XLK": "<b>기술</b> — 애플·MSFT·엔비디아 등 대형 IT·반도체. 금리 하락, AI/실적 기대감엔 강세 · 금리 급등, 성장주 조정엔 약세.",
    "XLF": "<b>금융</b> — 은행·보험·자산운용. 금리 상승, 경기 호조엔 강세 · 경기침체 우려, 신용부실 리스크엔 약세.",
    "XLV": "<b>헬스케어</b> — 제약·바이오·의료기기. 경기와 무관하게 방어적 · 약가 규제, 정책 리스크엔 약세.",
    "XLY": "<b>임의소비재</b> — 아마존·테슬라 등 경기소비재. 소비심리·고용 호조엔 강세 · 금리 인상, 소비 위축엔 약세.",
    "XLP": "<b>필수소비재</b> — 생필품·유통. 증시 조정기엔 상대적 강세(방어주) · 강세장에서는 소외.",
    "XLE": "<b>에너지</b> — 정유·가스. 유가 상승, 지정학 리스크엔 강세 · 유가 하락, 수요 둔화엔 약세.",
    "XLI": "<b>산업재</b> — 제조·항공·건설장비. 경기 확장, 인프라 투자엔 강세 · 경기 둔화엔 약세.",
    "XLB": "<b>소재</b> — 화학·철강·광산. 원자재 가격 상승, 달러 약세엔 강세 · 경기 둔화, 달러 강세엔 약세.",
    "XLU": "<b>유틸리티</b> — 전력·가스·수도. 금리 하락기, 안전자산 선호엔 강세 · 금리 상승기엔 약세.",
    "MAGS": "<b>매그니피센트7</b> — 애플·MSFT·엔비디아 등 빅테크 7종목만 담는 테마 ETF.",
    "SOXX": "<b>반도체</b> — 필라델피아 반도체 지수 추종. AI·반도체 사이클에 민감.",
}


def ma_cell(mas):
    """이동평균선 칸. 5▲는 5일선 위, 60▼는 60일선 아래, 120–는 데이터 부족."""
    chips = []
    for n, above in mas:
        if above is None:
            chips.append(f'<span class="ma na" title="{n}일선: 데이터 부족">{n}–</span>')
        elif above:
            chips.append(f'<span class="ma up" title="{n}일 이동평균선 위">{n}▲</span>')
        else:
            chips.append(f'<span class="ma down" title="{n}일 이동평균선 아래">{n}▼</span>')
    return f'<td class="ma-td">{"".join(chips)}</td>'


def price_str(sym, v):
    """카드 제목 띠에 붙는 종가. 한국 종목은 원, 나머지는 달러로 적는다."""
    if sym.endswith((".KS", ".KQ")):
        return f"{v:,.0f}원"
    return f"${v:,.2f}"


def tv_symbol(label, sym):
    """카드를 펼쳤을 때 띄울 TradingView 심볼. 없으면 None(펼침 버튼도 안 만든다)."""
    if sym.endswith(".KS"):
        return "KRX:" + sym[:-3]
    if sym.endswith(".KQ"):
        return "KOSDAQ:" + sym[:-3]
    return label


def rank_sorted(section, rows, mcaps):
    """(행, 순위) 목록을 돌려준다.

    미국·한국 탭은 받아온 시가총액이 큰 순으로 다시 세워서 자리번호를 그대로
    순위 뱃지로 쓴다 — 손으로 적어둔 목록 순서는 시간이 지나면 실제 순위와
    어긋나기 때문이다. 시가총액을 절반도 못 받아오면 순위를 지어내지 않고
    원래 목록 순서 그대로, 뱃지 없이 내보낸다.
    """
    if section not in ("us30", "kr10"):
        return [(r, None) for r in rows]
    have = [r for r in rows if r[3] in mcaps]
    if len(have) < len(rows) * 0.5:
        print(f"  [warn] {section}: 시가총액 {len(have)}/{len(rows)}개뿐이라 "
              f"순위 뱃지를 붙이지 않습니다", file=sys.stderr)
        return [(r, None) for r in rows]
    have.sort(key=lambda r: -mcaps[r[3]])
    missing = [r for r in rows if r[3] not in mcaps]   # 못 받은 종목은 뒤에, 뱃지 없이
    return [(r, i) for i, r in enumerate(have, 1)] + [(r, None) for r in missing]


# 미국 탭에 섞여 있는 외국 기업. 반도체·제약을 볼 때 같이 봐야 해서 남겨 뒀지만,
# 순위 뱃지는 "미국 기업 순위"가 아니라 이 목록 안의 시가총액 순서라서 헷갈릴 수
# 있다. 그래서 카드에 "해외" 표시를 붙여 둔다 (2026-08-31 영재님 선택).
FOREIGN_LISTED = {"TSM", "ASML", "ARM", "HSBC", "NVS", "RY"}


def name_class(name):
    """이름 길이에 따라 글자 크기 단계를 고른다 (2026-08-16).

    "어플라이드머티리얼즈"·"삼성바이오로직스" 같은 긴 이름은 기본 12.8px로는 좁은
    카드에서 잘린다. 카드 폭을 키우면 한 줄에 들어가는 개수가 줄어드니, 대신 이름
    글자만 단계적으로 줄여서 어느 화면 폭에서도 이름이 다 보이게 한다.
    실제 크기는 index.html의 .supp-name.len-m / .len-l / .len-xl 에 있다.
    """
    n = len(name)
    if n >= 10:
        return "supp-name len-xl"
    if n >= 8:
        return "supp-name len-l"
    if n >= 6:
        return "supp-name len-m"
    return "supp-name"


def chg_rows(items):
    """(라벨, 값, 값클래스, 설명) 목록을 등락 3줄 블록으로 만든다.
    보조지표 카드와 개요 지수 카드가 똑같이 쓴다."""
    out = []
    for lab, v, cls_name, tip, unit in items:
        t = f' title="{tip}"' if tip else ""
        if v is None or (isinstance(v, float) and math.isnan(v)):
            out.append(f'<div class="supp-cr"><span class="supp-dlab"{t}>{lab}</span>'
                       f'<span class="{cls_name} needchk">확인 필요</span></div>')
            continue
        cls = "up" if v > 0 else ("down" if v < 0 else "flat")
        out.append(f'<div class="supp-cr"><span class="supp-dlab"{t}>{lab}</span>'
                   f'<span class="{cls_name} {cls}">{v:+.2f}{unit}</span></div>')
    return '<div class="supp-chg">' + "".join(out) + "</div>"


def chg_stack(day, week, ytd, ddath=None, base_yr=None):
    """제목 띠 오른쪽에 붙는 일간/주간/올해 등락 세 줄.

    값이 없으면 지어내지 않고 "확인 필요"로 둔다. 줄 수는 값이 있든 없든 항상 셋이라
    카드 높이가 종목마다 달라지지 않는다.
    맨 아래 라벨을 "년간"이 아니라 "26년"으로 적은 이유: 이 값은 지난 1년이 아니라
    올해 첫 거래일 종가 대비(YTD)라, "년간"이라고 쓰면 최근 12개월로 오해하기 쉽다.
    """
    yr = base_yr if base_yr else datetime.datetime.now(KST).year
    return chg_rows([
        ("일간", day, "supp-dchg", "직전 거래일 종가 대비", "%"),
        ("주간", week, "supp-wchg", "5거래일 전 종가 대비", "%"),
        (f"{yr % 100}년", ytd, "supp-ychg",
         f"{yr - 1}년 마지막 거래일 종가 대비 (YTD) — 최근 12개월이 아닙니다", "%"),
        # 사상최고 대비도 접힌 상태에서 바로 보이게 (2026-08-16 요청).
        # 최근 1년이 아니라 상장 이후 전체 기간의 최고 종가가 기준이다.
        ("사상최고", ddath, "supp-achg",
         "상장 이후 전체 기간의 최고 종가 대비 — 52주 고점이 아닙니다", "%"),
    ])


def make_row(name, label, logo, sym, rate, closes, aths=None, desc=None, tag=None,
             rank=None, vols=None, pers=None, is_etf=False, mcaps=None):
    # 기간 지표(일간·주간·올해)는 전부 제목 띠 오른쪽에 세로로 쌓았고, 표에는
    # 펼쳐야 보이는 것들만 남겼다: 고점대비 두 개, 연속, RSI, 이평선.
    # desc가 있으면(ETF) 카드 맨 아래에 설명 한 줄이 붙는다.
    # 제목 띠 오른쪽에는 기준일 종가를 그대로 적는다(2026-08-09 영재님 요청).
    aths = aths or {}
    logo_html = (f'<img class="supp-logo" src="https://logo.clearbit.com/{logo}" '
                 f"onerror=\"this.style.display='none'\">") if logo else ""
    desc_td = f'<td class="supp-desc">{desc}</td>' if desc else ""
    tag_html = f'<span class="supp-tag">{tag}</span>' if tag else ""
    # 시총 순위 뱃지 — 목록 자체가 시총순이라 자리 번호가 곧 순위다(2026-08-15 요청)
    rank_html = f'<span class="supp-rank">{rank}</span>' if rank else ""
    # 이름이 길면 글자를 조금 줄여서 잘리지 않게 한다 (2026-08-16).
    # "어플라이드머티리얼즈"·"한화에어로스페이스" 같은 이름은 기본 12.8px로는
    # 좁은 카드에서 잘린다. 칸을 넓히면 한 줄에 들어가는 카드 수가 줄어서
    # 대신 이름 쪽 글자만 단계적으로 줄인다.
    ncls = name_class(name)
    foreign_html = ('<span class="supp-foreign" title="미국에 상장했지만 본사가 미국이 '
                    '아닌 기업입니다 — 왼쪽 순위는 미국 기업 순위가 아니라 이 목록 '
                    '안에서의 시가총액 순서입니다">해외</span>'
                    if label in FOREIGN_LISTED else "")
    # 펼침 카드에서 차트는 뺐다(2026-08-15 요청) — 위젯 로딩이 느리고 좁은 카드에서
    # 잘 안 보여서, 차트는 개요 탭 지수 카드에서만 쓴다.
    chart_td = ""
    # 거래대금·거래량 배수 — 등락률만으로는 "오늘 왜 움직였나"를 못 본다.
    # 평소의 2배 넘게 거래되면 뉴스가 있었다는 뜻이라 색으로 표시한다.
    turnover = volmul = None
    intraday = False
    if vols is not None:
        try:
            v = vols[sym].dropna()
            c = closes[sym].dropna()
            if len(v) >= 21 and len(c):
                last_v = float(v.iloc[-1])
                med = float(v.tail(21).iloc[:-1].median())
                turnover = last_v * float(c.iloc[-1])
                volmul = last_v / med if med > 0 else None
                # 2시간마다 돌기 때문에 장이 열려 있는 동안에도 실행된다. 그때
                # 마지막 봉은 아직 쌓이는 중인 거래량이라, 20일 중앙값과 비교하면
                # 오전엔 늘 "0.1배"가 나와서 거래가 죽은 날처럼 보인다.
                # 확정값이 아니면 배수를 숫자로 내지 않는다.
                intraday = is_intraday(sym, v.index[-1].date())
        except Exception as e:
            print(f"  [warn] {sym} 거래량: {e}", file=sys.stderr)
    cur = "KRW" if sym.endswith((".KS", ".KQ")) else "USD"
    mcap_html = mcap_cell((mcaps or {}).get(sym), cur, is_etf)
    if is_etf:
        # ETF는 기업 재무제표가 없다(개별 기업이 아니라 바구니라서).
        # 못 받아온 것과 구분해서 "해당 없음"으로 둔다.
        val_html = na_cell("ETF에는 기업 재무 지표가 없습니다") * 5
    else:
        p = (pers or {}).get(sym) or {}
        val_html = (per_cell(p.get("trailing")) + per_cell(p.get("forward"))
                    + ratio_cell(p.get("pbr"), "배", 2, hi=100,
                                 tip="주가순자산비율 — 1배면 장부상 순자산과 시가총액이 같다는 뜻")
                    + pct_val_cell(p.get("roe"), 1, color=True,
                                   tip="자기자본이익률 — 주주 돈으로 한 해 얼마를 벌었는지")
                    + pct_val_cell(p.get("de"), 0,
                                   tip="부채비율(부채 ÷ 자기자본) — 100%면 부채와 자기자본이 같다는 뜻"))


    try:
        close = closes[sym]
        px = f'<span class="supp-px">{price_str(sym, float(close.dropna().iloc[-1]))}</span>'
        (day, dd52, ddath, week, ytd, sd, rsi, mas,
         up52, base_yr, low52, high52) = compute(close, rate, aths.get(sym))
        # 접힌 카드에서도 등락을 바로 보게 제목 띠에 붙인다 (2026-08-15 요청).
        # 일간 아래 주간까지 두 줄로 쌓는다 (2026-08-16 요청).
        chg_html = chg_stack(day, week, ytd, ddath, base_yr)
        # 제목 띠는 두 줄이다 — 왼쪽 위: 이름·티커, 왼쪽 아래: 가격.
        # 오른쪽에는 일간/주간 등락이 두 줄로 붙는다.
        # 종목마다 줄 수가 같아야 카드 높이가 전부 같아진다(2026-08-16 요청).
        name_td = (f'<td>{rank_html}{logo_html}<div class="supp-main">'
                   f'<div class="supp-l1"><span class="{ncls}">{name}</span>'
                   f'<span class="supp-ticker">{label}</span>{foreign_html}</div>'
                   f'<div class="supp-l2">{tag_html}{px}</div></div>{chg_html}</td>')
        # 카드 왼쪽 띠 색: 오늘 오르면 빨강, 내리면 파랑 (2026-08-09 시인성 개선)
        sign = ("d-up" if day and day > 0 else
                "d-down" if day and day < 0 else "d-flat")
        # 일간·주간·YTD는 제목 띠에 있으므로 표에서는 뺀다 (2026-08-15·16 요청)
        return (f'          <tr class="{sign}">' + name_td
                + grp_cell(SUPP_GROUPS[0])
                + range_cell(low52, high52, float(close.dropna().iloc[-1]))
                + pct_cell(up52) + pct_cell(dd52)
                + grp_cell(SUPP_GROUPS[1]) + mcap_html + val_html
                + grp_cell(SUPP_GROUPS[2])
                + turnover_cell(turnover, cur, intraday) + volmul_cell(volmul, intraday)
                + grp_cell(SUPP_GROUPS[3])
                + streak_cell(sd) + rsi_cell(rsi) + ma_cell(mas)
                + desc_td + chart_td + "</tr>")
    except Exception as e:
        print(f"  [warn] {sym}: {e}", file=sys.stderr)
        nc = '<td class="needchk">확인 필요</td>'
        name_td = (f'<td>{rank_html}{logo_html}<div class="supp-main">'
                   f'<div class="supp-l1"><span class="{ncls}">{name}</span>'
                   f'<span class="supp-ticker">{label}</span>{foreign_html}</div>'
                   f'<div class="supp-l2"><span class="supp-px needchk">확인 필요</span></div>'
                   f'</div>{empty_stack()}</td>')
        return (f"          <tr>{name_td}{grp_cell(SUPP_GROUPS[0])}{nc * 3}"
                + f"{grp_cell(SUPP_GROUPS[1])}{mcap_html}{val_html}{grp_cell(SUPP_GROUPS[2])}"
                + turnover_cell(turnover, cur, intraday) + volmul_cell(volmul, intraday)
                + f"{grp_cell(SUPP_GROUPS[3])}{nc * 3}{desc_td}{chart_td}</tr>")


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
        f'            <div class="fng-bar" title="0 극도의 공포 · 50 중립 · 100 극도의 탐욕">'
        f'<div class="fng-mark" style="left:{score}%"></div></div>\n'
        '            <div class="fng-scale"><span>0 공포</span><span>50</span>'
        '<span>탐욕 100</span></div>\n'
        f'            <details class="fng-det"><summary>자세히</summary>'
        f'<div class="fng-prev">{asof}<br>{prev_line}</div></details>\n'
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
        '            <div class="fng-scale"><span>0 공포</span><span>50</span>'
        '<span>탐욕 100</span></div>\n'
        f'            <details class="fng-det"><summary>자세히</summary>'
        f'<div class="fng-prev">{note}</div></details>\n'
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
    # ── 2026-08-16 추가. 여기 넣기만 하면 매출·영업이익·이익률·설비투자·잉여현금
    #    흐름은 야후 분기 재무제표에서 자동으로 붙는다. 어닝콜 요약(EARNCALL)과
    #    클라우드 부문(CLOUD_SEG)은 손으로 적는 자료라 아직 없고, 없으면 그 줄이
    #    통째로 빠질 뿐 카드는 정상으로 나온다.
    ("일라이릴리", "LLY", "lilly.com"),
    ("월마트", "WMT", "walmart.com"),
    ("인텔", "INTC", "intel.com"),
    ("팔란티어", "PLTR", "palantir.com"),
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
    if isinstance(v, tuple):                      # 전년이 적자 → %가 성립하지 않는다
        _, prev, now = v
        tip = (f"전년 동기가 {bil(prev)}로 적자여서 증감률을 %로 낼 수 없습니다 "
               f"(적자를 기준으로 나누면 부호가 뒤집힙니다). 올해는 {bil(now)}입니다.")
        if now > 0:
            return f'<span class="up" title="{tip}">적자 → 흑자</span>'
        if now > prev:
            return f'<span class="up" title="{tip}">적자 축소</span>'
        if now < prev:
            return f'<span class="down" title="{tip}">적자 확대</span>'
        return f'<span class="flat" title="{tip}">적자 지속</span>'
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
    # 예전에는 매출과 영업이익이 "둘 다" 있는 분기만 남겼는데, 야후가 새 분기를
    # 올릴 때 매출을 먼저 넣고 영업이익을 나중에 채우는 일이 있다. 그러면 갓 발표된
    # 분기가 통째로 사라져서, 화면에는 아무 표시 없이 한 분기 뒤처진 값이 나온다
    # (2026-08-31 영재님이 아마존에서 발견). 이제는 매출이 있으면 분기를 살리고
    # 영업이익만 None으로 둬서 그 칸만 "확인 필요"가 되게 한다.
    out = []
    for ts in sorted(rev.index):
        r = float(rev[ts])
        if r <= 0:
            continue          # 매출이 없으면 이익률을 계산할 수 없다
        o = float(opi[ts]) if ts in opi.index else None
        out.append((quarter_label(ts), r, o))
    if not out:
        raise ValueError("매출이 있는 분기가 없음")
    dropped = [q for q, _, o in out[-FIN_QUARTERS:] if o is None]
    if dropped:
        print(f"  [warn] {ticker}: 영업이익이 아직 없는 분기 {dropped} — "
              "매출만 표시하고 이익 칸은 확인 필요로 둡니다", file=sys.stderr)
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
    """전년 동기(4분기 전) 대비.

    기준이 되는 전년 값이 마이너스(적자)면 (올해/전년 - 1)의 부호가 뒤집힌다.
    예: 전년 영업이익 -10억, 올해 +15.3억 → (15.3 / -10 - 1) = -2.529 → "-252.9%".
    영업이익이 늘었는데 마이너스 증감률이 찍히는 것이다(2026-08-16 영재님이 인텔
    카드에서 발견). 적자를 기준으로 한 배수는 애초에 뜻이 없으므로, 숫자를 고쳐
    적는 대신 "적자→흑자"처럼 무슨 일이 있었는지로 바꿔 적는다.

    돌려주는 값
      - float                  : 정상적인 증감률(%)
      - ("turn", 전년, 올해)    : 전년이 적자라 %로 적을 수 없는 경우
      - None                   : 분기 수가 모자라거나 값이 비어 있음
    """
    if len(vals) < 5 or vals[-1] is None or vals[-5] is None or not vals[-5]:
        return None
    prev, now = vals[-5], vals[-1]
    if prev < 0:
        return ("turn", prev, now)
    return (now / prev - 1) * 100


def lag_chip(newest):
    """야후에 아직 그 분기 재무제표가 안 올라왔다는 표시."""
    tip = (f"회사는 이미 발표했지만 야후 파이낸스에 {newest} 재무제표가 아직 "
           "올라오지 않았습니다. 올라오면 다음 자동 갱신 때 저절로 채워집니다.")
    return f'<span class="fin-lag" title="{tip}">{newest} 미반영</span>'


def fin_item(name, ticker, logo, series, cash, newest=None):
    """cash는 fetch_cash 결과((CAPEX목록, FCF목록)) 또는 None.

    newest가 들어오면 "다른 카드는 그 분기까지 있는데 이 카드만 뒤처졌다"는 뜻이라
    제목 옆에 표시를 붙인다.
    """
    labs = [q for q, _, _ in series]
    revs = [r for _, r, _ in series]
    ops = [o for _, _, o in series]
    # 영업이익이 아직 안 올라온 분기는 이익률도 낼 수 없다 — 0으로 채우지 않는다
    mgs = [(o / r * 100) if o is not None else None for _, r, o in series]

    mg_pp = (mgs[-1] - mgs[-5]
             if len(mgs) >= 5 and mgs[-1] is not None and mgs[-5] is not None
             else None)

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
        + (lag_chip(newest) if newest else "")
        + '<span class="fin-more">자세히 보기</span></summary>\n'
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
    """빅테크 분기 실적 카드.

    야후는 회사가 실적을 발표한 뒤에도 분기 재무제표를 며칠~몇 주 늦게 올린다.
    그래서 어떤 카드만 한 분기 뒤처지는 일이 생기는데, 작은 글씨의 "26 2Q 기준"만
    보고는 알아채기 어렵다(2026-08-31 영재님이 엔비디아에서 발견). 그래서 먼저
    전부 받아본 뒤 가장 최신 분기를 구하고, 그보다 뒤처진 카드에는 표시를 붙인다.
    """
    fetched, ok, cok = [], 0, 0
    for name, ticker, logo in BIGTECH:
        # 현금흐름표는 따로 받는다. 이쪽이 실패해도 매출·영업이익은 그대로 보여준다.
        try:
            cash = fetch_cash(ticker)
            cok += 1
        except Exception as e:
            print(f"  [warn] 현금흐름 {ticker}: {e}", file=sys.stderr)
            cash = None
        try:
            fetched.append((name, ticker, logo, fetch_fin(ticker), cash))
            ok += 1
        except Exception as e:
            print(f"  [warn] 재무 {ticker}: {e}", file=sys.stderr)
            fetched.append((name, ticker, logo, None, None))

    # 분기 라벨("26 2Q")은 글자 그대로 정렬해도 시간 순서가 맞는다
    lasts = [ser[-1][0] for *_x, ser, _c in fetched if ser]
    newest = max(lasts) if lasts else None
    behind = [t for _n, t, _l, ser, _c in fetched if ser and ser[-1][0] != newest]
    if behind:
        print(f"  [warn] 야후에 최신 분기({newest})가 아직 없는 종목: {', '.join(behind)}",
              file=sys.stderr)

    items = []
    for name, ticker, logo, ser, cash in fetched:
        if ser is None:
            items.append(fin_item_fail(name, ticker, logo, "분기 손익계산서를 못 받아왔습니다"))
        else:
            items.append(fin_item(name, ticker, logo, ser, cash,
                                  newest if ser[-1][0] != newest else None))
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
    # 아래 6개는 없어진 매크로·심리 탭에서 넘어온 것들. 카드를 펼치면 보조지표가 나온다.
    ("달러 인덱스", "DXY", "DX-Y.NYB", "TVC:DXY", 2),
    ("원달러 환율", "USDKRW", "KRW=X", "FX_IDC:USDKRW", 2),
    ("WTI 원유", "USOIL", "CL=F", "TVC:USOIL", 2),
    ("브렌트유", "UKOIL", "BZ=F", "TVC:UKOIL", 2),
    ("금", "GOLD", "GC=F", "TVC:GOLD", 2),
    ("은", "SILVER", "SI=F", "TVC:SILVER", 2),
    ("비트코인", "BTC", "BTC-USD", "COINBASE:BTCUSD", 0),
    ("하이일드 스프레드", "HY OAS", "FRED:BAMLH0A0HYM2", "FRED:BAMLH0A0HYM2", 2),
]

FRED_SYMS = [sym for _, _, sym, _, _ in INDEXES if sym.startswith("FRED:")]


def _redact(msg):
    """로그에 API 키가 찍히지 않게 지운다. (깃허브도 시크릿을 가려주지만 이중으로)"""
    return re.sub(r"api_key=[^&\s]+", "api_key=***", str(msg))


def _fred_get(url, timeout):
    req = urllib.request.Request(url, headers={
        "User-Agent": UA,
        "Accept": "application/json,text/csv,text/plain,*/*",
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


def _fred_parse_api(raw):
    """api.stlouisfed.org JSON 형식. 결측치는 값이 "."으로 온다."""
    obs = json.loads(raw).get("observations")
    if not obs:
        raise ValueError("observations 비어 있음")
    s = pd.Series(pd.to_numeric([o["value"] for o in obs], errors="coerce"),
                  index=pd.to_datetime([o["date"] for o in obs])).dropna().sort_index()
    return s


def fetch_fred(series_id):
    """FRED(세인트루이스 연은)에서 일별 시계열을 받는다.

    휴장일·미발표일은 값이 "."로 들어오는데, 이런 결측치는 만들어 채우지 않고
    그냥 건너뛴다(dropna). 끝까지 못 받으면 예외를 던지고, 호출부에서 "확인 필요"로
    처리한다 — 값을 지어내지 않는다.

    2026-08-05 두 번의 Actions 실행에서 fred.stlouisfed.org(그래프/다운로드용 주소)가
    csv·txt 6번 재시도 모두 "The read operation timed out"이었다. 연결은 되는데 응답이
    안 오고 주소를 바꿔도 같으니, 깃허브 러너에서 그 호스트가 막힌 것으로 본다.
    그래서 프로그램 접근용 주소인 api.stlouisfed.org를 1순위로 쓴다. 이쪽은 무료 API
    키가 필요하고, 키는 깃허브 시크릿(FRED_API_KEY)에서 환경변수로 들어온다.

    키가 없으면 예전처럼 csv·txt만 시도한다 — 즉 키를 안 넣어도 스크립트는 안 죽고,
    하이일드 칸만 "확인 필요"로 남는다.
    """
    cosd = (datetime.date.today() - datetime.timedelta(days=5 * 365)).isoformat()
    routes = []
    api_key = os.environ.get("FRED_API_KEY", "").strip()
    if api_key:
        routes.append((
            f"https://api.stlouisfed.org/fred/series/observations?series_id={series_id}"
            f"&api_key={api_key}&file_type=json&observation_start={cosd}&sort_order=asc",
            _fred_parse_api, "api"))
    else:
        print("  [info] FRED_API_KEY가 없어서 공개 csv 주소만 시도합니다", file=sys.stderr)
    routes += [
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
                errors.append(_redact(f"{tag}/{timeout}s {type(e).__name__}: {e}"))
        else:
            if time.monotonic() - started < DEADLINE:
                time.sleep(3)
            continue
        break
    # API 쪽 오류가 가장 진단에 도움이 되므로(키 오타면 400, 미승인이면 403) 반드시 남긴다
    api_errs = [e for e in errors if e.startswith("api/")]
    tail = api_errs[:1] + errors[-2:] if api_errs else errors[-3:]
    raise RuntimeError(f"{attempt}회 재시도 실패 — " + " | ".join(tail))


def num(v, digits):
    return f"{v:,.{digits}f}"


def im_row(k, v_html):
    return f'<div class="im"><span class="im-k">{k}</span>{v_html}</div>'


def im_pct(v):
    if v is None or (isinstance(v, float) and math.isnan(v)):
        return '<span class="im-v needchk">확인 필요</span>'
    cls = "up" if v > 0 else ("down" if v < 0 else "needchk")
    return f'<span class="im-v {cls}">{v:+.2f}%</span>'


def im_pp(v):
    """FRED 스프레드용 — %가 아니라 %p 차이로 적는다."""
    if v is None:
        return '<span class="im-v needchk">확인 필요</span>'
    cls = "up" if v > 0 else ("down" if v < 0 else "needchk")
    return f'<span class="im-v {cls}">{v:+.2f}%p</span>'


def idx_metrics(s, sym, ath):
    """카드를 펼쳤을 때 보여줄 보조지표 블록.

    없어진 매크로·심리 탭의 표가 하던 역할이 여기로 왔다. 하이일드 스프레드(FRED)는
    값 자체가 %p라서 등락을 %로 적으면 헷갈리므로 %p 차이로 따로 계산한다.
    """
    if sym.startswith("FRED:"):
        last = float(s.iloc[-1])
        d1, d5, d21 = (None if a is None else last - a
                       for a in (ago(s, 1), ago(s, 5), ago(s, 21)))
        rows = [im_row(k, im_pp(None if a is None else last - a))
                for k, a in [("전일 대비", ago(s, 1)), ("1주 대비", ago(s, 5)),
                             ("1개월 대비", ago(s, 21)), ("1년 대비", ago(s, 252))]]
        rows.append(im_row("52주 범위",
                           f'<span class="im-v">{float(s.tail(252).min()):.2f}~'
                           f'{float(s.tail(252).max()):.2f}%p</span>'))
        # 값 자체가 %인 계열이라 제목 띠에도 비율이 아니라 %p로 적는다
        d252 = (None if ago(s, 252) is None else last - ago(s, 252))
        stack = chg_rows([
            ("일간", d1, "supp-dchg", "직전 거래일 대비 (%p)", "%p"),
            ("주간", d5, "supp-wchg", "5거래일 전 대비 (%p)", "%p"),
            ("1개월", d21, "supp-ychg", "21거래일 전 대비 (%p)", "%p"),
            ("1년", d252, "supp-achg", "252거래일 전 대비 (%p)", "%p"),
        ])
        return '<div class="idx-metrics">' + "".join(rows) + "</div>", stack
    (day, dd52, ddath, week, ytd, sd, rsi, mas,
     up52, base_yr, _lo, _hi) = compute(s, False, ath)
    streak, direction = sd
    st = ('<span class="im-v needchk">보합</span>' if streak == 0 else
          f'<span class="im-v up">{streak}일 상승</span>' if direction > 0 else
          f'<span class="im-v down">{streak}일 하락</span>')
    ma_html = ma_cell(mas).replace('<td class="ma-td">', '<span class="im-v">') \
                          .replace("</td>", "</span>")
    rows = [im_row("일간", im_pct(day)), im_row("주간", im_pct(week)),
            im_row(f"{base_yr % 100}년 YTD", im_pct(ytd)), im_row("52주 저점대비", im_pct(up52)),
            im_row("52주 고점대비", im_pct(dd52)),
            im_row("사상최고 대비", im_pct(ddath)), im_row("연속", st),
            im_row("RSI", f'<span class="im-v">{rsi:.1f}</span>' if rsi is not None
                   else '<span class="im-v needchk">확인 필요</span>'),
            im_row("이평선", ma_html)]
    return ('<div class="idx-metrics">' + "".join(rows) + "</div>",
            chg_stack(day, week, ytd, ddath, base_yr))


def idx_card(name, label, tvsym, last, digits, metrics="", stack=""):
    """지수 카드 하나. 클릭하면 보조지표가 펼쳐지도록 <details>로 감싼다.

    차트는 뺐다(2026-08-16 요청). 트레이딩뷰 위젯이 카드 밖으로 넘쳐서 아래 카드를
    덮었고, 같은 이유로 종목 카드에서도 이미 뺀 상태였다. tvsym 인자는 INDEXES
    표의 모양을 유지하려고 남겨 둔다.

    제목 띠는 종목 카드와 똑같이 일간·주간·연간 세 줄이다(2026-08-16 요청).
    하이일드 스프레드처럼 값 자체가 %인 계열은 idx_metrics 쪽에서 %p로 만들어
    넘겨주므로, 3.00 → 3.10이 "+3.33%"가 아니라 "+0.10%p"로 나온다.
    """
    return (
        '          <details class="idx-card">\n'
        '            <summary class="idx-sum">\n'
        '              <div class="idx-main">\n'
        f'                <div class="idx-name">{name}<span class="idx-sym">{label}</span></div>\n'
        f'                <div class="idx-val">{num(last, digits)}</div>\n'
        '              </div>\n'
        f'              {stack}\n'
        '            </summary>\n'
        f'            {metrics}\n'
        '          </details>'
    )


def empty_stack():
    """시세를 못 받았을 때의 등락 3줄 — 줄 수는 그대로라 카드 높이가 안 흔들린다."""
    return chg_rows([("일간", None, "supp-dchg", None, "%"),
                     ("주간", None, "supp-wchg", None, "%"),
                     ("연간", None, "supp-ychg", None, "%"),
                     ("사상최고", None, "supp-achg", None, "%")])


def idx_card_fail(name, label, tvsym):
    return (
        '          <details class="idx-card">\n'
        '            <summary class="idx-sum">\n'
        '              <div class="idx-main">\n'
        f'                <div class="idx-name">{name}<span class="idx-sym">{label}</span></div>\n'
        '                <div class="idx-val needchk">확인 필요</div>\n'
        '              </div>\n'
        f"              {empty_stack()}\n"
        '            </summary>\n'
        '          </details>'
    )


def build_idx(closes, aths=None):
    aths = aths or {}
    cards, ok = [], 0
    for name, label, sym, tvsym, digits in INDEXES:
        try:
            s = closes[sym].dropna()
            if len(s) < 2:
                raise ValueError("데이터 부족")
            try:
                metrics, stack = idx_metrics(s, sym, aths.get(sym))
            except Exception as me:
                # 지표 계산이 안 돼도 카드 자체(현재값)는 살린다
                print(f"  [warn] 지수 지표 {sym}: {me}", file=sys.stderr)
                metrics, stack = "", empty_stack()
            cards.append(idx_card(name, label, tvsym,
                                  float(s.iloc[-1]), digits, metrics, stack))
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




# ------------------------------------------------------------- 오늘의 신호
#
# 표 103종목을 매번 훑지 않아도 되게, 기계적 조건에 걸린 종목만 개요 탭에 모은다.
# 전부 이미 받아온 종가에서 계산하는 값이라 새 데이터 소스는 없다. 조건:
#   52주 신고가  : 오늘 종가가 최근 252거래일 최고가 (1년치 데이터가 있을 때만)
#   골든/데드크로스: 5일 이동평균이 20일 이동평균을 오늘 상향/하향 돌파
#   RSI 과매도/과열: 14일 RSI 30 이하 / 70 이상
#   급등/급락    : 하루 ±5% 이상
# 계산 조건일 뿐 매수·매도 추천이 아니라는 문구를 화면에 같이 적는다.

def build_signals(closes):
    stocks, seen = [], set()
    for sec in ("us30", "kr10", "etf"):
        for name, label, _, sym, _ in SECTIONS[sec]:
            if sym not in seen:
                seen.add(sym)
                stocks.append((name, sym))

    hi52, golden, dead, oversold, overheat, spike = [], [], [], [], [], []
    for name, sym in stocks:
        s = closes.get(sym)
        if s is None:
            continue
        s = s.dropna()
        if len(s) < 60:
            continue
        last, prev = float(s.iloc[-1]), float(s.iloc[-2])
        day = (last / prev - 1) * 100
        try:
            r = rsi14(s)
        except Exception:
            r = None

        if len(s) >= 252 and last >= float(s.tail(252).max()):
            hi52.append((name, sym, price_str(sym, last), -last))
        if len(s) >= 21:
            ma5, ma20 = float(s.tail(5).mean()), float(s.tail(20).mean())
            y = s.iloc[:-1]
            ma5y, ma20y = float(y.tail(5).mean()), float(y.tail(20).mean())
            if ma5 > ma20 and ma5y <= ma20y:
                golden.append((name, sym, f"{day:+.1f}%", 0))
            elif ma5 < ma20 and ma5y >= ma20y:
                dead.append((name, sym, f"{day:+.1f}%", 0))
        if r is not None and r <= 30:
            oversold.append((name, sym, f"RSI {r:.1f}", r))
        elif r is not None and r >= 70:
            overheat.append((name, sym, f"RSI {r:.1f}", -r))
        if abs(day) >= 5:
            spike.append((name, sym, f"{day:+.1f}%", -abs(day)))

    def chips(items, vcls):
        if not items:
            return '<span class="sig-none">오늘은 없음</span>'
        items = sorted(items, key=lambda t: t[3])
        out = [f'<span class="sig-chip">{n}<b class="{vcls}">{v}</b></span>'
               for n, _, v, _ in items[:14]]
        if len(items) > 14:
            out.append(f'<span class="sig-none">외 {len(items) - 14}종목</span>')
        return "".join(out)

    rows = [
        ("52주 신고가", chips(hi52, "sig-acc")),
        ("골든크로스 <i>5일선이 20일선 상향 돌파</i>", chips(golden, "up")),
        ("데드크로스 <i>5일선이 20일선 하향 돌파</i>", chips(dead, "down")),
        ("RSI 과매도 <i>30 이하</i>", chips(oversold, "down")),
        ("RSI 과열 <i>70 이상</i>", chips(overheat, "up")),
        ("하루 ±5% 이상", chips(spike, "sig-acc")),
    ]
    n_all = sum(len(x) for x in (hi52, golden, dead, oversold, overheat, spike))
    print(f"  신호 {n_all}건 (신고가 {len(hi52)} · 골든 {len(golden)} · 데드 {len(dead)} · "
          f"과매도 {len(oversold)} · 과열 {len(overheat)} · 급등락 {len(spike)})")
    body = "".join(f'<div class="sig-row"><span class="sig-k">{k}</span>'
                   f'<span class="sig-v">{v}</span></div>' for k, v in rows)
    return f'\n        <div class="sig-grid">{body}</div>\n      '


# ------------------------------------------------- 시가총액 표기
#
# 시총순위 탭은 2026-08-31에 없앴다(영재님 요청). 반기별 순위 히트맵과 그 수기
# 데이터(MCAP_HIST·MCAP_EVENTS 등)는 이 커밋 이전 기록에 그대로 남아 있으니,
# 되살릴 일이 생기면 git 이력에서 꺼내면 된다.
# 시가총액 자체는 계속 받는다 — 카드의 순위 뱃지와 펼침 표의 시가총액 칸에 쓴다.


def mcap_fmt(cap, cur="USD"):
    """시가총액을 읽기 쉬운 단위로. 원화와 달러를 한 칸에 섞지 않도록 통화를 받는다."""
    if cap is None or (isinstance(cap, float) and math.isnan(cap)) or cap <= 0:
        return None
    if cur == "KRW":
        return f"{cap / 1e12:.1f}조원" if cap >= 1e12 else f"{cap / 1e8:,.0f}억원"
    return f"${cap / 1e12:.3f}조" if cap >= 1e12 else f"${cap / 1e9:,.1f}B"


def mcap_cell(cap, cur, is_etf=False):
    """펼친 표의 시가총액 칸. 정렬이 단위 글자에 속지 않도록 원값을 data-v에 심는다."""
    if is_etf:
        return na_cell("ETF는 시가총액이 아니라 순자산(AUM)으로 크기를 잽니다")
    t = mcap_fmt(cap, cur)
    if t is None:
        return '<td class="needchk">확인 필요</td>'
    return f'<td data-v="{cap:.0f}" title="야후 파이낸스 기준">{t}</td>'



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
            f'            <details class="yld-det"><summary>과거</summary>'
            f'<div class="yld-hist">{hist}</div></details>\n'
            '          </div>')


def build_yield(closes):
    """미 10년물·2년물과 장단기 금리차.

    두 금리를 각각 iloc[-1]로 뽑아 빼면 안 된다. ^TNX는 미국 정규장에만 찍히고
    2YY=F는 거의 24시간 찍혀서, 한국 아침에 돌리면 마지막 봉 날짜가 하루 어긋난다.
    서로 다른 날의 두 금리를 빼면 금리차가 몇 bp씩 틀어지고, 0 근처에서는
    "역전이다/아니다" 판정 자체가 뒤집힐 수 있다. 그래서 두 계열에 공통으로
    존재하는 날짜만 남긴 뒤에 계산한다.
    """
    s10 = closes.get(Y10)
    s02 = closes.get(Y02)
    s10 = s10.dropna() if s10 is not None else None
    s02 = s02.dropna() if s02 is not None else None
    aligned = False
    if s10 is not None and s02 is not None:
        common = s10.index.intersection(s02.index)
        if len(common) >= 2:
            s10, s02 = s10.loc[common], s02.loc[common]
            aligned = True
        else:
            print("  [warn] 금리: 10년물과 2년물의 공통 거래일이 2일 미만이라 "
                  "금리차를 계산하지 않습니다", file=sys.stderr)

    def pick(s):
        try:
            if s is None or len(s) < 2:
                return None, None, None, None
            return float(s.iloc[-1]), ago(s, 1), ago(s, 21), ago(s, 252)
        except Exception as e:
            print(f"  [warn] 금리: {e}", file=sys.stderr)
            return None, None, None, None

    t10, p10, m10, y10 = pick(s10)
    t02, p02, m02, y02 = pick(s02)
    items = [yld_item("미 10년물", t10, p10, m10, y10),
             yld_item("미 2년물", t02, p02, m02, y02)]

    # 개별 금리는 각자 최신값을 그대로 보여준다. 다만 "차"는 같은 날짜끼리만 뺀다.
    if t10 is None or t02 is None or not aligned:
        items.append(yld_item("장단기 금리차 (10년 − 2년)", None, None, None, None))
        state = ('<span class="needchk">두 금리의 거래일을 맞추지 못해 금리차를 '
                 "계산하지 않았습니다</span>" if (t10 is not None and t02 is not None)
                 else '<span class="needchk">두 금리를 다 받아와야 계산할 수 있습니다</span>')
    else:
        sp = t10 - t02
        spp = (p10 - p02) if (p10 is not None and p02 is not None) else None
        spm = (m10 - m02) if (m10 is not None and m02 is not None) else None
        spy = (y10 - y02) if (y10 is not None and y02 is not None) else None
        items.append(yld_item("장단기 금리차 (10년 − 2년)", sp, spp, spm, spy, unit="%p"))
        why = ('<span class="yld-why">돈을 오래 빌려주는 쪽이 더 낮은 이자를 받는 '
               '뒤집힌 상태입니다. 시장이 "가까운 미래에 경기가 나빠져 금리가 내려갈 것"으로 '
               '보고 있다는 뜻이라, 과거 미국 경기침체 앞에서 거의 매번 먼저 나타났습니다. '
               '다만 역전 시점과 실제 침체 사이에는 대체로 1~2년 시차가 있었고, 역전이 '
               '풀리는 국면이 오히려 침체와 더 가까웠습니다.</span>')
        if sp < 0:
            state = ('<b class="down">역전 상태</b> — 2년물이 10년물보다 '
                     f'{abs(sp) * 100:.0f}bp 높습니다' + why)
        else:
            state = ('<b class="up">역전 아님</b> — 10년물이 2년물보다 '
                     f'{sp * 100:.0f}bp 높습니다'
                     '<span class="yld-why">장기 금리가 단기보다 높은 정상적인 모양입니다. '
                     '이 차이가 좁아지다 마이너스로 내려가면 "장단기 금리 역전"이라 부릅니다.'
                     "</span>")
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


def market_today(sym):
    """그 종목이 상장된 시장의 "오늘" 날짜.

    한국시간 자정~오후 1시 사이에는 KST 날짜가 미국보다 하루 앞선다. 그때 미국
    종목의 발표일을 KST 날짜로 거르면, 오늘 밤 뉴욕에서 발표하는 회사가 "이미
    지난 날짜"로 취급돼 목록에서 통째로 빠진다.
    """
    if sym.endswith((".KS", ".KQ")):
        return datetime.datetime.now(KST).date()
    try:
        return datetime.datetime.now(ZoneInfo("America/New_York")).date()
    except Exception:
        # 시간대 정보를 못 읽으면 KST 기준으로 두되, 하루 앞서 잘라내지 않도록
        # 하루 여유를 준다 — 놓치는 것보다 하루 지난 걸 한 번 더 보는 게 낫다.
        return datetime.datetime.now(KST).date() - datetime.timedelta(days=1)


def fetch_earnings(sym):
    """(날짜, 확정여부) 또는 None. 오늘 이후 가장 가까운 발표일 하나만."""
    t = yf.Ticker(sym)
    today = market_today(sym)

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
    # 창의 시작점은 각 시장의 오늘(fetch_earnings 안에서 처리), 창의 길이만 여기서 잡는다.
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
    # 여기서 자르지 않는다. 날짜순이라 잘리는 건 항상 뒤쪽 = 달력 둘째 달이어서,
    # 미리 자르면 9~10월 일정이 통째로 사라진다. 개수 제한은 아래 목록 카드에만
    # 적용하고(build_earn_list), 달력은 받은 걸 다 그린다.
    return rows, miss


def build_earn_list(rows):
    if not rows:
        return ('        <div class="earn-empty">앞으로 '
                f'{EARN_WINDOW}일 안에 잡힌 발표일을 하나도 받아오지 못했습니다 (확인 필요)</div>')
    out = []
    cut = len(rows) - EARN_MAX
    if cut > 0:
        print(f"  목록 카드에는 가까운 {EARN_MAX}건만 싣습니다 (뒤쪽 {cut}건은 달력에만)")
    for d, name, short, confirmed in rows[:EARN_MAX]:
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
#
# 물가지표(CPI·PPI·PCE)는 2026-08-16에 아래 공식 일정표에서 직접 확인해 옮겨 적었다.
#   - CPI: https://www.bls.gov/schedule/news_release/cpi.htm
#   - PPI: https://www.bls.gov/schedule/news_release/ppi.htm
#   - PCE(개인소득·지출): https://www.bea.gov/news/schedule
#   교차검증: https://www.bls.gov/schedule/2026/home.htm (요일까지 일치 확인)
#   셋 다 현지 오전 8시 30분(ET) 발표라 한국시간으로도 같은 날 밤(21:30~22:30 KST)이다.
#   그래서 FOMC·BOJ와 달리 날짜를 하루 밀지 않는다.
#   2026년 12월분(=2027년 1월 발표)은 아직 공식 일정이 안 나와서 넣지 않았다.
MACRO_EVENTS = [
    # (날짜, 칩에 쓸 짧은 라벨, 확정 여부)
    (datetime.date(2026, 8, 26), "美 PCE", True),
    (datetime.date(2026, 8, 27), "한은 금통위", True),
    (datetime.date(2026, 9, 10), "美 PPI", True),
    (datetime.date(2026, 9, 11), "美 CPI", True),
    (datetime.date(2026, 9, 17), "FOMC", True),
    (datetime.date(2026, 9, 18), "BOJ", True),
    (datetime.date(2026, 9, 30), "美 PCE", True),
    (datetime.date(2026, 10, 2), "테슬라 인도량*", False),
    (datetime.date(2026, 10, 14), "美 CPI", True),
    (datetime.date(2026, 10, 15), "美 PPI", True),
    (datetime.date(2026, 10, 22), "한은 금통위", True),
    (datetime.date(2026, 10, 29), "FOMC", True),
    (datetime.date(2026, 10, 29), "美 PCE", True),
    (datetime.date(2026, 10, 30), "BOJ", True),
    (datetime.date(2026, 11, 10), "美 CPI", True),
    (datetime.date(2026, 11, 13), "美 PPI", True),
    (datetime.date(2026, 11, 25), "美 PCE", True),
    (datetime.date(2026, 11, 26), "한은 금통위", True),
    (datetime.date(2026, 12, 10), "FOMC", True),
    (datetime.date(2026, 12, 10), "美 CPI", True),
    (datetime.date(2026, 12, 15), "美 PPI", True),
    (datetime.date(2026, 12, 18), "BOJ", True),
    (datetime.date(2026, 12, 23), "美 PCE", True),
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
        # 물가지표(CPI·PPI·PCE)는 회의 일정과 성격이 달라 칩 색을 따로 준다
        kind = "price" if short.startswith("美 ") else "macro"
        by_day.setdefault(d, []).append((short, kind))

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
                f'<div class="cal-chip{"" if kind == "earn" else " " + kind}">{c}</div>'
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


# ------------------------------------------------------------- 섹터별 등락 히트맵
#
# 섹터는 야후의 sector 값을 쓰지 않고 손으로 적었다. 야후는 같은 회사를 조회
# 시점마다 다르게 분류할 때가 있고("Technology" ↔ "Consumer Cyclical"), 한국
# 종목은 아예 비어 오는 경우가 많아서, 자동으로 두면 어느 날 조용히 칸이 바뀐다.
# 종목을 새로 넣으면 여기에도 한 줄 추가해야 한다 — 빠뜨리면 "기타"로 모인다.
SECTOR_OF = {
    # 반도체 (설계·제조·장비·메모리를 한 칸에 둔다 — 사이클을 같이 타서)
    "NVDA": "반도체", "TSM": "반도체", "AVGO": "반도체", "AMD": "반도체",
    "ASML": "반도체", "MU": "반도체", "INTC": "반도체", "AMAT": "반도체",
    "LRCX": "반도체", "ARM": "반도체", "KLAC": "반도체", "SNDK": "반도체",
    "TXN": "반도체", "MRVL": "반도체", "QCOM": "반도체", "ADI": "반도체",
    "005930.KS": "반도체", "000660.KS": "반도체",
    "009150.KS": "반도체",
    # 인터넷·소프트웨어 (스트리밍인 넷플릭스도 여기에 둔다 — 혼자 "미디어" 칸을
    # 만들면 그 칸 평균이 곧 넷플릭스 한 종목이라 업종 지표가 되지 못한다)
    "MSFT": "인터넷·소프트웨어", "GOOGL": "인터넷·소프트웨어",
    "META": "인터넷·소프트웨어", "ORCL": "인터넷·소프트웨어",
    "PLTR": "인터넷·소프트웨어", "CRWD": "인터넷·소프트웨어",
    "IBM": "인터넷·소프트웨어", "PANW": "인터넷·소프트웨어",
    "CRM": "인터넷·소프트웨어",
    "035420.KS": "인터넷·소프트웨어", "402340.KS": "인터넷·소프트웨어",
    # 통신·미디어 — 2026-08-31 TOP75 확장으로 통신 3사와 디즈니가 들어와 되살렸다.
    # 넷플릭스도 디즈니와 같은 성격이라 여기로 옮긴다(전에는 혼자라 소프트웨어에 뒀다).
    "VZ": "통신·미디어", "TMUS": "통신·미디어", "T": "통신·미디어",
    "DIS": "통신·미디어", "NFLX": "통신·미디어",
    # 산업재 — 철도·건설기계·광업처럼 "물건을 나르고 캐고 만드는" 쪽.
    # 캐터필러는 그동안 항공우주·방산에 잘못 들어가 있었다.
    "UNP": "산업재", "CAT": "산업재", "SCCO": "산업재",
    # 하드웨어·네트워크
    "AAPL": "하드웨어·네트워크", "CSCO": "하드웨어·네트워크",
    "DELL": "하드웨어·네트워크", "ANET": "하드웨어·네트워크",
    "APH": "하드웨어·네트워크",
    # 금융
    "BRK-B": "금융", "JPM": "금융", "V": "금융", "MA": "금융", "BAC": "금융",
    "HSBC": "금융", "MS": "금융", "GS": "금융", "RY": "금융", "WFC": "금융",
    "C": "금융", "AXP": "금융", "SCHW": "금융", "BLK": "금융", "BX": "금융",
    # 웰타워는 헬스케어 시설 리츠다. 부동산 묶음을 하나 더 만들 만큼 종목이 없어
    # 금융에 둔다(리츠는 결국 금융상품이라 아주 틀린 자리도 아니다).
    "WELL": "금융",
    "105560.KS": "금융", "055550.KS": "금융",
    "086790.KS": "금융", "032830.KS": "금융", "034730.KS": "금융",
    # 헬스케어·제약
    "LLY": "헬스케어·제약", "JNJ": "헬스케어·제약", "ABBV": "헬스케어·제약",
    "UNH": "헬스케어·제약", "MRK": "헬스케어·제약", "NVS": "헬스케어·제약",
    "AMGN": "헬스케어·제약", "TMO": "헬스케어·제약",
    "ABT": "헬스케어·제약", "GILD": "헬스케어·제약",
    "207940.KS": "헬스케어·제약", "068270.KS": "헬스케어·제약",
    # 소비재·유통
    "AMZN": "소비재·유통", "WMT": "소비재·유통", "COST": "소비재·유통",
    "KO": "소비재·유통", "PG": "소비재·유통", "HD": "소비재·유통",
    "PM": "소비재·유통", "PEP": "소비재·유통", "MCD": "소비재·유통",
    "028260.KS": "소비재·유통",
    # 자동차·2차전지
    "TSLA": "자동차·2차전지", "005380.KS": "자동차·2차전지",
    "000270.KS": "자동차·2차전지", "012330.KS": "자동차·2차전지",
    "373220.KS": "자동차·2차전지",
    # 에너지·전력
    "XOM": "에너지·전력", "CVX": "에너지·전력", "GEV": "에너지·전력",
    "NEE": "에너지·전력",
    "034020.KS": "에너지·전력",
    # 항공우주·방산·산업재
    "SPCX": "항공우주·방산", "GE": "항공우주·방산", "RTX": "항공우주·방산",
    "012450.KS": "항공우주·방산",
    "329180.KS": "항공우주·방산",
}
# 화면에 놓을 순서 (익숙한 순서를 고정해 둬야 매일 자리가 안 바뀐다)
SECTOR_ORDER = ["반도체", "인터넷·소프트웨어", "하드웨어·네트워크", "통신·미디어",
                "금융", "헬스케어·제약", "소비재·유통", "자동차·2차전지",
                "에너지·전력", "산업재", "항공우주·방산"]


def check_tables():
    """서로 맞춰 둬야 하는 표들이 어긋나지 않았는지 시작하자마자 확인한다.

    종목을 새로 넣고 SECTOR_OF에 안 적으면, 그 종목은 아무 경고 없이 히트맵에서
    빠지고 업종 평균에서도 빠진다. 조용히 사라지는 것보다 Actions가 빨간색으로
    실패하는 편이 낫다는 판단(2026-08-16 영재님 선택).
    """
    secs = [sym for k in ("us30", "kr10") for *_, sym, _ in SECTIONS[k]]
    problems = []
    gap = [x for x in secs if x not in SECTOR_OF]
    if gap:
        problems.append(f"SECTOR_OF에 없는 종목: {gap}")
    dead = [k for k in SECTOR_OF if k not in secs]
    if dead:
        problems.append(f"SECTIONS에서 사라진 SECTOR_OF 항목: {dead}")
    bad = sorted(set(SECTOR_OF.values()) - set(SECTOR_ORDER))
    if bad:
        problems.append(f"SECTOR_ORDER에 없는 업종: {bad}")
    empty = [g for g in SECTOR_ORDER if g not in set(SECTOR_OF.values())]
    if empty:
        problems.append(f"소속 종목이 없는 업종: {empty}")
    etfs = [n for n, *_ in SECTIONS["etf"]]
    for nm, d in (("ETF_DESC", ETF_DESC), ("ETF_TAG", ETF_TAG)):
        miss = [n for n in etfs if n not in d]
        if miss:
            problems.append(f"{nm}에 없는 ETF: {miss}")
    dup = [x for x in set(secs) if secs.count(x) > 1]
    if dup:
        problems.append(f"중복된 종목: {dup}")
    if problems:
        raise SystemExit("[error] 표가 서로 어긋났습니다 — 고치고 다시 돌리세요:\n  - "
                         + "\n  - ".join(problems))


def sector_step(v):
    """등락률 → 색 단계. 빨강(상승) 4단계 · 중립 · 파랑(하락) 4단계.
    발산형이라 가운데는 색이 아니라 회색이고, 양쪽 팔의 구간 폭이 같다.
    색만으로는 못 읽으니 칸 안에 숫자를 항상 같이 적는다."""
    if v is None:
        return "s-na"
    a = abs(v)
    lv = 1 if a < 1 else 2 if a < 2 else 3 if a < 3 else 4
    if a < 0.3:
        return "s-0"
    return f"s-{'u' if v > 0 else 'd'}{lv}"


def build_sector(closes):
    """개요 탭의 섹터별 등락 히트맵.

    같은 섹터 종목들의 전일 대비 등락률을 단순평균(동일가중)한다. 시가총액
    가중이 아닌 이유: 시총가중이면 반도체 칸이 사실상 엔비디아 하나가 되어
    "업종이 움직였나"를 못 본다. 대신 칸을 누르면 종목별 값이 다 나온다.
    한 종목도 못 받아온 섹터는 지어내지 않고 "확인 필요"로 둔다.
    """
    # 미국과 한국은 마지막 거래일이 다르다. 한국 낮에 돌리면 한국 종목은 오늘,
    # 미국 종목은 어젯밤 값이다. 둘을 한 칸에 평균하는 것 자체는 "각 시장의 직전
    # 세션 대비"라는 뜻으로 유효하지만, 그냥 "전일 대비"라고만 적으면 같은 날짜인
    # 줄 오해하게 된다. 그래서 기준일을 시장별로 뽑아 칸마다 밝혀 둔다.
    ref = {k: last_close_date(closes, [r[3] for r in SECTIONS[k]]) for k in ("us30", "kr10")}
    per_sector, stale = {}, []
    for sec in ("us30", "kr10"):
        for name, _label, _dom, sym, _r in SECTIONS[sec]:
            g = SECTOR_OF.get(sym)
            if not g:
                continue
            try:
                c = closes[sym].dropna()
                if len(c) < 2:
                    raise ValueError("데이터 부족")
                # 그 시장의 최신 거래일보다 뒤처진 종목(거래정지 등)은 평균에서 뺀다.
                # 며칠 전 등락을 오늘 값인 것처럼 섞으면 업종 평균이 흐려진다.
                if ref[sec] and c.index[-1].date() < ref[sec]:
                    stale.append(name)
                    raise ValueError("기준일보다 뒤처진 시세")
                d = (float(c.iloc[-1]) / float(c.iloc[-2]) - 1) * 100
            except Exception:
                d = None
            per_sector.setdefault(g, []).append((name, d, sec))

    if stale:
        print(f"  [warn] 섹터 히트맵: 기준일보다 뒤처져 평균에서 뺀 종목 "
              f"{len(stale)}개 ({', '.join(stale[:6])})", file=sys.stderr)
    dstr = " · ".join(f"{'미국' if k == 'us30' else '한국'} "
                      f"{ref[k].isoformat() if ref[k] else '확인 필요'}"
                      for k in ("us30", "kr10"))

    tiles = []
    for g in SECTOR_ORDER:
        members = per_sector.get(g, [])
        got = [d for _n, d, _s in members if d is not None]
        avg = sum(got) / len(got) if got else None
        step = sector_step(avg)
        head = (f'{avg:+.2f}%' if avg is not None else "확인 필요")
        mkts = sorted({s for _n, _d, s in members})
        tip = (f"{g} · 동일가중 평균 · 기준일 " +
               " · ".join(f"{'미국' if k == 'us30' else '한국'} "
                          f"{ref[k].isoformat() if ref[k] else '확인 필요'}" for k in mkts) +
               (" · 두 시장이 섞여 있어 기준일이 서로 다를 수 있습니다"
                if len(mkts) > 1 else ""))
        detail = "".join(
            f'<div class="sec-m"><span class="sec-mn">{n}'
            + ('<span class="sec-mk">한</span>' if sec == "kr10" else "")
            + "</span>"
            + (f'<span class="sec-mv {"up" if d > 0 else "down" if d < 0 else "flat"}">'
               f'{d:+.2f}%</span>' if d is not None
               else '<span class="sec-mv needchk">확인 필요</span>')
            + "</div>"
            for n, d, sec in sorted(members, key=lambda x: (x[1] is None, -(x[1] or 0))))
        cnt = f"{len(got)}/{len(members)}" if len(got) != len(members) else str(len(members))
        tiles.append(
            '        <details class="sec-tile">\n'
            f'          <summary class="sec-sum {step}" title="{tip}">\n'
            f'            <span class="sec-name">{g}</span>\n'
            f'            <span class="sec-val">{head}</span>\n'
            f'            <span class="sec-cnt">{cnt}종목</span>\n'
            '          </summary>\n'
            f'          <div class="sec-list">{detail}</div>\n'
            '        </details>')
    return ('      <div class="sec-note">기준일 ' + dstr +
            ' · <span class="sec-mk">한</span> 표시가 한국 종목입니다</div>\n'
            '      <div class="sec-grid">\n' + "\n".join(tiles) + "\n      </div>")


# ------------------------------------------------------------------ 버전 · 변경 이력
#
# 화면 맨 위에 버전 뱃지가 뜨고, 누르면 개요 탭 맨 아래 변경 이력으로 간다.
# 새 기능을 넣거나 값이 달라지는 수정을 하면 여기 맨 앞에 한 줄 추가하고
# VERSION을 올린다. 자동으로 붙는 게 아니라 손으로 적는 자료다.
#   - "고침"은 화면에 나가던 숫자가 실제로 틀렸던 것
#   - "추가"는 없던 정보가 생긴 것
#   - "정리"는 숫자는 그대로인데 보기가 달라진 것
VERSION = "2.9"

CHANGELOG = [
    ("2.9", "2026-08-31", [
        ("고침", "<b>상단 티커 띠가 여러 겹으로 겹쳐 보이고 글씨가 안 보이던 문제.</b> "
                "트레이딩뷰는 시세 화면(iframe)을 제가 비우던 칸 <b>바깥</b>에 붙이는데, "
                "v2.6에서 테마 전환용으로 다시 붙이는 코드를 넣으면서 이전 것을 못 지웠습니다. "
                "그래서 테마를 바꿀 때마다 위젯이 한 겹씩 쌓였고, 밝은 테마로 그려진 겹이 "
                "밑에 남아 어두운 글씨가 비쳐 보였습니다. 이제 컨테이너를 통째로 비우고 "
                "다시 만듭니다 — 테마를 다섯 번 바꿔도 하나만 남는 것을 확인했습니다."),
        ("정리", "티커 띠 높이를 고정하고 넘치는 부분을 잘라내, 위젯이 잘못되더라도 "
                "아래 탭 줄을 덮지 않게 했습니다."),
    ]),
    ("2.8", "2026-08-31", [
        ("고침", "빅테크분석에서 <b>매출은 올라왔는데 영업이익이 아직 없는 분기가 통째로 "
                "사라지고 있었습니다.</b> 야후가 새 분기를 넣을 때 항목을 한꺼번에 채우지 "
                "않는데, 예전 코드는 둘 다 있는 분기만 남겨서 갓 발표된 분기가 아무 표시 "
                "없이 빠졌습니다. 이제 매출이 있으면 분기를 살리고 이익 칸만 \"확인 필요\"로 둡니다."),
        ("추가", "어떤 카드가 다른 카드보다 뒤처지면 제목 옆에 <b>\"26 3Q 미반영\"</b> 같은 "
                "표시가 붙습니다. 회사는 발표했는데 야후에 아직 안 올라온 상태를 구분하기 "
                "위해서입니다 — 엔비디아처럼 발표 직후 며칠간 생기는 일입니다."),
    ]),
    ("2.7", "2026-08-31", [
        ("추가", "미국 종목을 <b>TOP75로 넓혔습니다</b>(21종목 추가). 마벨·퀄컴·아나로그디바이스, "
                "펩시코·맥도날드·디즈니, 버라이즌·티모바일·AT&amp;T, 찰스슈왑·블랙록·블랙스톤 등이 "
                "들어왔습니다. <b>로빈후드는 미국 132위라 아직 들어오지 않습니다.</b>"),
        ("고침", "<b>팔로알토네트웍스(미국 39위)가 그동안 빠져 있었습니다.</b> 55위 종목은 있는데 "
                "39위가 없던 상태라, 확장과 별개로 메웠습니다."),
        ("고침", "캐터필러가 <b>항공우주·방산</b>으로 잘못 분류돼 있어 새로 만든 <b>산업재</b>로 "
                "옮겼습니다(유니온퍼시픽·서던코퍼와 같은 묶음)."),
        ("추가", "업종에 <b>통신·미디어</b>(버라이즌·티모바일·AT&amp;T·디즈니·넷플릭스)와 "
                "<b>산업재</b>를 새로 만들었습니다. 넷플릭스는 전에 혼자라 소프트웨어에 뒀는데 "
                "디즈니가 들어오면서 제자리를 찾았습니다."),
        ("정리", "TSMC·ASML·HSBC·노바티스·로열뱅크·ARM처럼 <b>본사가 미국이 아닌 기업</b>에 "
                "\"해외\" 표시를 붙였습니다 — 왼쪽 순위 뱃지가 미국 기업 순위가 아니라 "
                "이 목록 안의 시가총액 순서라는 걸 구분하기 위해서입니다."),
    ]),
    ("2.6", "2026-08-31", [
        ("고침", "<b>야간모드에서 상단 티커 띠와 S&amp;P500 히트맵 글씨가 거의 안 보였습니다.</b> "
                "트레이딩뷰 위젯은 만들 때 색 테마를 한 번 정해 넣는 구조라 나중에 어둡게 "
                "바꿔도 따라오지 않았는데, 밝은 테마로 굳어 있어서 어두운 배경 위에 "
                "어두운 글씨가 얹혔습니다. 이제 위젯을 붙일 때 현재 테마를 넣고, "
                "테마를 바꾸면 다시 붙입니다(기기 설정만 어둡게 해둔 경우도 포함)."),
    ]),
    ("2.5", "2026-08-31", [
        ("정리", "<b>시총순위 탭을 없앴습니다.</b> 반기별 순위 히트맵과 그 수기 데이터는 "
                "저장소 이력에 남아 있어 되살릴 수 있습니다."),
        ("추가", "대신 <b>시가총액을 종목 카드 안</b>으로 옮겼습니다 — 카드를 펼치면 "
                "\"밸류에이션 · 재무\" 첫 줄에 금액이 나옵니다(미국은 달러, 한국은 원). "
                "정렬 기준으로도 고를 수 있습니다."),
        ("추가", "<b>탭 순서를 바꿀 수 있습니다.</b> 탭 줄 오른쪽 \"↕ 순서\"를 누르고 "
                "▲▼로 옮기면 이 브라우저에 기억됩니다."),
    ]),
    ("2.4", "2026-08-17", [
        ("추가", "반도체 탭에 <b>낸드 점유율</b>(삼성·SK하이닉스·마이크론·키옥시아·샌디스크·YMTC)과 "
                "<b>낸드 계약가 추이</b> 카드를 넣었습니다. ’26 2분기 매출 점유율은 아직 발표 전이라 "
                "비워 뒀고, 계약가는 확정치가 나온 분기가 ’25 1분기 하나뿐이라 나머지는 전망으로 표시했습니다."),
        ("정리", "카드를 펼쳤을 때 나오는 13칸을 <b>가격 위치 · 밸류에이션/재무 · 거래 · 기술 지표</b> "
                "네 묶음으로 나누고 사이에 제목 줄을 넣었습니다."),
        ("정리", "정렬 기준을 열 번호가 아니라 <b>열 이름</b>으로 찾도록 바꿨습니다 — 앞으로 칸이 "
                "늘거나 순서가 바뀌어도 엉뚱한 열로 정렬되지 않습니다."),
        ("고침", "개요 탭 히트맵 카드에 <b>&lt;/div&gt;가 하나 더 있어</b> 그 뒤 내용이 탭 밖으로 "
                "새어 나오고 있었습니다(v1.9에서 경제 캘린더를 지울 때 남은 자국)."),
    ]),
    ("2.3", "2026-08-17", [
        ("고침", "빅테크분석의 전년 동기 대비 증감률이 <b>전년이 적자일 때 부호가 뒤집혔습니다</b>. "
                "인텔은 영업이익이 늘었는데 −252.9%로 찍혔습니다 — 적자를 기준으로 나누면 "
                "생기는 문제라, 이제 %가 아니라 \"적자 → 흑자\"처럼 무슨 일이 있었는지로 적습니다."),
        ("추가", "카드 제목에 <b>사상최고 대비</b>를 넣어 일간·주간·연간과 함께 네 줄로 보입니다."),
        ("추가", "빅테크분석 탭에 <b>일라이릴리·월마트·인텔·팔란티어</b>를 넣어 12종목이 됐습니다."),
        ("정리", "개요 지수 카드를 종목 카드와 같은 좌우 배치로 바꿔 세로 길이를 줄였습니다."),
        ("정리", "v2.2에 넣었던 <b>원화 기준 수익률</b> 칸은 요청에 따라 뺐습니다."),
    ]),
    ("2.2", "2026-08-16", [
        ("추가", "<b>PBR·ROE·부채비율</b>을 펼침 표에 넣었습니다."),
        ("추가", "<b>원화 기준 수익률</b> — 미국 종목을 환율까지 반영해 원화로 환산한 주간·연간 수익률."),
        ("추가", "<b>스크리너</b> — PER·PBR·ROE·부채비율·RSI·52주 저점/고점대비·거래량 8개 조건을 동시에 겁니다."),
        ("추가", "<b>52주 위치 게이지</b>와 <b>갱신 멈춤 경보</b>(거래일 3일 이상 밀리면 상단에 띠)."),
        ("정리", "개요 지수 카드의 트레이딩뷰 차트를 뺐습니다 — 위젯이 카드 밖으로 넘쳐 아래를 덮었습니다."),
    ]),
    ("2.1", "2026-08-16", [
        ("고침", "<b>사상최고 대비</b>가 전체 기간 시세를 못 받으면 조용히 15개월 최고가로 대체되고 "
                "있었습니다. 이제 실제로 받은 종목만 숫자를 내고 나머지는 \"확인 필요\"입니다."),
        ("고침", "<b>52주 고점/저점대비</b>가 1년치 데이터가 없는 종목(스페이스X 등)에도 계산됐습니다."),
        ("고침", "<b>시총 TOP10</b>이 한국 종목 개수까지 세는 바람에 미국이 대부분 빠져도 게시됐습니다."),
        ("고침", "<b>실적 캘린더</b>가 40건 제한을 달력에도 적용해 둘째 달 일정이 통째로 사라졌습니다."),
        ("고침", "<b>하이일드 스프레드</b>가 카드 머리에서만 %p를 %로 적었습니다(10bp → \"+3.33%\")."),
        ("고침", "<b>장단기 금리차</b>가 서로 다른 날짜의 두 금리를 뺐습니다."),
        ("고침", "미국 <b>실적 발표일</b>을 한국 날짜로 걸러, 오늘 밤 발표하는 회사가 빠졌습니다."),
        ("고침", "장중에 <b>거래량 배수</b>가 부분 거래량으로 계산돼 오전엔 늘 \"0.1배\"로 나왔습니다."),
        ("고침", "연도 라벨이 실행 시각 기준이라 새해 첫날 어긋났습니다 — 시세 날짜 기준으로 바꿨습니다."),
        ("고침", "RSI가 계산 불가일 때 \"nan\"으로 찍히던 것을 \"확인 필요\"로 바꿨습니다."),
    ]),
    ("2.0", "2026-08-16", [
        ("추가", "<b>PER·선행 PER</b>, <b>거래대금·평소 대비 거래량</b>, <b>52주 저점대비</b>."),
        ("추가", "개요 탭에 <b>섹터별 등락 히트맵</b> — 미국 60 + 한국 20을 9개 업종으로."),
        ("고침", "<b>스페이스X</b>는 2026-06-12에 나스닥 상장(SPCX)했는데 비상장으로 처리돼 순위에서 빠져 있었습니다."),
        ("추가", "실적 캘린더에 <b>CPI·PPI·PCE</b> 일정(BLS·BEA 공식 일정표 기준)."),
    ]),
    ("1.9", "2026-08-16", [
        ("추가", "카드 제목 띠에 <b>일간·주간·연간</b> 등락률."),
        ("정리", "쓰지 않던 경제 캘린더 위젯을 없앴고, 실적 발표일이 올라오는 기준을 설명에 밝혔습니다."),
    ]),
    ("1.8", "2026-08-15", [
        ("추가", "<b>반도체</b>·<b>자동차</b> 탭(점유율·가격 추이), 미국 <b>TOP60</b>으로 확장."),
        ("추가", "야간모드, 전체 펼치기 버튼, 시가총액 순위 뱃지."),
        ("정리", "종목 카드를 두 줄(이름·티커 / 가격)로 바꾸고 모든 카드 높이를 맞췄습니다."),
    ]),
]


def build_changelog():
    kind_cls = {"고침": "cl-fix", "추가": "cl-new", "정리": "cl-tidy"}
    out = []
    for i, (ver, date, items) in enumerate(CHANGELOG):
        lis = "".join(
            f'<li><span class="cl-tag {kind_cls.get(k, "")}">{k}</span>'
            f'<span class="cl-txt">{t}</span></li>'
            for k, t in items)
        out.append(
            f'        <details class="cl-ver"{" open" if i == 0 else ""}>\n'
            f'          <summary><b>v{ver}</b><span class="cl-date">{date}</span>'
            f'{"<span class=" + chr(34) + "cl-now" + chr(34) + ">현재</span>" if i == 0 else ""}'
            f'<span class="cl-cnt">{len(items)}건</span></summary>\n'
            f'          <ul class="cl-list">{lis}</ul>\n'
            '        </details>')
    return "\n".join(out)


def load_ath_cache():
    """저장해 둔 사상최고 값을 읽는다. 없거나 깨져 있으면 빈 값으로 시작한다.

    tried는 "전체 기간 조회를 한 번이라도 시도해 본 심볼" 목록이다. 야후가 끝내
    시세를 안 주는 심볼(비상장 선물 등)이 하나라도 있으면, 이게 없을 때 '아직 못
    받은 종목이 있다'는 판단이 영영 참이 되어 4분짜리 전체 조회를 매 실행마다
    다시 돌게 된다.
    """
    try:
        with open(ATH_CACHE, encoding="utf-8") as f:
            d = json.load(f)
        aths = {k: float(v) for k, v in d.get("aths", {}).items()
                if isinstance(v, (int, float)) and math.isfinite(float(v)) and v > 0}
        return aths, d.get("date", ""), set(d.get("tried", []))
    except FileNotFoundError:
        return {}, "", set()
    except Exception as e:
        print(f"  [warn] {ATH_CACHE} 읽기 실패, 새로 만듭니다: {e}", file=sys.stderr)
        return {}, "", set()


def save_ath_cache(aths, date_str, tried=()):
    """사상최고 값을 저장한다. 실패해도 대시보드 갱신은 계속 진행한다."""
    try:
        with open(ATH_CACHE, "w", encoding="utf-8") as f:
            json.dump({"date": date_str,
                       "tried": sorted(tried),
                       "aths": {k: round(v, 6) for k, v in sorted(aths.items())}},
                      f, ensure_ascii=False, indent=0, sort_keys=True)
    except Exception as e:
        print(f"  [warn] {ATH_CACHE} 저장 실패: {e}", file=sys.stderr)


def last_close_date(closes, syms):
    """주어진 종목들이 실제로 담고 있는 마지막 거래일을 돌려준다.

    화면에 "언제 돌렸는지"가 아니라 "언제 종가인지"를 적기 위한 값이다. 종목마다
    상장폐지·거래정지로 며칠씩 뒤처진 게 섞일 수 있어서, 가장 최근 날짜를 쓴다.
    하나도 못 구하면 None을 돌려주고, 호출부에서 "확인 필요"로 적는다.
    """
    best = None
    for sym in syms:
        s = closes.get(sym)
        if s is None:
            continue
        try:
            idx = s.dropna().index
            if len(idx) == 0:
                continue
            d = idx[-1].date()
        except Exception:
            continue
        if best is None or d > best:
            best = d
    return best


def close_label(d, tzname, close_h, close_m):
    """거래일을 화면 문구로 만든다.

    2시간마다 돌기 때문에 미국장이 열려 있는 동안에도 실행된다. 그때 야후가 주는
    당일 봉은 아직 확정된 종가가 아니라 진행 중인 값이다. 그걸 "종가"라고 적으면
    거짓말이 되므로, 장이 안 끝났으면 "장중"이라고 적는다.
    """
    if d is None:
        return "확인 필요"
    try:
        now = datetime.datetime.now(ZoneInfo(tzname))
        if d == now.date() and (now.hour, now.minute) < (close_h, close_m):
            return f"{d.isoformat()} 장중"
    except Exception:
        pass   # 시간대 정보를 못 읽으면 조용히 "종가"로 둔다 — 갱신 자체를 막지는 않는다
    return f"{d.isoformat()} 종가"


def splice(html, marker, body):
    start, end = f"<!--{marker}:START-->", f"<!--{marker}:END-->"
    i, j = html.find(start), html.find(end)
    if i == -1 or j == -1:
        print(f"  [error] markers for {marker} not found", file=sys.stderr)
        return html, False
    return html[: i + len(start)] + "\n" + body + "\n      " + html[j:], True


def main(html_path):
    check_tables()          # 표끼리 어긋났으면 여기서 멈춘다 (조용히 빠지는 것 방지)
    all_syms = sorted(
        ({sym for rows in SECTIONS.values() for _, _, _, sym, _ in rows}
         | {sym for _, _, sym, _, _ in INDEXES}      # 개요 탭 주요 지수 카드
         | {Y10, Y02}                                # 국채금리 카드 (표에는 안 실리지만 받아야 한다)
         | {KR_BOND_ETF})                            # 한국 심리지수 계산용
        - set(FRED_SYMS)   # FRED 심볼은 야후가 아니라 fetch_fred()로 따로 받는다
    )
    print(f"downloading {len(all_syms)} symbols...")
    # auto_adjust=True : 액면분할·배당을 보정한 수정주가로 받는다.
    # (보정 안 된 원주가를 쓰면 분할일이 하루 만에 -50% 폭락한 것처럼 계산된다)
    data = yf.download(all_syms, period="15mo", interval="1d",
                       auto_adjust=True, progress=False, group_by="ticker", threads=True)

    closes, vols = {}, {}
    for sym in all_syms:
        try:
            s = data[sym]["Close"] if isinstance(data.columns, pd.MultiIndex) else data["Close"]
            if s.dropna().empty:
                raise ValueError("empty")
            closes[sym] = s
        except Exception as e:
            print(f"  [warn] no data for {sym}: {e}", file=sys.stderr)
        try:
            # 거래량은 없어도 표 전체가 죽으면 안 되므로 따로 감싼다
            v = data[sym]["Volume"] if isinstance(data.columns, pd.MultiIndex) else data["Volume"]
            if not v.dropna().empty:
                vols[sym] = v
        except Exception:
            pass

    # 사상 최고가(전체 기간 최고 종가)는 위의 15개월치로는 알 수 없어서 따로 받는다.
    # 여기서 실패해도 표 전체가 죽으면 안 되므로, 실패하면 aths를 비워 두고
    # "사상최고 대비" 칸만 확인 필요로 남긴다 — 값을 만들어 채우지 않는다.
    today_kst = datetime.datetime.now(KST).date().isoformat()
    aths, cache_date, tried = load_ath_cache()

    # 하루 한 번은 전체 기간을 다시 받는다. 액면분할이 생기면 auto_adjust가 과거 주가를
    # 소급해서 낮추기 때문에, 저장해 둔 값을 계속 쓰면 분할 전 고점이 그대로 남아
    # "사상최고 대비"가 실제보다 나쁘게 나온다. 그래서 캐시를 믿되 매일 한 번 갈아엎는다.
    # "아직 시도조차 안 해 본 심볼"만 센다. 시도했는데 야후가 값을 안 준 심볼까지
    # 세면 need_full이 영원히 참이 되어 캐시가 무의미해진다.
    missing = [s for s in all_syms if s not in aths and s not in tried]
    need_full = (cache_date != today_kst) or bool(missing)
    full_ok = False
    if need_full:
        why = "캐시 없음/날짜 지남" if cache_date != today_kst else f"신규 종목 {len(missing)}개"
        print(f"downloading all-time history for 사상최고... ({why})")
        try:
            hist = yf.download(all_syms, period="max", interval="1d",
                               auto_adjust=True, progress=False, group_by="ticker",
                               threads=True)
            got = 0
            for sym in all_syms:
                try:
                    s = (hist[sym]["Close"] if isinstance(hist.columns, pd.MultiIndex)
                         else hist["Close"]).dropna()
                    if not s.empty:
                        aths[sym] = float(s.max())
                        got += 1
                except Exception:
                    pass
            tried.update(all_syms)     # 값을 못 받은 심볼도 "시도했음"으로 남긴다
            # 거의 다 실패한 실행을 성공으로 찍으면, 캐시 날짜가 오늘로 박히면서
            # 그날 하루 종일 전체 조회를 건너뛰게 된다. 9할은 받아야 성공으로 본다.
            full_ok = got >= len(all_syms) * 0.9
            print(f"  사상최고 확보 {got}/{len(all_syms)} (전체 조회)")
            if not full_ok:
                print(f"  [warn] 전체 조회가 {got}/{len(all_syms)}밖에 안 돼 캐시 날짜를 "
                      "갱신하지 않습니다 — 다음 실행에서 다시 시도합니다", file=sys.stderr)
        except Exception as e:
            # 전체 조회가 실패해도 저장해 둔 값이 있으면 그걸 계속 쓴다.
            print(f"  [warn] 전체 기간 시세 실패: {e}", file=sys.stderr)
    else:
        print(f"  사상최고: 오늘 저장된 값 재사용 {len(aths)}/{len(all_syms)} (전체 조회 건너뜀)")

    # 저장된 값이든 방금 받은 값이든, 최근 15개월치에서 더 높은 종가가 나왔으면 그걸로 올린다.
    # 오늘 새 신고가를 찍은 종목이 캐시 재사용 실행에서 누락되지 않게 하는 부분.
    bumped = 0
    for sym, s in closes.items():
        if sym.startswith("FRED:"):
            continue
        try:
            hi = float(s.dropna().max())
        except Exception:
            continue
        if not math.isfinite(hi):
            continue
        # 이미 "진짜 전체 기간 최고가"를 아는 종목만 위로 갱신한다.
        # 모르는 종목에 15개월 최고가를 대신 넣으면, 1년보다 더 전에 고점을 찍은
        # 종목의 "사상최고 대비"가 실제보다 덜 빠진 것처럼 조용히 틀리게 나온다.
        # 값이 없으면 없는 대로 두고 화면에는 "확인 필요"가 나가게 한다.
        if sym in aths and hi > aths[sym]:
            bumped += 1
            aths[sym] = hi
    if bumped:
        print(f"  사상최고 갱신 {bumped}종목 (최근 15개월 중 신고가)")
    no_ath = [s for s in all_syms if s not in aths and not s.startswith("FRED:")]
    if no_ath:
        print(f'  [warn] 사상최고를 모르는 종목 {len(no_ath)}개 — 그 칸은 "확인 필요"로 '
              f"둡니다: {', '.join(no_ath[:10])}{'…' if len(no_ath) > 10 else ''}",
              file=sys.stderr)
    # 전체 조회가 실패했으면 날짜를 오늘로 찍지 않는다. 그래야 다음 실행에서 다시 시도한다.
    save_ath_cache(aths, today_kst if full_ok else cache_date, tried)

    print(f"downloading {len(FRED_SYMS)} FRED series...")
    for sym in FRED_SYMS:
        try:
            closes[sym] = fetch_fred(sym.split(":", 1)[1])
        except Exception as e:
            print(f"  [warn] no data for {sym}: {e}", file=sys.stderr)

    with open(html_path, encoding="utf-8") as f:
        html = f.read()

    # 시가총액: 카드의 순위 뱃지와 펼침 표의 시가총액 칸에 쓴다.
    # 실패해도 죽지 않는다 — 순위 뱃지가 안 붙고 그 칸만 "확인 필요"가 된다.
    print("fetching market caps & PER...")
    mcaps, pers = {}, {}
    for sec in ("us30", "kr10"):
        for _, label, _, sym, _ in SECTIONS[sec]:
            try:
                mc = yf.Ticker(sym).fast_info["market_cap"]
                if mc and mc > 0:
                    mcaps[sym] = float(mc)
            except Exception:
                pass
            # PER·PBR·ROE·부채비율은 fast_info에 없어서 info를 따로 부른다. 느리고
            # 가끔 비어서 오는데, 실패하면 그 칸만 "확인 필요"가 되고 나머지는 멀쩡하다.
            # 한 번 부른 info에서 네 지표를 다 뽑으므로 요청 수는 늘지 않는다.
            try:
                pers[sym] = pick_valuation(yf.Ticker(sym).info or {})
            except Exception:
                pass
    n_target = len(SECTIONS["us30"]) + len(SECTIONS["kr10"])
    print(f"  시가총액 확보 {len(mcaps)}/{n_target} · PER 확보 {len(pers)}/{n_target}")
    if len(pers) < n_target * 0.5:
        print(f"  [warn] PER을 {len(pers)}개밖에 못 받았습니다 — 나머지 칸은 "
              '"확인 필요"로 남습니다', file=sys.stderr)

    ok_count = 0
    for section, rows in SECTIONS.items():
        rows = rank_sorted(section, rows, mcaps)
        body = "\n".join(
            make_row(*row, closes, aths,
                     ETF_DESC.get(row[0]) if section == "etf" else None,
                     ETF_TAG.get(row[0]) if section == "etf" else None,
                     rank, vols, pers, section == "etf", mcaps)
            for row, rank in rows)
        start = f"<!--SUPP:{section}:START-->"
        end = f"<!--SUPP:{section}:END-->"
        i, j = html.find(start), html.find(end)
        if i == -1 or j == -1:
            print(f"  [error] markers for {section} not found", file=sys.stderr)
            continue
        html = html[: i + len(start)] + "\n" + body + "\n          " + html[j:]
        ok_count += 1

    html, ver_ok = splice(html, "CHANGELOG", build_changelog())
    for a, b in (("VER", "/VER"), ("VER2", "/VER2")):
        html = re.sub(rf"(<!--{a}-->)(.*?)(<!--{b}-->)",
                      lambda m: m.group(1) + f"v{VERSION}" + m.group(3), html, flags=re.S)

    print("building sector heatmap...")
    html, sec_ok = splice(html, "SECTOR", build_sector(closes))

    print("building index cards...")
    html, idx_ok = splice(html, "IDX", build_idx(closes, aths))

    print("building signals...")
    html, sig_ok = splice(html, "SIG", build_signals(closes))

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


    # 화면에는 "스크립트를 돌린 날"이 아니라 "숫자가 어느 거래일 종가인지"를 적는다.
    # 예전에는 실행 날짜만 찍었는데, 한국 아침에 보면 미국 숫자는 아직 이틀 전 종가인데
    # 화면에는 오늘 날짜가 적혀 있어서 사실과 다르게 읽혔다. 그래서 시장별로 나눠 적는다.
    # 주식 표에 실린 종목만 본다. 비트코인·환율·원자재 선물은 24시간 돌아서 늘 오늘
    # 날짜가 찍히는데, 그걸 섞으면 미국 주식이 아직 어제 종가인데도 오늘로 보이게 된다.
    us_d = last_close_date(closes, [r[3] for r in SECTIONS.get("us30", [])])
    kr_d = last_close_date(closes, [r[3] for r in SECTIONS.get("kr10", [])])
    now_kst = datetime.datetime.now(KST)
    today = now_kst.date().isoformat()
    stamp = (f"미국 {close_label(us_d, 'America/New_York', 16, 0)} · "
             f"한국 {close_label(kr_d, 'Asia/Seoul', 15, 30)} "
             f"(자동 갱신 {now_kst.strftime('%m-%d %H:%M')})")
    ds, de = "<!--SUPPDATE-->", "<!--/SUPPDATE-->"
    i, j = html.find(ds), html.find(de)
    if i != -1 and j != -1:
        html = html[: i + len(ds)] + stamp + html[j:]

    with open(html_path, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"updated {ok_count}/{len(SECTIONS)} sections, "
          f"{len(closes)}/{len(all_syms) + len(FRED_SYMS)} symbols fetched, "
          f"idx={'ok' if idx_ok else 'MARKER MISSING'}, "
          f"earn={'ok' if ecal_ok and elist_ok else 'MARKER MISSING'}({len(earn_rows)}건), "
          f"fng={'ok' if fng_ok else 'MARKER MISSING'}, "
          f"yield={'ok' if yld_ok else 'MARKER MISSING'}, "
          f"fin={'ok' if fin_ok else 'MARKER MISSING'}, "
          f"sig={'ok' if sig_ok else 'MARKER MISSING'}, "
          f"sector={'ok' if sec_ok else 'MARKER MISSING'}, "
          f"ver=v{VERSION}{'' if ver_ok else '(MARKER MISSING)'}, "
          f"run={today}, 미국종가={us_d or '확인 필요'}, 한국종가={kr_d or '확인 필요'}")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "index.html")
