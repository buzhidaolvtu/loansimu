import streamlit as st
import akshare as ak
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import datetime, timedelta
from fredapi import Fred

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

# --- 渲染宏观看板 ---
st.header("🎛 宏观博弈：实际利率 vs 美元强度")
st.caption("左轴：10年期美债实际利率 (%) | 右轴：美元指数 (指数越高说明美元越强)")

# 在代码顶部定义你的 Key (拿到后填入)
FRED_API_KEY = "7ca649d44293c1d55844b8806fa0305e"
# --- 数据获取函数 ---
@st.cache_data(ttl=86400)
def get_macro_data_from_fred():
    try:
        fred = Fred(api_key=FRED_API_KEY)
        # 1. 获取 10年期美债实际利率 (DFII10)
        real_rate = fred.get_series('DFII10')
        # 2. 获取 美元指数 (DTWEXBGS - 贸易加权美元指数，较稳定)
        dxy = fred.get_series('DTWEXBGS')

        # 合并并清理数据
        df_macro = pd.concat([real_rate, dxy], axis=1)
        df_macro.columns = ['real_rate', 'dxy']
        df_macro = df_macro.reset_index().rename(columns={'index': 'date'})

        # 筛选近 1 年数据
        one_year_ago = datetime.now() - timedelta(days=365)
        df_macro = df_macro[df_macro['date'] >= one_year_ago].dropna()
        return df_macro
    except Exception as e:
        st.error(f"FRED 接口调用失败，请检查 Key 或网络: {e}")
        return None
macro_df = get_macro_data_from_fred()

if macro_df is not None and not macro_df.empty:
    # 创建双 Y 轴图表
    fig_macro = make_subplots(specs=[[{"secondary_y": True}]])

    # 添加实际利率曲线 (左轴)
    fig_macro.add_trace(
        go.Scatter(x=macro_df['date'], y=macro_df['real_rate'],
                   name="10Y实际利率 (成本)", line=dict(color='#00BFFF', width=2)),
        secondary_y=False,
    )

    # 添加美元指数曲线 (右轴 - 使用浅色填充体现避险背景)
    fig_macro.add_trace(
        go.Scatter(x=macro_df['date'], y=macro_df['dxy'],
                   name="美元指数 (避险/信用)", line=dict(color='rgba(169, 169, 169, 0.5)', width=1),
                   fill='tozeroy', fillcolor='rgba(200, 200, 200, 0.1)'),
        secondary_y=True,
    )

    # 零轴线
    fig_macro.add_hline(y=0, line_dash="dash", line_color="red", secondary_y=False)

    # 布局美化
    fig_macro.update_layout(
        hovermode="x unified",
        template="plotly_white",
        height=400,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        margin=dict(t=30, b=10)
    )

    fig_macro.update_yaxes(title_text="实际利率 (%)", secondary_y=False)
    fig_macro.update_yaxes(title_text="美元指数", secondary_y=True)

    st.plotly_chart(fig_macro, use_container_width=True)

    # 增加实时宏观解读
    curr_rate = macro_df['real_rate'].iloc[-1]
    curr_dxy = macro_df['dxy'].iloc[-1]

    m_col1, m_col2 = st.columns(2)
    m_col1.write(f"📊 当前实际利率: **{curr_rate:.2f}%**")
    m_col2.write(f"💵 当前美元指数: **{curr_dxy:.2f}**")

    if curr_rate < 0:
        st.info("💡 提示：当前实际利率为负，持有黄金具有天然吸引力。")
    elif curr_dxy > 105:
        st.warning("⚠️ 警报：美元极强。若金价同步大涨，说明避险情绪极高，市场在对冲美元信用。")

else:
    st.info("正在等待 FRED 数据加载...")


@st.cache_data(ttl=3600)
def get_gold_daily_data():
    # 获取原始日线数据
    df = ak.spot_hist_sge(symbol="Au99.99")
    df['date'] = pd.to_datetime(df['date'])
    # 仅保留日期和收盘价
    df_daily = df[['date', 'close']].rename(columns={'close': 'price'})
    return df_daily


