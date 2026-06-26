"""
손절실패 에이전트 데모 — Streamlit

실행:
    cd 손절실패
    streamlit run app_streamlit.py
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from data.virtual_trades import TRANSACTIONS
from agent import analyze_real
from data_loader import load_daily_ohlcv

st.set_page_config(page_title="손절실패 에이전트", layout="wide")

st.title("📉 손절실패 에이전트")
st.caption(
    "끝난 거래 하나를 받아 '손절을 못 하고 버틴 정도'를 0~1 점수로 매기는 엔진입니다. "
    "가상 투자자 20거래(실제 KOSPI 분봉 가격 기반)로 시연합니다."
)


@st.cache_data
def get_results():
    return analyze_real(TRANSACTIONS)


results = get_results()

# ── 전체 거래 요약 표 ──────────────────────────────────────────────────────
df = pd.DataFrame(
    [
        {
            "종목": r["ticker"],
            "판정": r["judgment_type"],
            "점수": r["score"],
            "실현수익률(%)": r["signals"]["realized_return_pct"],
            "확대": r["signals"]["expansion_score"],
            "지연": r["signals"]["delay_score"],
            "물타기": r["signals"]["avg_down_score"],
            "초과손실": r["signals"]["excess_loss_score"],
            "지연일수": r["signals"]["delay_days"],
            "lucky_hold": "⚠️" if r["flags"]["lucky_hold"] else "",
        }
        for r in results
    ]
).sort_values("점수", ascending=False).reset_index(drop=True)

st.subheader(f"전체 거래 {len(df)}건")

col_a, col_b, col_c, col_d = st.columns(4)
col_a.metric("평균 점수", f"{df['점수'].mean():.3f}")
col_b.metric("지연형", int((df["판정"] == "지연형").sum()))
col_c.metric("물타기형", int((df["판정"] == "물타기형").sum()))
col_d.metric("lucky_hold", int((df["lucky_hold"] == "⚠️").sum()))

st.dataframe(
    df,
    width="stretch",
    height=420,
    column_config={
        "점수": st.column_config.ProgressColumn("점수", min_value=0, max_value=1, format="%.3f"),
    },
)

st.divider()

# ── 거래 상세 보기 ─────────────────────────────────────────────────────────
st.subheader("거래 상세 보기")
ticker_options = df["종목"].tolist()
selected_ticker = st.selectbox("종목 선택", ticker_options)

r = next(x for x in results if x["ticker"] == selected_ticker)
sig = r["signals"]

col1, col2 = st.columns([2, 1])

with col1:
    st.markdown(f"### {r['ticker']}  ·  **{r['judgment_type']}**")
    st.metric("최종 점수", f"{r['score']:.3f}")
    st.write(f"**진단:** {r['narrative']}")
    if r["recommendation"]:
        st.info(f"💡 {r['recommendation']}")
    if r["flags"]["lucky_hold"]:
        shadow = r.get("shadow_score")
        shadow_txt = f" (이 행동을 손실로 채점하면 {shadow:.2f}점)" if shadow is not None else ""
        st.warning(f"⚠️ **lucky_hold** — 수익으로 끝났지만 도중 -20% 이상 빠졌습니다. 운이 좋았을 뿐 손절 실패였습니다.{shadow_txt}")

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("실현수익률", f"{sig['realized_return_pct']:.1f}%")
    m2.metric("MAE", f"{sig['MAE_pct']:.1f}%")
    m3.metric("손절선", f"{sig['stop_pct']:.1f}% ({sig['stop_method']})")
    m4.metric("지연일수", f"{sig['delay_days']}일")

with col2:
    sig_df = pd.DataFrame(
        {
            "신호": ["확대(0.35)", "지연(0.30)", "물타기(0.20)", "초과손실(0.15)"],
            "점수": [
                sig["expansion_score"],
                sig["delay_score"],
                sig["avg_down_score"],
                sig["excess_loss_score"],
            ],
        }
    )
    fig_bar = go.Figure(
        go.Bar(x=sig_df["점수"], y=sig_df["신호"], orientation="h", marker_color="indianred")
    )
    fig_bar.update_layout(
        title="신호별 점수 (가중치)",
        xaxis_range=[0, 1],
        height=280,
        margin=dict(l=0, r=10, t=40, b=0),
    )
    st.plotly_chart(fig_bar, width="stretch")

# ── 가격 차트 (진입/이탈/매도 마커) ────────────────────────────────────────
st.markdown("**가격 차트**")
daily = load_daily_ohlcv(r["ticker"])
price_df = pd.DataFrame([{"date": d.date, "close": d.close, "low": d.low} for d in daily])
entry_date = pd.Timestamp(r["entry_ts"]).date()
exit_date = pd.Timestamp(r["exit_ts"]).date()
price_df = price_df[(price_df["date"] >= entry_date) & (price_df["date"] <= exit_date)]

fig = go.Figure()
fig.add_trace(go.Scatter(x=price_df["date"], y=price_df["close"], mode="lines", name="종가"))
fig.add_hline(
    y=price_df["close"].iloc[0] * (1 + sig["stop_pct"] / 100),
    line_dash="dash",
    line_color="orange",
    annotation_text=f"손절선 {sig['stop_pct']:.1f}%",
)
fig.add_trace(
    go.Scatter(
        x=[entry_date], y=[price_df["close"].iloc[0]],
        mode="markers+text", marker=dict(color="blue", size=12),
        text=["매수"], textposition="top center", name="매수",
    )
)
fig.add_trace(
    go.Scatter(
        x=[exit_date], y=[price_df["close"].iloc[-1]],
        mode="markers+text", marker=dict(color="green", size=12),
        text=["매도"], textposition="top center", name="매도",
    )
)
if sig["breach_date"]:
    breach_date = pd.Timestamp(sig["breach_date"]).date()
    breach_row = price_df[price_df["date"] == breach_date]
    if not breach_row.empty:
        fig.add_trace(
            go.Scatter(
                x=[breach_date], y=[breach_row["low"].iloc[0]],
                mode="markers+text", marker=dict(color="red", size=12, symbol="x"),
                text=["이탈"], textposition="bottom center", name="이탈일",
            )
        )
fig.update_layout(height=400, margin=dict(l=0, r=10, t=20, b=0))
st.plotly_chart(fig, width="stretch")
