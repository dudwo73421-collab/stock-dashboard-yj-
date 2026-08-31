# -*- coding: utf-8 -*-
"""반도체 탭(D램·HBM·파운드리 점유율 + D램 가격)을 만든다.

이 탭은 자동 갱신되지 않는 수기 카드다. 야후 파이낸스에는 점유율·메모리 가격이
없고, 이 숫자를 만드는 Counterpoint·TrendForce는 무료 API를 주지 않는다.
분기 자료가 새로 나오면(분기 말 +4~6주) 아래 표를 고쳐서 다시 돌리면 된다.

숫자는 전부 실제로 확인한 출처가 있는 값만 넣는다. 못 구한 칸은 None으로 두면
선이 끊기고 표에는 "확인 필요"로 나온다 — 절대 추정해서 채우지 않는다.
"""
import html as H

UPDATED = "2026-08-15"
NEXT_DUE = "2026년 3분기 자료 (11월경)"

# ── 기업별 고유색 (밝은 화면 / 어두운 화면) ────────────────────────────────
# 색은 기업을 따라간다 — D램 차트의 삼성과 파운드리 차트의 삼성이 같은 파랑이다.
COLORS = {
    "삼성전자":      ("#2a78d6", "#3987e5"),
    "SK하이닉스":    ("#eb6834", "#d95926"),
    "마이크론":      ("#1baf7a", "#199e70"),
    "창신메모리":    ("#eda100", "#c98500"),
    "난야":          ("#e87ba4", "#d55181"),
    "TSMC":          ("#4a3aa7", "#9085e9"),
    "SMIC":          ("#008300", "#00a12f"),
    "UMC":           ("#e34948", "#e66767"),
    "글로벌파운드리": ("#8a6d3b", "#a98a55"),
    "키옥시아":      ("#eda100", "#c98500"),
    "샌디스크":      ("#e87ba4", "#d55181"),
    "YMTC":          ("#008300", "#00a12f"),
    "기타":          ("#898781", "#898781"),
}

# ── D램 점유율 (Counterpoint, 매출 기준) ───────────────────────────────────
DRAM_Q = ["'25 1Q", "'25 2Q", "'25 3Q", "'25 4Q", "'26 1Q", "'26 2Q"]
DRAM = [
    ("삼성전자",   [34, 33, 33, 36, 38, 39]),
    ("SK하이닉스", [36, 39, 33, 32, 29, 26]),
    ("마이크론",   [25, 22, 26, 22, 22, 25]),
    ("창신메모리", [3, 4, 6, 8, 8, 7]),
    ("난야",       [1, 1, 2, 2, 2, None]),
    ("기타",       [0, 1, 1, 1, 1, None]),
]
DRAM_SRC = [
    ("Counterpoint 분기 점유율 (’25 1Q~’26 1Q)",
     "https://counterpointresearch.com/en/insights/global-dram-and-hbm-market-share"),
    ("Counterpoint ’26 2Q (삼성 39 · SK 26 · 마이크론 25)",
     "https://counterpointresearch.com/en/insights/ai-demand-reshapes-dram-rankings-in-q2-2026"),
    ("TrendForce ’26 1Q 대조 (38.5 / 28.8 / 22.4)",
     "https://www.trendforce.com/presscenter/news/20260601-13070.html"),
]
DRAM_NOTE = ("매출 기준 점유율입니다. 이번 사이클은 D램 가격이 크게 올라서 "
             "<b>출하량(비트) 점유율과는 다릅니다</b> — 업계 매출이 ’25 1Q $270억에서 "
             "’26 1Q 약 $970억으로 뛰었습니다. ’26 2분기는 상위 3사만 Counterpoint가 "
             "직접 밝혔고 창신 7%는 2차 보도 기준, 난야·기타는 아직 공개 전이라 비워뒀습니다.")