@st.cache_data(ttl=86400)
def get_cb_alpha_analysis(df_gold_daily):
    try:
        fred = Fred(api_key=FRED_API_KEY)
        # 获取10年期美债收益率 (日级)
        bond_yield = fred.get_series('DGS10')
        bond_df = bond_yield.reset_index()
        bond_df.columns = ['date', 'yield']
        bond_df['date'] = pd.to_datetime(bond_df['date'])

        # 建立索引进行日级合并
        df_cb = pd.merge(df_gold_daily, bond_df, on='date', how='inner')

        # 计算 30 日滚动相关性 (日级变化)
        # pct_change() 在日级数据上能反映最真实的博弈动量
        df_cb['corr'] = df_cb['price'].pct_change().rolling(30).corr(df_cb['yield'].pct_change())

        return df_cb.tail(365)  # 只看近一年
    except Exception as e:
        st.error(f"去美元化日级分析失败: {e}")
        return None

# 1. 获取日级金价
df_daily = get_gold_daily_data()
# 3. 渲染“去美元化”日级看板
cb_df = get_cb_alpha_analysis(df_daily)

if cb_df is not None:
    # 绘制相关性曲线
    fig_corr = go.Figure()
    fig_corr.add_trace(go.Scatter(
        x=cb_df['date'], y=cb_df['corr'],
        name="30日滚动相关性",
        line=dict(color='#FFD700', width=2),
        fill='tozeroy',
        fillcolor='rgba(255, 215, 0, 0.1)'
    ))

    # 增加参考线
    fig_corr.add_hline(y=0, line_dash="dash", line_color="white", opacity=0.5)
    fig_corr.add_hline(y=-0.5, line_dash="dot", line_color="green", annotation_text="正常负相关")

    fig_corr.update_layout(
        yaxis=dict(range=[-1, 1], title="相关系数"),
        height=300,
        template="plotly_white",
        margin=dict(t=10, b=10)
    )
    st.plotly_chart(fig_corr, use_container_width=True)

    # 深度解读逻辑
    latest_corr = cb_df['corr'].iloc[-1]
    if latest_corr > -0.2:
        st.success(f"🔥 **检测到静默溢价显著！** 当前相关性为 {latest_corr:.2f}。金价正在抵抗高利率压力，去美元化买盘强劲。")
    else:
        st.info(f"📊 当前相关性为 {latest_corr:.2f}。金价目前仍主要受宏观利率逻辑驱动。")


# --- 1. 定义博弈标签逻辑 ---
def get_battle_label(corr):
    if corr < -0.6:
        return "🍏 经典引力模式", "利率主导：金价严格跟随宏观成本，建议关注实际利率低点布局。", "normal"
    elif -0.6 <= corr < -0.2:
        return "🟡 博弈过渡模式", "情绪抬头：避险情绪开始干扰利率定价，金价波幅可能加大。", "off"
    elif -0.2 <= corr < 0.2:
        return "🔥 去美元化/信用对冲", "信用主导：机构不计成本减持美元资产，金价已脱离利率束缚！", "inverse"
    else:
        return "🚨 极端背离模式", "狂热/恐慌：金价与利率同涨。警惕高溢价下的短期剧烈波动。", "inverse"

