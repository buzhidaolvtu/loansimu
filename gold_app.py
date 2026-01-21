import streamlit as st
import akshare as ak
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime

# 页面配置
st.set_page_config(page_title="黄金全周期深度分析", layout="wide")

st.title("🏆 黄金实时行情与多周期复利深度看板")


# --- 1. 顶部：实时行情 ---
def get_realtime_gold():
    try:
        df = ak.spot_quotations_sge(symbol="Au99.99")
        return df.iloc[-1] if not df.empty else None
    except:
        return None


realtime = get_realtime_gold()
if realtime is not None:
    c1, c2, c3 = st.columns([1, 1, 2])
    c1.metric("最新现价 (元/克)", f"￥{float(realtime['现价']):.2f}")
    c2.write(f"⏱ 行情时间: {realtime['时间']}\n\n🔄 更新时间: {realtime['更新时间']}")
    c3.success(f"✅ 接口正常 | 品种: {realtime['品种']}")
st.divider()


# --- 2. 数据处理：计算多周期 ROI 与 年化收益 ---
@st.cache_data(ttl=3600)
def get_gold_analysis_data():
    df = ak.spot_hist_sge(symbol="Au99.99")
    df['date'] = pd.to_datetime(df['date'])
    df_m = df.resample('M', on='date')['close'].mean().reset_index()
    df_m.columns = ['month', 'price']

    # 定义周期（月）
    periods = {'1y': 12, '2y': 24, '3y': 36, '5y': 60, '10y': 120}

    for label, months in periods.items():
        years = months / 12
        # 1. 计算总 ROI
        df_m[f'roi_{label}'] = (df_m['price'] - df_m['price'].shift(months)) / df_m['price'].shift(months)
        # 2. 计算年化复利收益率 (CAGR)
        # 公式: (1 + total_roi)^(1/years) - 1
        df_m[f'annual_{label}'] = ((1 + df_m[f'roi_{label}']) ** (1 / years) - 1) * 100
        # 还原总 ROI 为百分比供图表 2/3 使用
        df_m[f'roi_{label}'] = df_m[f'roi_{label}'] * 100

    df_m['color_1y'] = df_m['roi_1y'].apply(lambda x: 'red' if x >= 0 else 'green')
    return df_m


try:
    df = get_gold_analysis_data()

    # --- 图表 1: 价格与 1年 ROI 点标注 ---
    st.header("2. 价格走势与年度 ROI (红正绿负)")
    fig1 = go.Figure()
    fig1.add_trace(go.Scatter(x=df['month'], y=df['price'], mode='lines', line=dict(color='lightgrey'), name='月均价'))
    df_p = df[df['roi_1y'].notna()]
    fig1.add_trace(go.Scatter(
        x=df_p['month'], y=df_p['price'], mode='markers+text',
        marker=dict(color=df_p['color_1y'], size=6),
        text=df_p['roi_1y'].apply(lambda x: f"{x:.0f}%"),
        textposition="top center", textfont=dict(size=8, color=df_p['color_1y']),
        name='1年ROI'
    ))
    st.plotly_chart(fig1, use_container_width=True)

    # --- 图表 2: 多周期总 ROI 对比 ---
    st.header("3. 多周期总回报对比 (1年 vs 5年 vs 10年)")
    fig2 = go.Figure()
    fig2.add_trace(go.Scatter(x=df['month'], y=df['roi_1y'], name='1年总回报', line=dict(color='orange', dash='dot')))
    fig2.add_trace(go.Scatter(x=df['month'], y=df['roi_5y'], name='5年总回报', line=dict(color='blue')))
    fig2.add_trace(go.Scatter(x=df['month'], y=df['roi_10y'], name='10年总回报', line=dict(color='purple', width=3)))
    fig2.add_hline(y=0, line_dash="dash", line_color="black")
    st.plotly_chart(fig2, use_container_width=True)

    # --- 图表 3: 年化复利曲线 (核心新增) ---
    st.header("4. 滚动年化复利收益率 (1y, 2y, 3y, 5y)")
    st.caption("注：该图表展示了在任意时间点向前回溯，不同持有周期所获得的“平均年收益”，用于对比投资效率。")
    fig3 = go.Figure()
    colors = {'annual_1y': '#FFA07A', 'annual_2y': '#20B2AA', 'annual_3y': '#778899', 'annual_5y': '#FF4500'}
    names = {'annual_1y': '1年年化', 'annual_2y': '2年年化', 'annual_3y': '3年年化', 'annual_5y': '5年年化'}

    for col in ['annual_1y', 'annual_2y', 'annual_3y', 'annual_5y']:
        fig3.add_trace(go.Scatter(x=df['month'], y=df[col], name=names[col], line=dict(color=colors[col])))

    fig3.add_hline(y=0, line_dash="dash", line_color="black")
    fig3.update_layout(yaxis_title="年化收益率 (%)", hovermode="x unified", template="plotly_white")
    st.plotly_chart(fig3, use_container_width=True)

    # 底部概览
    latest = df.iloc[-1]
    st.markdown("### 🔍 最新年化收益表现")
    cols = st.columns(4)
    cols[0].metric("1年年化", f"{latest['annual_1y']:.2f}%")
    cols[1].metric("2年年化", f"{latest['annual_2y']:.2f}%")
    cols[2].metric("3年年化", f"{latest['annual_3y']:.2f}%")
    cols[3].metric("5年年化", f"{latest['annual_5y']:.2f}%")

except Exception as e:
    st.error(f"分析失败: {e}")