# ── HBM 점유율 (Counterpoint, 매출 기준) ───────────────────────────────────
HBM_Q = ["'24 2Q", "'24 3Q", "'24 4Q", "'25 1Q", "'25 2Q", "'25 3Q", "'25 4Q", "'26 1Q"]
HBM = [
    ("SK하이닉스", [57, 53, 51, 69, 64, 56, 57, 58]),
    ("삼성전자",   [38, 35, 40, 13, 15, 23, 22, 21]),
    ("마이크론",   [5, 11, 9, 18, 21, 21, 21, 21]),
]
HBM_SRC = [
    ("Counterpoint 분기 HBM 점유율",
     "https://counterpointresearch.com/en/insights/global-dram-and-hbm-market-share"),
    ("SK하이닉스 뉴스룸 — 출하량 62%(’25 2Q) / 매출 57%(’25 3Q)",
     "https://news.skhynix.com/en/2026-market-outlook-focus-on-the-hbm-led-memory-supercycle/"),
    ("TrendForce — 삼성 HBM4 수율 80%(’26 8월)",
     "https://www.trendforce.com/news/2026/08/10/news-samsungs-hbm4-yield-reportedly-hits-80-as-race-to-supply-vera-rubin-heats-up-sk-hynix-labor-talks-add-a-twist/"),
]
HBM_NOTE = ("역시 매출 기준입니다. <b>출하량 기준과 숫자가 꽤 다릅니다</b> — ’25 2분기는 "
            "매출로는 64/15/21인데 출하량으로는 62/17/21입니다. 마이크론이 출하량에서 "
            "삼성을 처음 앞선 게 ’25 2분기이고, ’26 1분기에는 둘 다 21%로 같습니다. "
            "’26 2분기 HBM 업체별 점유율은 아직 어디에도 공개되지 않았습니다. "
            "HBM4는 삼성이 ’26년 2월 먼저 양산을 시작했고 SK하이닉스가 2분기부터 "
            "본격 출하에 들어갔습니다.")

# ── 낸드 점유율 (Counterpoint, 매출 기준) ──────────────────────────────────
# D램 카드와 같은 출처(Counterpoint)를 쓴다. TrendForce도 낸드 순위를 내지만
# 벤더 일부만 %로 공개하고(키옥시아·샌디스크는 대부분 분기가 미공개) YMTC는
# 아예 언급하지 않아, 한 줄로 이어지는 시계열을 만들 수 없다.
# 주의: TrendForce 보도자료의 "매출액"에서 점유율을 역산하면 안 된다. 분모가
# 상위 5개사 합계가 아니라 전체 시장이라 실제 발표치와 어긋난다(2Q25 SK는
# 역산 22.8% vs 발표 21.1%).
# 계열 순서 = 색 슬롯 순서다. 이 순서를 바꾸면 인접 색 대비 검증이 깨진다.
NAND_Q = ["'25 1Q", "'25 2Q", "'25 3Q", "'25 4Q", "'26 1Q", "'26 2Q"]
NAND = [
    ("삼성전자",   [31, 32, 32, 27, 29, None]),
    ("SK하이닉스", [16, 20, 18, 22, 18, None]),
    ("마이크론",   [15, 13, 12, 13, 13, None]),
    ("키옥시아",   [17, 14, 16, 15, 14, None]),
    ("샌디스크",   [13, 12, 12, 13, 13, None]),
    ("YMTC",       [8, 9, 10, 11, 13, None]),
]
NAND_SRC = [
    ("Counterpoint 낸드 분기 점유율 (’25 1Q~’26 1Q)",
     "https://counterpointresearch.com/en/insights/global-nand-memory-market-share"),
    ("Counterpoint ’26 2Q 출하량 기준 (매출 아님)",
     "https://counterpointresearch.com/en/insights/server-led-essds-hit-48-percent-of-nand-shipments"),
    ("TrendForce ’26 1Q 대조 (삼성 31.6 · SK 17.6 · 키옥시아/마이크론/샌디스크 각 13.9)",
     "https://www.trendforce.com/presscenter/news/20260525-13058.html"),
]
NAND_NOTE = ("매출 기준이고 <b>이 여섯 회사만으로 100%를 나눈 값</b>이라 D램 카드와 달리 "
             "\"기타\" 칸이 없습니다(Counterpoint가 낸드는 6사만 집계). ’26 2분기는 "
             "<b>매출 기준 점유율이 아직 발표되지 않아 통째로 비웠습니다</b> — "
             "출하량(비트) 기준으로는 삼성 25% · SK하이닉스 22% · YMTC 14%가 나왔지만 "
             "기준이 달라 같은 선에 이어 붙이지 않았습니다. 같은 분기를 TrendForce로 보면 "
             "1~3%p 차이가 납니다(’26 1Q 삼성 29 vs 31.6). <b>SK하이닉스는 Solidigm을 "
             "포함</b>한 수치이고, 샌디스크는 2025년 2월 웨스턴디지털에서 분할된 뒤 기준입니다. "
             "눈여겨볼 건 <b>YMTC가 8%에서 13%까지 올라온 것</b>과 삼성이 30%선에서 "
             "밀렸다는 점입니다.")