# --- 2. 在 UI 中展示 (增加趋势提醒逻辑) ---
if cb_df is not None:
    latest_corr = cb_df['corr'].iloc[-1]
    # 获取过去 5 天的平均相关性，用于判断趋势稳定性
    avg_corr_5d = cb_df['corr'].tail(5).mean()

    label, desc, status_color = get_battle_label(latest_corr)

    st.subheader("🕵️ 市场博弈诊断与趋势预警")

    # 计算趋势提醒内容
    trend_note = ""
    trend_level = "info"  # info, warning, success

    if latest_corr > -0.2:
        if latest_corr > avg_corr_5d:
            trend_note = "🚀 **溢价加速中**：金价正快速脱离美债引力。这种‘极端背离’通常由突发地缘或央行大额扫货引起，短期冲力强但波动风险极大。"
            trend_level = "warning"
        else:
            trend_note = "🧘 **高位盘整中**：虽然仍处于‘去美元化’逻辑，但脱离程度有所收敛。说明市场正在消化高价，寻找新的信用锚点。"
            trend_level = "info"
    elif latest_corr < -0.6:
        trend_note = "📏 **回归理性**：金价重新回到实际利率的轨道。此时定投最稳，建议紧盯‘实际利率曲线’，利率见顶即是加仓良机。"
        trend_level = "success"
    else:
        trend_note = "🌀 **逻辑切换中**：市场正在利率与避险之间摇摆，方向不明。建议维持 2026 既定定投节奏，不宜激进调仓。"
        trend_level = "info"

    # 创建彩色看板
    battle_col1, battle_col2 = st.columns([1, 2])
    with battle_col1:
        st.metric("实时相关性锚点", f"{latest_corr:.2f}",
                  delta=f"{latest_corr - avg_corr_5d:.2f} (对比5日均值)",
                  help="接近-1为经典逻辑，接近0或转正为去美元化逻辑")
    with battle_col2:
        st.markdown(f"### {label}")
        if trend_level == "warning":
            st.warning(trend_note)
        elif trend_level == "success":
            st.success(trend_note)
        else:
            st.info(trend_note)

    # 针对定投的实操提醒
    st.markdown(f"> **2026实操策略提示：** {desc}")


def get_msi_analysis(df_daily, cb_df, macro_df):
    try:
        # 1. 计算价格乖离率 (Bias)
        price_now = df_daily['price'].iloc[-1]
        ma20 = df_daily['price'].rolling(20).mean().iloc[-1]
        bias_20 = (price_now - ma20) / ma20 * 100

        # 2. 计算相关性动量
        corr_now = cb_df['corr'].iloc[-1]
        corr_delta = corr_now - cb_df['corr'].tail(10).mean()

        # 3. 计算宏观抵抗力 (对比 DXY)
        dxy_change = macro_df['dxy'].pct_change().tail(5).mean()
        gold_change = df_daily['price'].pct_change().tail(5).mean()
        # 如果 DXY 涨且 Gold 涨，抵抗力得高分
        resistance_score = 100 if (dxy_change > 0 and gold_change > 0) else 50

        # 综合评分逻辑 (0-100)
        # 权重：40% 乖离度, 30% 相关性变动, 30% 宏观抵抗力
        msi_score = (min(abs(bias_20) * 5, 40) +
                     min(max(corr_delta * 200, 0), 30) +
                     (resistance_score * 0.3))

        return msi_score, bias_20
    except:
        return 50, 0


# --- 动量分析 ---
msi_val, b20 = get_msi_analysis(df_daily, cb_df, macro_df)

st.subheader("🚀 MSI 动量强度雷达")

# 1. 动量 Alert 核心逻辑
alert_text = ""
alert_type = "info" # 默认为普通信息

if msi_val > 75:
    alert_text = "🚨 【动量过热警报】MSI 评分已突破 75！市场进入极端狂热区，1118元附近追涨风险极大，建议仅维持 1g 基础定投，严禁任何大额加仓。"
    alert_type = "error"
    st.toast("发现极端动量过热，请警惕风险！", icon="🚨")
elif msi_val < 35:
    alert_text = "🟢 【动量机会提醒】MSI 评分低于 35。市场情绪当前较为低迷或存在超跌，1118元以下可能是长线布局的‘捡漏’机会。"
    alert_type = "success"
    st.toast("动量回落至机会区，建议关注布局。", icon="✅")
else:
    alert_text = "⚖️ 【动量平稳状态】当前 MSI 得分在 35-75 之间。动量处于健康博弈区间，无极端超买超卖，建议继续执行 2026 既定定投计划。"
    alert_type = "info"

