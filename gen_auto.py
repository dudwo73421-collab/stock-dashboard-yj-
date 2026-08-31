# -*- coding: utf-8 -*-
"""자동차 탭 — 글로벌 완성차 그룹 판매량·점유율, 전기차 점유율.

반도체 탭과 같은 수기 카드다. 자동 갱신되지 않는다.

이 자료에는 반도체보다 훨씬 큰 함정이 하나 있다. 집계 기준이 네 가지로 섞여 있고
서로 4~8%씩 차이가 난다:
    회사 발표 판매량 / 도매 출하(딜러 인도) / 등록대수 / 소매 판매
그래서 카드마다 기준을 하나로 통일하고, 화면에도 그 기준을 명시한다.
출처가 서로 다른 숫자를 한 그래프에 섞지 않는다.

못 구한 값은 None으로 둔다 — 선이 끊기고 표에는 "확인 필요"로 나온다.
"""
import html as H
import importlib.util

_spec = importlib.util.spec_from_file_location("gs", "/home/claude/gen_semi.py")
gs = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(gs)

UPDATED = "2026-08-15"
NEXT_DUE = "2026년 3분기 자료 (10~11월경)"

COLORS = {
    "토요타":     ("#e34948", "#e66767"),
    "폭스바겐":   ("#2a78d6", "#3987e5"),
    "현대차그룹": ("#1baf7a", "#199e70"),
    "BYD":        ("#eb6834", "#d95926"),
    "지리":       ("#4a3aa7", "#9085e9"),
    "테슬라":     ("#e87ba4", "#d55181"),
    "SAIC":       ("#eda100", "#c98500"),
    "닛산":       ("#008300", "#00a12f"),
    "스텔란티스": ("#8a6d3b", "#a98a55"),
    "GM":         ("#0e7c9e", "#3aa5c4"),
    "포드":       ("#7a4fd1", "#a98ae4"),
    "혼다":       ("#b8005c", "#d4477f"),
    "체리":       ("#5a6b00", "#8ba320"),
    "창안":       ("#556070", "#8794a6"),
    "기타차":     ("#898781", "#898781"),
}

# ── 2025년 글로벌 판매량 (회사 발표 기준, 백만 대) ─────────────────────────
# GM·혼다는 출처끼리 값이 크게 갈려서 넣지 않았다(아래 주석 참고).
SALES25 = [
    ("토요타", 11.32, "+4.6%"),
    ("폭스바겐", 8.98, "-0.5%"),
    ("현대차그룹", 7.24, "+0.2%"),
    ("스텔란티스", 5.48, "+1.0%"),
    ("BYD", 4.60, "+7.1%"),
    ("SAIC", 4.51, "+12.3%"),
    ("포드", 4.40, "-2.0%"),
    ("지리", 4.12, "+26.0%"),
    ("닛산", 3.20, "-4.4%"),
    ("창안", 2.91, "+8.5%"),
    ("체리", 2.63, "+8.0%"),
    ("테슬라", 1.64, "-8.6%"),
]
SALES_NOTE = (
    "각 회사가 직접 발표한 2025년 연간 판매량입니다(백만 대). "
    "<b>GM과 혼다는 뺐습니다</b> — GM은 출처에 따라 618만 대와 455만 대로 26%나 갈리고"
    "(중국 합작사를 넣느냐 마느냐 차이로 보입니다), 혼다는 352만 vs 346만으로 엇갈려서 "
    "어느 쪽을 쓸지 확정할 수 없었습니다. 지어내지 않고 비워두는 쪽을 택했습니다. "
    "폭스바겐·스텔란티스·포드·테슬라는 <b>도매 출하(딜러 인도)</b> 기준이고 나머지는 "
    "회사 발표 판매량이라, 1~2위 사이 소수점 차이는 큰 의미를 두지 마세요.")
SALES_SRC = [
    ("토요타 2025 (11,322,575대)", "https://www.motor1.com/news/784354/toyota-best-selling-car-brand-2025/"),
    ("폭스바겐그룹 공식 (898만 대)", "https://www.volkswagen-group.com/en/press-releases/volkswagen-group-deliveries-remain-stable-in-2025-20095"),
    ("현대차 소매 + 기아 합산", "https://www.hyundai.com/worldwide/en/newsroom/detail/0000001111"),
    ("BYD 2025 (460만 대)", "https://carnewschina.com/2026/01/01/byd-sold-4-6-million-cars-in-2025-but-things-dont-look-very-good-for-2026/"),
    ("2025 글로벌 순위 종합", "https://carnewschina.com/2026/02/26/three-chinese-automakers-enter-global-top-10-as-2025-sales-rankings-finalized/"),
]