# 낸드 계약가 (TrendForce, 전분기 대비). 확정치를 %로 다시 밝힌 분기가 거의 없어
# 대부분 발표 당시 전망치다. ’25 2분기는 종합 수치를 아예 내지 않아 비워 둔다.
NAND_PRICE = [
    ("'25 1Q", -15, -15, True),
    ("'25 2Q", None, None, False),
    ("'25 3Q", 5, 10, False),
    ("'25 4Q", 5, 10, False),
    ("'26 1Q", 85, 90, False),
    ("'26 2Q", 70, 75, False),
    ("'26 3Q", 10, 15, False),
]
NAND_SPOT = [
    ("512Gb TLC 웨이퍼 (현물)", "$21.13", "현물"),
]
NAND_PRICE_SRC = [
    ("TrendForce ’25 1Q 확정 (업계 ASP -15% QoQ)",
     "https://www.trendforce.com/presscenter/news/20250529-12600.html"),
    ("TrendForce ’26 1Q 전망 (+85~90%)",
     "https://www.trendforce.com/presscenter/news/20260303-12943.html"),
    ("TrendForce ’26 2Q 전망 (+70~75%)",
     "https://www.trendforce.com/presscenter/news/20260331-12995.html"),
    ("TrendForce ’26 3Q 전망 (+10~15%)",
     "https://www.trendforce.com/presscenter/news/20260703-13134.html"),
    ("TrendForce 현물가 (2026-08-12 발표)",
     "https://www.trendforce.com/news/2026/08/12/insights-memory-spot-price-update-dram-spot-trading-stays-subdued-as-pricing-gap-persists-ddr4-up-0-93/"),
]
NAND_PRICE_NOTE = ("<b>확정 실적으로 다시 발표된 분기는 ’25 1분기 하나뿐</b>이고 나머지는 "
                   "전부 발표 당시 전망치입니다(연한 막대). TrendForce가 낸드는 사후에 "
                   "확정 계약가 변동률을 %로 다시 내지 않기 때문입니다. ’25 2분기는 "
                   "종합 수치 자체를 발표하지 않아 <b>막대를 그리지 않고 비웠습니다</b>. "
                   "’26 1분기 전망은 +20~25% → +55~60% → +85~90%로 세 번 상향된 값이라 "
                   "폭을 그대로 믿기보다 방향으로 보시는 편이 낫습니다. "
                   "지금 국면은 <b>계약가는 오르는데 현물 거래는 침체</b>인 괴리 상태입니다.")


# ── 파운드리 점유율 (Counterpoint, 순수 파운드리 기준) ─────────────────────
FND_Q = ["'25 1Q", "'25 2Q", "'25 3Q", "'25 4Q", "'26 1Q"]
FND = [
    ("TSMC",           [68, 71, 72, 72, 73]),
    ("삼성전자",       [9, 8, 7, 7, 7]),
    ("SMIC",           [6, 5, 5, 5, 5]),
    ("UMC",            [5, 5, 4, 4, 4]),
    ("글로벌파운드리", [4, 4, 4, 4, 3]),
    ("기타",           [8, 8, 8, 8, 7]),
]
FND_SRC = [
    ("Counterpoint 순수 파운드리 분기 점유율",
     "https://counterpointresearch.com/en/insights/global-semiconductor-foundry-market-share"),
    ("TrendForce ’26 1Q 대조 (TSMC 72% · 삼성 6.5%)",
     "https://www.trendforce.com/presscenter/news/20260612-13095.html"),
    ("인텔 ’26 2Q 실적 — 파운드리 외부 매출 $2.93억",
     "https://analysis.org/intel-q2-2026-16-1-billion-in-revenue-and-293-million-in-external-foundry-sales/"),
]
FND_NOTE = ("<b>인텔은 이 집계에 없습니다.</b> 순수 파운드리(남의 칩을 받아 만드는 회사) "
            "기준이라 자체 생산이 대부분인 인텔은 빠집니다. 인텔 ’26 2분기 파운드리 매출 "
            "$58억 중 <b>외부 고객 매출은 $2.93억</b>뿐이라, 그 기준으로 넣으면 표 맨 아래에 "
            "붙습니다. TSMC 점유율은 집계 기관마다 1~2%p 차이가 납니다(Counterpoint 73% vs "
            "TrendForce 72%). ’26 2분기 파운드리 순위는 9월경 나옵니다.")

