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

    # --- 5. 底部新增：2026年度定投跟踪 ---
    st.divider()
    st.header("📅 2026年度黄金定投跟踪 📿")

    # 构造 2026 年 12 个月的日期序列
    months_2026 = pd.date_range(start='2026-01-01', periods=12, freq='MS')
    plan_data = []

    current_date = datetime.now()
    completed_months = 0
    accumulated_sum = 0.0  # 用于累加已发生的金额

    for m in months_2026:
        month_str = m.strftime('%Y-%m')
        # 在 df 中查找该月的历史均价
        match = df[df['month'].dt.strftime('%Y-%m') == month_str]

        if not match.empty:
            avg_price_val = float(match.iloc[0]['price'])
            avg_price_display = f"￥{avg_price_val:.2f}"
            completed_months += 1
            accumulated_sum += avg_price_val  # 核心逻辑：直接累加表格中存在的金额
        elif m > current_date:
            avg_price_display = "待发生"
        else:
            avg_price_display = "计算中..."

        plan_data.append({"月份": month_str, "实物金价 📿": avg_price_display})

    # 转换为 DataFrame 并转置为两行显示
    df_plan = pd.DataFrame(plan_data).set_index("月份").T

    # 显示定投进度和自动累积的金额
    progress_val = completed_months / 12

    stat_col1, stat_col2 = st.columns(2)
    with stat_col1:
        st.write(f"**2026年定投进度：{completed_months} / 12 个月 🥇**")
        st.progress(progress_val)
    with stat_col2:
        # 这里显示的金额就是表格中所有已出价格的直接加总
        st.metric("2026年度已累积投入 (按每月1g计)", f"￥{accumulated_sum:,.2f}")

    # 渲染表格
    st.table(df_plan)

except Exception as e:
    st.error(f"分析失败: {e}")