# ── 판매량 추이 (백만 대, 회사 발표 기준) ──────────────────────────────────
TREND_X = ["2023", "2024", "2025", "'26 상반기"]
# 선그래프에는 연간 세 시점만 쓴다 — 반년치를 같은 축에 두면 모두 반토막 난 것처럼
# 보여서 오히려 오해를 부른다. 상반기 값은 아래 표에 그대로 남긴다.
TREND_YEARS = TREND_X[:3]
TREND = [
    ("토요타",     [11.23, 10.82, 11.32, 5.39]),
    ("폭스바겐",   [9.24, 9.03, 8.98, 4.13]),
    ("현대차그룹", [7.32, 7.23, 7.24, 3.58]),
    ("BYD",        [3.02, 4.27, 4.60, 1.81]),
    ("SAIC",       [None, 4.01, 4.51, 2.05]),
    ("지리",       [None, 3.27, 4.12, 1.93]),
    ("닛산",       [3.23, 3.35, 3.20, 1.51]),
    ("테슬라",     [None, 1.79, 1.64, 0.84]),
]
TREND_NOTE = (
    "그래프는 <b>연간 판매량</b>(백만 대)만 그렸습니다. 2026년 상반기는 반년치라 같은 "
    "축에 두면 전부 반토막 난 것처럼 보여서, 아래 <b>숫자로 보기</b>에만 넣었습니다. "
    "상반기 흐름을 보면 토요타·폭스바겐·현대차그룹은 대체로 제자리인데 BYD가 처음 "
    "꺾였고(-15.7%), SAIC·지리는 계속 올라오는 중입니다. 2023년 값이 없는 회사는 "
    "그해 자료를 확인하지 못해 비워뒀습니다.")

# ── 글로벌 점유율 (CPCA, 2026년 상반기) ────────────────────────────────────
SHARE26 = [
    ("토요타", 11.0), ("폭스바겐", 8.1), ("현대차그룹", 7.6), ("스텔란티스", 6.0),
    ("닛산", 5.4), ("BYD", 4.8), ("지리", 4.6), ("GM", 4.5),
    ("포드", 4.1), ("체리", 4.1),
]
SHARE_NOTE = (
    "중국승용차협회(CPCA) 집계, <b>2026년 상반기</b> 기준입니다. 여기 숫자는 위 판매량 "
    "카드와 <b>집계 기준이 달라서</b> 직접 나눠 계산한 값과 맞지 않습니다 — 그래서 "
    "한 출처 안에서만 비교하시라고 카드를 따로 뒀습니다. 중국 3사(BYD·지리·체리)가 "
    "동시에 10위 안에 든 게 이번이 처음입니다. 닛산은 르노-닛산-미쓰비시 연합 기준이라 "
    "닛산 단독 판매량보다 큽니다.")
SHARE_SRC = [
    ("CPCA 2026 상반기 글로벌 점유율", "https://carnewschina.com/2026/08/05/three-chinese-companies-entered-top-10-global-automakers-by-market-share-in-h1-2026/"),
    ("TechNode 대조 보도", "https://technode.com/2026/08/06/three-chinese-automakers-byd-geely-and-chery-break-into-the-global-top-10/"),
    ("focus2move 2025 (토요타 12.2% · VW 9.6% · 현대차 8.0%)", "https://www.focus2move.com/world-car-group-ranking/"),
]

# ── 순수 전기차(BEV) 점유율 추이 (Counterpoint, 분기) ──────────────────────
BEV_X = ["'24 2Q", "'24 3Q", "'24 4Q", "'25 1Q", "'25 2Q", "'25 3Q", "'25 4Q", "'26 1Q"]
BEV = [
    ("BYD",    [17, 16, 16, 15, 18, 16, 15, 11]),
    ("테슬라", [17, 17, 14, 12, 12, 13, 10, 13]),
    ("지리",   [8, 9, 9, 11, 11, 10, 9, 10]),
    ("기타차", [58, 59, 61, 61, 60, 61, 66, 66]),
]
BEV_NOTE = (
    "<b>순수 전기차(BEV)만</b> 센 점유율입니다 — 플러그인 하이브리드(PHEV)는 뺐습니다. "
    "이 구분이 중요한 게, PHEV까지 넣으면 BYD가 압도적 1위인데 BEV만 보면 테슬라와 "
    "엎치락뒤치락합니다. ’26년 1분기에 테슬라 13% · BYD 11%로 테슬라가 다시 앞섰고, "
    "회색 <b>기타</b>가 66%까지 커진 게 이 그래프의 진짜 이야기입니다 — 상위 3사 밖의 "
    "업체들이 시장을 나눠 갖고 있다는 뜻입니다. Counterpoint는 이 시리즈에서 테슬라·"
    "BYD·지리 셋만 공개해서 나머지는 묶여 있고, ’26년 2분기는 아직 발표 전입니다.")