# ── D램 계약가 분기 변동률 (TrendForce, 일반 D램 / HBM 제외) ───────────────
# (분기, 하한%, 상한%, 실적여부)
PRICE = [
    ("'25 1Q", -13, -8, False),
    ("'25 2Q", -5, 0, False),
    ("'25 3Q", 10, 15, False),
    ("'25 4Q", 45, 50, True),
    ("'26 1Q", 93, 98, True),
    ("'26 2Q", 58, 63, False),
    ("'26 3Q", 13, 18, False),
]
# 현물가 (TrendForce, 2026-08-14 세션 평균) / 계약가 (2026년 6월 하반월)
SPOT = [
    ("DDR5 16Gb (2Gx8) 4800/5600", "$52.73", "현물"),
    ("DDR5 16Gb eTT", "$23.65", "현물"),
    ("DDR4 16Gb (2Gx8) 3200", "$88.21", "현물"),
    ("DDR4 8Gb (1Gx8) 3200", "$42.72", "현물"),
    ("DDR3 4Gb 512Mx8", "$13.98", "현물"),
    ("DDR4 16Gb (2Gx8)", "$42.00", "계약"),
    ("DDR4 8Gb (1Gx8)", "$21.00", "계약"),
    ("DDR3 4Gb (256Mx16)", "$12.50", "계약"),
]
PRICE_SRC = [
    ("TrendForce ’26 1Q D램 실적 (+93~98% QoQ)",
     "https://www.trendforce.com/presscenter/news/20260601-13070.html"),
    ("TrendForce ’25 4Q 실적 (+45~50% QoQ)",
     "https://www.trendforce.com/presscenter/news/20260226-12937.html"),
    ("TrendForce ’26 3Q 전망 (+13~18% QoQ)",
     "https://www.trendforce.com/presscenter/news/20260703-13134.html"),
    ("TrendForce 현물·계약가",
     "https://www.trendforce.com/price/dram/dram_spot"),
]
PRICE_NOTE = ("일반 D램(HBM 제외) 계약가의 전분기 대비 변동률입니다. 값이 구간으로 "
              "발표돼서 막대는 구간 전체를 그립니다. <b>진한 막대가 확정 실적, "
              "연한 막대가 전망</b>입니다. ’25년 1~3분기는 TrendForce가 사후에 확정치를 "
              "%로 다시 밝히지 않아 발표 당시 전망치로 남겨뒀습니다. DDR5 계약가는 "
              "유료 자료라 공개된 건 현물가뿐입니다.")


def vid(s):
    return "".join(c if c.isalnum() else "-" for c in s)