m_col1, m_col2 = st.columns([1, 2])

with m_col1:
    st.metric("动量得分", f"{msi_val:.1f}/100",
              delta="超买风险" if msi_val > 70 else "动量健康",
              delta_color="inverse" if msi_val > 70 else "normal")

with m_col2:
    # 根据 Alert 状态显示不同颜色的提醒框
    if alert_type == "error":
        st.error(alert_text)
    elif alert_type == "success":
        st.success(alert_text)
    else:
        st.info(alert_text)

# 补充：原本的 Bias 详细解读（保留）
if msi_val > 80:
    st.warning(f"💡 深度诊断：当前价格偏离 20 日均线 {b20:.2f}%。这种动量通常由情绪驱动，慎防回调。")


# --- 在执行 MSI 分析后，构建历史动量序列 ---
@st.cache_data(ttl=3600)
def get_msi_history(df_daily, cb_df, macro_df):
    # 这里我们模拟计算过去 30 天的 MSI 走势
    msi_history = []
    dates = cb_df['date'].tail(30).tolist()

    # 为了效率，我们对 tail(30) 进行滚动计算
    for i in range(-30, 0):
        # 截取到当日的数据
        sub_df = df_daily.iloc[:len(df_daily) + i + 1]
        sub_cb = cb_df.iloc[:len(cb_df) + i + 1]
        sub_macro = macro_df.iloc[:len(macro_df) + i + 1]

        score, _ = get_msi_analysis(sub_df, sub_cb, sub_macro)
        msi_history.append(score)

    return pd.DataFrame({'date': dates, 'msi': msi_history})


# --- UI 渲染历史图表 ---
msi_hist_df = get_msi_history(df_daily, cb_df, macro_df)

fig_msi = go.Figure()
fig_msi.add_trace(go.Scatter(
    x=msi_hist_df['date'], y=msi_hist_df['msi'],
    mode='lines+markers',
    name='MSI 动量趋势',
    line=dict(color='#FF4500', width=3),
    fill='tozeroy',
    fillcolor='rgba(255, 69, 0, 0.1)'
))

# 增加 75 和 35 的阈值线
fig_msi.add_hline(y=75, line_dash="dash", line_color="red", annotation_text="超买区")
fig_msi.add_hline(y=35, line_dash="dash", line_color="green", annotation_text="机会区")

fig_msi.update_layout(
    title="🚀 近 30 日动量强度 (MSI) 演变趋势",
    yaxis=dict(range=[0, 100]),
    height=300,
    template="plotly_white"
)
st.plotly_chart(fig_msi, use_container_width=True)

# --- C. 基于动量的震荡箱体预测 ---
st.subheader("📦 未来 30 天震荡箱体预测")
curr_price = df_daily['price'].iloc[-1]
# 逻辑：动量越高，向上波动的概率越大；动量回落，向下寻找支撑
# 波动率估算 (利用过去 30 天标准差)
volatility = df_daily['price'].tail(30).std()

if msi_val > 60:
    support, resistance = curr_price - volatility, curr_price + (volatility * 1.5)
    box_msg = "🔥 **动量偏强**：价格大概率向上测试阻力位，回调空间有限。"
elif msi_val < 40:
    support, resistance = curr_price - (volatility * 1.5), curr_price + volatility
    box_msg = "❄️ **动量偏弱**：价格大概率向下寻找支撑，短期突破乏力。"
else:
    support, resistance = curr_price - volatility, curr_price + volatility
    box_msg = "⚖️ **均衡震荡**：价格将在窄幅区间内洗盘，消化高位压力。"

p_col1, p_col2 = st.columns(2)
p_col1.metric("预测支撑位 (地板)", f"￥{support:.2f}")
p_col2.metric("预测阻力位 (天花板)", f"￥{resistance:.2f}")
st.write(box_msg)

st.divider()


# --- 2. 数据处理：计算多周期 ROI 与 年化收益 ---
# (以下代码保持原样，未做任何逻辑修改)
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