BEV_SRC = [
    ("Counterpoint 분기 BEV 점유율", "https://counterpointresearch.com/en/insights/global-electric-vehicle-market-share-quarterly"),
    ("CleanTechnica 2025 연간 대조 (BYD 16.6% · 테슬라 12% · 지리 10.4%)", "https://cleantechnica.com/2026/02/03/global-ev-sales-leaders-top-selling-brands-and-oems/"),
]

# ── 전기차 전체(BEV+PHEV) 시장 — SNE리서치 ────────────────────────────────
NEV_ROWS = [
    ("전 세계 합계", "1,763만 대", "2,147만 대", "991만 대 (상반기)"),
    ("BYD", "414만 대", "412만 대 · 19.2%", "150만 대 · 15.1%"),
    ("지리", "확인 필요", "223만 대 · 10.4%", "98만 대"),
    ("테슬라", "확인 필요", "164만 대 · 7.6%", "84만 대 · 8.5%"),
    ("폭스바겐그룹", "확인 필요", "확인 필요", "67만 대"),
    ("SAIC", "확인 필요", "확인 필요", "59만 대"),
    ("현대차그룹", "약 55만 대", "61만 대 · 2.9%", "37만 대 · 3.7%"),
]
NEV_REGION = [
    ("중국", "1,381만 대 · 64.3%", "531만 대 · 53.6% (-9.5%)"),
    ("유럽", "426만 대 · 19.8%", "253만 대 · 25.5% (+29.0%)"),
    ("북미", "174만 대 (-5.0%)", "68만 대 · 6.9% (-20.5%)"),
    ("아시아(중국 제외)", "123만 대 (+58.5%)", "93만 대 · 9.4% (+75.8%)"),
]
NEV_NOTE = (
    "<b>PHEV까지 포함한</b> 전기차 전체 시장입니다. 위 BEV 카드와 순위가 다른 게 "
    "정상입니다. 눈여겨볼 건 지역 흐름이에요 — ’26년 상반기에 중국이 -9.5%, 북미가 "
    "-20.5%로 꺾이는 동안 <b>유럽만 +29%</b>로 늘었고, 그 결과 유럽 비중이 19.8%에서 "
    "25.5%까지 올라왔습니다. 중국을 빼고 보면 순위가 완전히 뒤집혀서 폭스바겐 13.8% · "
    "테슬라 13.0% · BYD 10.8% · 현대차그룹 8.0% 순입니다. "
    "SNE는 상위 몇 곳만 공개해서 나머지는 확인 필요로 뒀습니다.")
NEV_SRC = [
    ("SNE리서치 2025 연간", "https://www.sneresearch.com/en/insight/release_view/589/page/0"),
    ("SNE리서치 2026 상반기", "https://www.sneresearch.com/en/insight/release_view/708/page/1"),
    ("SNE리서치 2026 상반기 (중국 제외)", "https://www.sneresearch.com/en/insight/release_view/711/page/1"),
    ("Benchmark 2025 (2,070만 대) — SNE와 3.7% 차이", "https://source.benchmarkminerals.com/article/global-ev-sales-reach-20-7-million-units-in-2025-growing-by-20"),
]


# ══════════════════════════════════════════════════════════ 가로 막대
def hbar(rows, unit, maxv=None, w=1000):
    """(이름, 값, 꼬리표) 목록을 가로 막대로. 순위 비교에는 이게 제일 빨리 읽힌다."""
    rowh, gap = 30, 6
    L, R, T = 132, 96, 6
    HG = T + len(rows) * (rowh + gap)
    PW = w - L - R
    mx = maxv or max(r[1] for r in rows)
    out = []
    for i, r in enumerate(rows):
        name, val = r[0], r[1]
        tail = r[2] if len(r) > 2 else ""
        y = T + i * (rowh + gap)
        bw = PW * val / mx
        c = f"var(--sc-{gs.vid(name)})"
        out.append(f'<text class="ab-name" x="{L-10}" y="{y+rowh*0.66:.1f}">{H.escape(name)}</text>')
        out.append(f'<rect class="ab-bar" style="fill:{c}" x="{L}" y="{y+4}" '
                   f'width="{bw:.1f}" height="{rowh-8}" rx="4"><title>{H.escape(name)} · '
                   f'{val}{unit}{" · " + tail if tail else ""}</title></rect>')
        out.append(f'<text class="ab-val" x="{L+bw+8:.1f}" y="{y+rowh*0.66:.1f}">{val}{unit}'
                   + (f'<tspan class="ab-tail"> {H.escape(tail)}</tspan>' if tail else "") + '</text>')
    return (f'<svg class="sc-svg ab-svg" viewBox="0 0 {w} {HG}" role="img" '
            f'aria-label="가로 막대 순위">' + "".join(out) + "</svg>")