# ══════════════════════════════════════════════════════════ 선 그래프
def line_chart(cid, quarters, series, ymax, ymin=0, w=1000, unit='%'):
    W, HG = w, 300
    L, R, T, B = 40, (168 if w > 700 else 132), 18, 34
    PW, PH = W - L - R, HG - T - B
    x = lambda i: L + PW * i / (len(quarters) - 1)
    y = lambda v: T + PH * (1 - (v - ymin) / (ymax - ymin))

    out = []
    gstep = 5 if (ymax - ymin) <= 20 else (10 if (ymax - ymin) <= 50 else 20)
    for g in range(ymin, ymax + 1, gstep):
        out.append(f'<line class="sc-grid" x1="{L}" y1="{y(g):.1f}" x2="{L+PW}" y2="{y(g):.1f}"/>')
        out.append(f'<text class="sc-ytick" x="{L-8}" y="{y(g)+4:.1f}">{g}</text>')
    for i, q in enumerate(quarters):
        out.append(f'<text class="sc-xtick" x="{x(i):.1f}" y="{T+PH+22}">{q}</text>')

    last = len(quarters) - 1
    # 오른쪽 라벨이 겹치지 않게, 마지막 값 순서대로 최소 간격을 벌린다
    ends = []
    for name, vals in series:
        j = max((k for k, v in enumerate(vals) if v is not None), default=None)
        if j is not None:
            ends.append([name, vals[j], y(vals[j]), j])
    ends.sort(key=lambda e: e[2])
    for k in range(1, len(ends)):
        if ends[k][2] - ends[k - 1][2] < 17:
            ends[k][2] = ends[k - 1][2] + 17

    for name, vals in series:
        c = f"var(--sc-{vid(name)})"
        runs, cur = [], []
        for i, v in enumerate(vals):
            if v is None:
                if len(cur) > 1:
                    runs.append(cur)
                cur = []
            else:
                cur.append(i)
        if len(cur) > 1:
            runs.append(cur)
        for run in runs:
            pts = " ".join(f"{x(i):.1f},{y(vals[i]):.1f}" for i in run)
            out.append(f'<polyline class="sc-line" style="stroke:{c}" points="{pts}"/>')
        for i, v in enumerate(vals):
            if v is None:
                continue
            out.append(f'<circle class="sc-dot" style="fill:{c}" cx="{x(i):.1f}" '
                       f'cy="{y(v):.1f}" r="4"><title>{H.escape(name)} · '
                       f'{quarters[i]} · {v}{unit}</title></circle>')

    for name, val, ly, j in ends:
        c = f"var(--sc-{vid(name)})"
        out.append(f'<line class="sc-stub" style="stroke:{c}" x1="{x(j)+5:.1f}" '
                   f'y1="{y(val):.1f}" x2="{L+PW+10}" y2="{ly:.1f}"/>')
        out.append(f'<text class="sc-elab" x="{L+PW+15}" y="{ly+4:.1f}">'
                   f'<tspan style="fill:{c}" class="sc-eval">{val}{unit}</tspan> '
                   f'{H.escape(name)}</text>')

    return (f'<svg class="sc-svg" viewBox="0 0 {W} {HG}" role="img" aria-label="{cid} 분기별 추이">'
            + "".join(out) + "</svg>")


def share_table(quarters, series):
    head = "".join(f"<th>{q}</th>" for q in quarters)
    rows = ""
    for name, vals in series:
        cells = "".join(f"<td>{v}%</td>" if v is not None
                        else '<td class="needchk">확인 필요</td>' for v in vals)
        rows += (f'<tr><th scope="row"><span class="sc-key" '
                 f'style="background:var(--sc-{vid(name)})"></span>{H.escape(name)}</th>{cells}</tr>')
    return f'<table class="sc-table"><thead><tr><th>업체</th>{head}</tr></thead><tbody>{rows}</tbody></table>'


def sources(items):
    return ('<div class="sc-src">출처 · ' + " · ".join(
        f'<a href="{u}" target="_blank" rel="noopener">{H.escape(t)}</a>' for t, u in items) + "</div>")


def dual_card(title, quarters, top, rest, note, src):
    """TSMC가 70%대, 나머지가 한 자릿수라 한 축에 그리면 아래쪽이 다 뭉친다.
    축을 억지로 끊는 대신 두 장으로 나눠 그린다 — 눈금이 서로 다르다는 걸
    제목에 분명히 적어둔다."""
    return f'''    <div class="card">
      <div class="card-title">{title}</div>
      <div class="card-note">{note}</div>
      <div class="sc-duo">
        <div class="sc-half"><div class="sc-sub">TSMC <span>눈금 60~80%</span></div>
          <div class="sc-wrap">{line_chart("fnd-top", quarters, top, 80, ymin=60, w=470)}</div></div>
        <div class="sc-half"><div class="sc-sub">나머지 업체 <span>눈금 0~10%</span></div>
          <div class="sc-wrap">{line_chart("fnd-rest", quarters, rest, 10, w=470)}</div></div>
      </div>
      <details class="sc-tbl"><summary>숫자로 보기</summary>
        <div class="sc-tblwrap">{share_table(quarters, top + rest)}</div>
      </details>
      {sources(src)}
    </div>
'''


def share_card(title, cid, quarters, series, ymax, note, src):
    return f'''    <div class="card">
      <div class="card-title">{title}</div>
      <div class="card-note">{note}</div>
      <div class="sc-wrap">{line_chart(cid, quarters, series, ymax)}</div>
      <details class="sc-tbl"><summary>숫자로 보기</summary>
        <div class="sc-tblwrap">{share_table(quarters, series)}</div>
      </details>
      {sources(src)}
    </div>
'''


# ══════════════════════════════════════════════════════════ 가격 막대
def price_chart(rows=None, label="D램"):
    """분기별 계약가 변동률 막대.

    lo/hi가 None인 분기는 "그 분기 수치가 발표되지 않았다"는 뜻이라 막대를
    그리지 않고 자리만 비워 둔다 — 앞뒤 분기를 이어 붙여 없는 값을 만들지 않는다.
    """
    rows = rows if rows is not None else PRICE
    got = [p for p in rows if p[1] is not None]
    W, HG = 1000, 300
    L, R, T, B = 46, 20, 22, 40
    PW, PH = W - L - R, HG - T - B
    lo = min(p[1] for p in got) - 8
    hi = max(p[2] for p in got) + 8
    y = lambda v: T + PH * (hi - v) / (hi - lo)
    step = PW / len(rows)
    out = []
    for g in range(-20, 101, 20):
        if lo <= g <= hi:
            cls = "sc-grid sc-zero" if g == 0 else "sc-grid"
            out.append(f'<line class="{cls}" x1="{L}" y1="{y(g):.1f}" x2="{L+PW}" y2="{y(g):.1f}"/>')
            out.append(f'<text class="sc-ytick" x="{L-8}" y="{y(g)+4:.1f}">{g:+d}%</text>')
    for i, (q, a, b, real) in enumerate(rows):
        cx = L + step * (i + 0.5)
        bw = step * 0.46
        out.append(f'<text class="sc-xtick" x="{cx:.1f}" y="{T+PH+22}">{q}</text>')
        if a is None:
            out.append(f'<text class="sc-nolab" x="{cx:.1f}" y="{y(0)-6:.1f}">미발표</text>')
            continue
        top, bot = y(b), y(a)
        # 구간이 아니라 단일 확정치면 "-15~-15%"가 아니라 "-15%"로 적는다
        rng = f"{a:+d}%" if a == b else f"{a:+d}~{b:+d}%"
        cls = "sc-bar" if real else "sc-bar sc-fc"
        col = "var(--up)" if b > 0 else "var(--down)"
        out.append(f'<rect class="{cls}" style="fill:{col}" x="{cx-bw:.1f}" y="{top:.1f}" '
                   f'width="{bw*2:.1f}" height="{max(2, bot-top):.1f}" rx="3">'
                   f'<title>{q} · {rng} · {"확정 실적" if real else "발표 당시 전망"}</title></rect>')
        lab = rng
        ly = (top - 7) if b > 0 else (bot + 15)
        out.append(f'<text class="sc-blab" x="{cx:.1f}" y="{ly:.1f}">{lab}</text>')
        if not real:
            out.append(f'<text class="sc-fclab" x="{cx:.1f}" y="{T+PH+34}">전망</text>')
    return ('<svg class="sc-svg" viewBox="0 0 %d %d" role="img" '
            'aria-label="%s 계약가 분기별 변동률">' % (W, HG, label)
            + "".join(out) + "</svg>")