def simple_table(head, rows):
    th = "".join(f"<th>{h}</th>" for h in head)
    tr = ""
    for r in rows:
        cells = "".join(
            f'<td class="needchk">{c}</td>' if c == "확인 필요" else f"<td>{H.escape(c)}</td>"
            for c in r[1:])
        tr += f'<tr><th scope="row">{H.escape(r[0])}</th>{cells}</tr>'
    return f'<table class="sc-table"><thead><tr>{th}</tr></thead><tbody>{tr}</tbody></table>'


def card(title, note, body, src, table=None):
    tbl = (f'<details class="sc-tbl"><summary>숫자로 보기</summary>'
           f'<div class="sc-tblwrap">{table}</div></details>') if table else ""
    return f'''    <div class="card">
      <div class="card-title">{title}</div>
      <div class="card-note">{note}</div>
      {body}
      {tbl}
      {gs.sources(src)}
    </div>
'''


def build():
    sales_tbl = simple_table(
        ["그룹"] + TREND_X,
        [(n, *[("확인 필요" if v is None else f"{v:.2f}") for v in vals]) for n, vals in TREND])
    nev_tbl = (simple_table(["업체", "2024", "2025", "2026 상반기"], NEV_ROWS)
               + simple_table(["지역", "2025", "2026 상반기"], NEV_REGION))
    return f'''  <!-- ================= 자동차 ================= -->
  <section class="panel" id="auto">
    <div class="card sc-head">
      <div class="card-title">글로벌 완성차 판매량 · 점유율 · 전기차</div>
      <div class="card-note">반도체 탭과 마찬가지로 <b>자동 갱신되지 않는 수기 카드</b>입니다. 자동차 판매 자료는 특히 <b>집계 기준이 네 가지로 섞여 있어</b>(회사 발표 판매량 / 도매 출하 / 등록대수 / 소매 판매) 출처끼리 4~8%씩 차이가 납니다. 그래서 카드마다 기준을 하나로 통일했고, 서로 다른 출처의 숫자를 한 그래프에 섞지 않았습니다. 확인하지 못한 값은 지어내지 않고 비워뒀습니다. 마지막 정리 <b>{UPDATED}</b> · 다음 갱신 대상 <b>{NEXT_DUE}</b></div>
    </div>
{card("2025년 글로벌 판매량 순위", SALES_NOTE, f'<div class="sc-wrap">{hbar(SALES25, "M")}</div>', SALES_SRC)}
{card("판매량 추이 (2023 ~ 2026 상반기)", TREND_NOTE, f'<div class="sc-wrap">{gs.line_chart("auto", TREND_YEARS, [(n, v[:3]) for n, v in TREND], 12, unit="M")}</div>', SALES_SRC, sales_tbl)}
{card("글로벌 점유율 (2026 상반기)", SHARE_NOTE, f'<div class="sc-wrap">{hbar(SHARE26, "%")}</div>', SHARE_SRC)}
{card("순수 전기차(BEV) 점유율 추이", BEV_NOTE, f'<div class="sc-wrap">{gs.line_chart("bev", BEV_X, BEV, 70)}</div>', BEV_SRC, gs.share_table(BEV_X, BEV))}
{card("전기차 전체(BEV+PHEV) 시장", NEV_NOTE, "", NEV_SRC, nev_tbl)}  </section>
'''


def css():
    light = "".join(f"    --sc-{gs.vid(n)}: {c[0]};\n" for n, c in COLORS.items())
    dark = "".join(f'  html[data-theme="dark"] {{ --sc-{gs.vid(n)}: {c[1]}; }}\n'
                   for n, c in COLORS.items())
    return f"""
  /* ── 자동차 탭 (수기 카드) ─────────────────────────────────────────── */
  :root {{
{light}  }}
{dark}  .ab-svg {{ min-width: 640px; }}
  .ab-name {{ fill: var(--text-primary); font-size: 12.5px; font-weight: 700;
    text-anchor: end; }}
  .ab-val {{ fill: var(--text-secondary); font-size: 12px; font-weight: 800;
    font-variant-numeric: tabular-nums; }}
  .ab-tail {{ fill: var(--text-muted); font-weight: 600; font-size: 11px; }}
  .ab-bar {{ cursor: help; }}
"""


if __name__ == "__main__":
    open("/tmp/auto_section.html", "w", encoding="utf-8").write(build())
    open("/tmp/auto.css", "w", encoding="utf-8").write(css())
    print("section", len(build()), "· css", len(css()))