def price_card(label="D램", pr=None, sp=None, note=None, src=None, asof=None):
    pr = pr if pr is not None else PRICE
    sp = sp if sp is not None else SPOT
    note = note if note is not None else PRICE_NOTE
    src = src if src is not None else PRICE_SRC
    rows = "".join(
        f'<tr><td>{H.escape(n)}</td><td class="sc-px">{v}</td>'
        f'<td><span class="sc-kind {"spot" if k == "현물" else "cont"}">{k}</span></td></tr>'
        for n, v, k in sp)
    prows = "".join(
        f'<tr><td>{q}</td>'
        + ((f'<td class="sc-px">{a:+d}%</td>' if a == b else f'<td class="sc-px">{a:+d}~{b:+d}%</td>')
           + f'<td>{"확정 실적" if r else "전망"}</td>'
           if a is not None else '<td class="needchk">확인 필요</td><td>미발표</td>')
        + "</tr>" for q, a, b, r in pr)
    return f'''    <div class="card">
      <div class="card-title">{label} 계약가 추이 (전분기 대비)</div>
      <div class="card-note">{note}</div>
      <div class="sc-wrap">{price_chart(pr, label)}</div>
      <details class="sc-tbl"><summary>숫자로 보기 · 현재 {label} 가격</summary>
        <div class="sc-tblwrap">
          <table class="sc-table sc-narrow"><thead><tr><th>분기</th><th>변동률</th><th>구분</th></tr></thead><tbody>{prows}</tbody></table>
          <table class="sc-table sc-narrow"><thead><tr><th>제품</th><th>가격</th><th>구분</th></tr></thead><tbody>{rows}</tbody></table>
        </div>
        <div class="sc-src">{asof or "현물가는 2026-08-14 세션 평균, 계약가는 2026년 6월 하반월 기준입니다."}</div>
      </details>
      {sources(src)}
    </div>
'''


def build():
    return f'''  <!-- ================= 반도체 ================= -->
  <section class="panel" id="semi">
    <div class="card sc-head">
      <div class="card-title">메모리 · 파운드리 시장 점유율과 가격</div>
      <div class="card-note">이 탭은 <b>자동 갱신되지 않는 수기 카드</b>입니다. 점유율과 메모리 가격은 야후 파이낸스에 없고, 이 숫자를 만드는 Counterpoint·TrendForce가 무료 API를 주지 않기 때문입니다. 모든 숫자는 실제로 확인한 출처가 있는 값만 넣었고, 못 구한 칸은 지어내지 않고 비워뒀습니다(선이 끊기고 표에는 "확인 필요"로 표시). 마지막 정리 <b>{UPDATED}</b> · 다음 갱신 대상 <b>{NEXT_DUE}</b></div>
    </div>
{share_card("D램 점유율 (매출 기준)", "dram", DRAM_Q, DRAM, 45, DRAM_NOTE, DRAM_SRC)}
{share_card("HBM 점유율 (매출 기준)", "hbm", HBM_Q, HBM, 75, HBM_NOTE, HBM_SRC)}
{share_card("낸드 점유율 (매출 기준)", "nand", NAND_Q, NAND, 40, NAND_NOTE, NAND_SRC)}
{price_card("낸드", NAND_PRICE, NAND_SPOT, NAND_PRICE_NOTE, NAND_PRICE_SRC,
            "현물가는 TrendForce가 2026-08-12에 발표한 512Gb TLC 웨이퍼 주간 시세입니다(주간 +4.97%).")}
{dual_card("파운드리 점유율 (순수 파운드리 기준)", FND_Q, FND[:1], FND[1:], FND_NOTE, FND_SRC)}
{price_card()}  </section>
'''


CSS_HEAD = """
  /* ── 반도체 탭: 점유율 추이 · D램 가격 (수기 카드) ─────────────────────── */
  /* 색은 기업을 따라간다 — D램 차트의 삼성과 파운드리 차트의 삼성이 같은 파랑 */
"""


def css():
    light = "".join(f"    --sc-{vid(n)}: {c[0]};\n" for n, c in COLORS.items())
    dark = "".join(f"      --sc-{vid(n)}: {c[1]};\n" for n, c in COLORS.items())
    return CSS_HEAD + f"""  :root {{
{light}  }}
  .sc-head .card-note {{ padding-bottom: 12px; }}
  .sc-wrap {{ overflow-x: auto; padding: 2px 16px 4px; }}
  .sc-svg {{ width: 100%; min-width: 820px; height: auto; display: block;
    font-family: system-ui, -apple-system, "Segoe UI", sans-serif; }}
  .sc-grid {{ stroke: var(--grid); stroke-width: 1; }}
  .sc-zero {{ stroke: var(--text-muted); opacity: .6; }}
  .sc-ytick, .sc-xtick {{ fill: var(--text-muted); font-size: 11px;
    font-variant-numeric: tabular-nums; }}
  .sc-ytick {{ text-anchor: end; }}
  .sc-xtick {{ text-anchor: middle; }}
  .sc-fclab {{ fill: var(--text-muted); font-size: 9px; text-anchor: middle; }}
  .sc-line {{ fill: none; stroke-width: 2.4; stroke-linejoin: round; stroke-linecap: round; }}
  .sc-dot {{ stroke: var(--surface-1); stroke-width: 1.5; cursor: help; }}
  .sc-stub {{ stroke-width: 1; opacity: .45; }}
  .sc-elab {{ fill: var(--text-secondary); font-size: 11.5px; font-weight: 600; }}
  .sc-eval {{ font-weight: 800; font-variant-numeric: tabular-nums; }}
  .sc-bar {{ cursor: help; }}
  .sc-fc {{ opacity: .42; }}
  .sc-blab {{ fill: var(--text-secondary); font-size: 10.5px; font-weight: 700;
    text-anchor: middle; font-variant-numeric: tabular-nums; }}
  .sc-duo {{ display: flex; flex-wrap: wrap; gap: 4px; }}
  .sc-half {{ flex: 1 1 380px; min-width: 0; }}
  .sc-sub {{ font-size: 11.5px; font-weight: 700; color: var(--text-secondary);
    padding: 4px 16px 0; }}
  .sc-sub span {{ font-weight: 500; color: var(--text-muted); font-size: 10.5px; }}
  .sc-half .sc-svg {{ min-width: 380px; }}
  .sc-tbl {{ border-top: 1px solid var(--grid); margin-top: 8px; }}
  .sc-tbl > summary {{ cursor: pointer; padding: 9px 16px; font-size: 12px;
    font-weight: 700; color: var(--text-secondary); }}
  .sc-tbl > summary:hover {{ color: var(--text-primary); }}
  .sc-tblwrap {{ overflow-x: auto; padding: 0 16px 8px; display: flex;
    gap: 18px; flex-wrap: wrap; }}
  .sc-table {{ border-collapse: collapse; font-size: 11.5px;
    font-variant-numeric: tabular-nums; }}
  .sc-narrow {{ flex: 1 1 260px; }}
  .sc-table th, .sc-table td {{ padding: 4px 8px; text-align: right;
    border-bottom: 1px solid var(--grid); white-space: nowrap; }}
  .sc-table thead th {{ color: var(--text-muted); font-size: 10.5px; font-weight: 600; }}
  .sc-table tbody th {{ text-align: left; font-weight: 700; }}
  .sc-table td:first-child {{ text-align: left; }}
  .sc-key {{ display: inline-block; width: 9px; height: 9px; border-radius: 2px;
    margin-right: 6px; }}
  .sc-px {{ font-weight: 800; }}
  .sc-kind {{ font-size: 9.5px; font-weight: 700; border-radius: 5px; padding: 1px 5px;
    color: var(--text-muted); border: 1px solid var(--border); }}
  .sc-kind.spot {{ color: var(--accent); }}
  .sc-src {{ font-size: 10.5px; color: var(--text-muted); padding: 2px 16px 12px;
    line-height: 1.7; }}
  .sc-src a {{ color: var(--text-secondary); }}
  @media (max-width: 700px) {{ .sc-wrap {{ padding: 2px 8px 4px; }} }}
  @media (prefers-color-scheme: dark) {{
    :root {{
{dark}    }}
  }}
"""


if __name__ == "__main__":
    open("/tmp/semi_section.html", "w", encoding="utf-8").write(build())
    open("/tmp/semi.css", "w", encoding="utf-8").write(css())
    print("section", len(build()), "· css", len(css()))
