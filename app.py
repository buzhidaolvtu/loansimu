import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
import numpy as np
import matplotlib
from matplotlib import font_manager
import os


# --- 0. 修复 Matplotlib 中文显示问题 ---
# 尝试寻找系统中可用的中文字体
def set_matplot_zh():
    # 假设 msyh.ttf 放在代码根目录下
    font_file = "msyh.ttf"

    if os.path.exists(font_file):
        # 1. 注册字体文件
        font_manager.fontManager.addfont(font_file)
        # 2. 获取该字体的正式名称
        prop = font_manager.FontProperties(fname=font_file)
        # 3. 设置为全局字体
        plt.rcParams['font.family'] = prop.get_name()
        plt.rcParams['axes.unicode_minus'] = False  # 修复负号显示
        return prop.get_name()
    else:
        # 如果文件丢失，针对 Mac 的后备方案
        st.warning("未找到 msyh.ttf，尝试调用 Mac 系统字体...")
        plt.rcParams['font.sans-serif'] = ['Arial Unicode MS', 'sans-serif']
        return "Arial Unicode MS"


zh_font = set_matplot_zh()
if zh_font:
    matplotlib.rc('font', family=zh_font)
plt.rcParams['axes.unicode_minus'] = False  # 正常显示负号

# 设置页面配置
st.set_page_config(page_title="房贷资金决策专业版", layout="wide")

# --- 1. 侧边栏：核心参数配置 ---
st.sidebar.header("⚙️ 贷款与投资参数")
total_principal = st.sidebar.number_input("待处理资金本金 (元)", 10000, 5000000, 50000, 5000)
years = st.sidebar.slider("剩余贷款期限 (年)", 1, 30, 27)
loan_rate = st.sidebar.slider("房贷年利率 (%)", 1.0, 6.0, 3.15, 0.05) / 100
repayment_type = st.sidebar.radio("还款方式", ["等额本息", "等额本金"])

st.sidebar.header("📈 投资参数")
cash_yield = st.sidebar.slider("方案1：现金理财收益率 (%)", 0.0, 10.0, 0.0, 0.1) / 100
stock_dividend_annual = st.sidebar.number_input("方案3：预计每年分红总额 (元)", 0, 1000000, 2800)


# --- 2. 核心数学解耦函数 ---

def get_repayment_schedule(p, r, t, mode):
    """函数 A: 专门计算贷款还款流水 (支出项)"""
    months = t * 12
    monthly_r = r / 12
    schedule = []
    if mode == "等额本息":
        monthly_payment = (p * monthly_r * (1 + monthly_r) ** months) / ((1 + monthly_r) ** months - 1)
        schedule = [monthly_payment] * months
    else:  # 等额本金
        monthly_p = p / months
        for i in range(months):
            interest = (p - i * monthly_p) * monthly_r
            schedule.append(monthly_p + interest)
    return schedule


def simulate_account_balance(p, schedule, invest_yield, annual_dividend, is_stock=False):
    """函数 B: 专门模拟账户余额演变 (对冲项)"""
    balance = p
    history = []
    monthly_invest_r = invest_yield / 12
    for m, payment in enumerate(schedule, 1):
        # 收入端
        if is_stock:
            if m % 12 == 0: balance += annual_dividend  # 方案3：年度注入
        else:
            balance = balance * (1 + monthly_invest_r)  # 方案1：月度复利
        # 支出端
        balance -= payment
        history.append(balance)
    return history


# --- 3. 执行逻辑 ---
repayment_schedule = get_repayment_schedule(total_principal, loan_rate, years, repayment_type)
total_interest_cost = sum(repayment_schedule) - total_principal
first_month_payment = repayment_schedule[0]
stock_roi = stock_dividend_annual / total_principal
history_cash = simulate_account_balance(total_principal, repayment_schedule, cash_yield, 0, is_stock=False)
history_stock = simulate_account_balance(total_principal, repayment_schedule, 0, stock_dividend_annual, is_stock=True)

# --- 4. 页面呈现 ---
st.title("🏠 房贷资金方案仿真模拟器")
st.info(f"分析目标：将 **{total_principal:,}元** 用于不同方案。贷款模式：**{repayment_type}**，期限 **{years}年**。")

m1, m2, m3 = st.columns(3)
with m1: st.metric("方案2节省总利息", f"{total_interest_cost:,.2f} 元")
with m2: st.metric("当前月供压力 (首月)", f"{first_month_payment:,.2f} 元")
with m3: st.metric("方案3年度利差", f"{(stock_roi - loan_rate) * 100:.2f}%")

# 5. 定性评价
st.divider()
st.subheader("📊 方案定性对比 (维度评价)")
stars_data = {
    "评价维度": ["降低债务 (Debt Reduction)", "持有现金流 (Cash Flow)", "持有资产 (Assets)"],
    "方案1：持有现金": ["★☆☆", "★★★", "★☆☆"],
    "方案2：提前还贷": ["★★★", "☆☆☆", "☆☆☆"],
    "方案3：购买股票": ["☆☆☆", "★☆☆", "★★★"]
}
st.table(pd.DataFrame(stars_data))

# 6. 量化坐标轴
st.subheader("🎯 风险-收益量化对比")
col_plot, col_text = st.columns([2, 1])
with col_plot:
    plot_data = {
        "方案1：持有现金": {"roi": cash_yield, "risk": 2, "color": '#1f77b4', "marker": 'o'},
        "方案2：提前还贷": {"roi": loan_rate, "risk": 7, "color": '#2ca02c', "marker": 's'},
        "方案3：购买股票": {"roi": stock_roi, "risk": 9, "color": '#d62728', "marker": 'D'}
    }
    fig, ax = plt.subplots(figsize=(10, 5))
    ax.axvline(x=loan_rate, color='gray', linestyle='--', alpha=0.5)
    ax.fill_between([0, loan_rate], 0, 12, color='red', alpha=0.05)
    ax.fill_between([loan_rate, 0.15], 0, 12, color='green', alpha=0.05)
    for name, data in plot_data.items():
        ax.scatter(data['roi'], data['risk'], s=300, c=data['color'], marker=data['marker'], label=name, edgecolors='black', zorder=5)
        ax.annotate(name, (data['roi'], data['risk']), xytext=(5, 5), textcoords='offset points')
    ax.set_xlabel("预期收益率 (ROI)");
    ax.set_ylabel("综合风险 (生活+市场)");
    ax.set_ylim(0, 12)
    st.pyplot(fig)
with col_text:
    st.write("### 📖 坐标轴说明")
    st.markdown(f"""
        **1. 横轴 (ROI): 资金回报率**
        - 以 **房贷利率 ({loan_rate*100:.2f}%)** 为生命线。
        - **红色区域 (左侧)**: 负利差区。意味着你的资金增值速度慢于债务吞噬速度，长期持有将导致本金缩水。
        - **绿色区域 (右侧)**: 正利差区。利用低息贷款作为杠杆，实现资产净值扩张。

        **2. 纵轴 (Risk): 综合风险评分**
        - **方案1 (风险2)**: 风险主要来自通胀和利差损耗，但生活应急能力极强。
        - **方案2 (风险6)**: 虽然无波动风险，但由于 **现金流完全锁死** 导致生活防御力下降，风险评分设为中等。
        - **方案3 (风险9)**: 承受股价波动的本金风险，需具备极强的心理素质。
        """)

    # 动态实时分析
    spread = (stock_roi - loan_rate) * 100
    if spread > 0:
        st.success(f"**当前状态：正向套利**\n\n方案3比方案2多出 **{spread:.2f}%** 的年化收益，属于优质财务杠杆。")
    else:
        st.error(f"**当前状态：利差倒挂**\n\n方案3收益低于还贷节省，建议优先考虑方案2。")

# 7. 终值预测
st.divider()
st.subheader(f"⏳ 长期价值增长推演 ({years}年终值预测)")
fv_df = pd.DataFrame({
    "方案": ["方案1 (理财账户结余)", "方案2 (还贷基准)", "方案3 (股票账户结余)"],
    "金额": [history_cash[-1], 0, history_stock[-1]]
})
st.bar_chart(fv_df.set_index("方案"))

# 8. 详细数学逻辑说明
with st.expander("🔍 查看计算方法与数学逻辑 (解耦版仿真原理)"):
    st.write("### 1. 债务端：刚性月供流出 (Loan Repayment Schedule)")
    st.write("程序首先生成一条精确到月的还款流水。")
    st.latex(r"Monthly\ Outflow = \text{Amortization}(P, r_{loan}, n)")

    st.write("### 2. 资产端：差异化收入模拟 (Asset Inflow Models)")
    c1, c2 = st.columns(2)
    with c1:
        st.markdown("**方案1：月度复利 (理财)**")
        st.latex(r"Inflow_{m} = Balance_{m-1} \cdot \frac{r_{cash}}{12}")
    with c2:
        st.markdown("**方案3：年度分红 (股票)**")
        st.latex(r"Inflow_{annual} = Dividend_{fixed}")
        st.caption("注：假设股票本金锁定，不计月度复利，仅执行年度补血。")

    st.write("### 3. 账户平衡方程 (Account Balance Equation)")
    st.latex(r"Balance_{m} = Balance_{m-1} + Inflow_{m} - Outflow_{m}")
    st.markdown("""
    > **核心逻辑：**
    > * **方案1**：利差收益 $r_{cash}$ 往往无法覆盖利息支出，导致本金被逐月“摊薄”甚至耗尽。
    > * **方案3**：年度分红若大于年度总还款额，账户结余将呈阶梯状上升，形成强力套利。
    """)

# 9. 建议
st.divider()
st.subheader("📋 综合决策建议")
col_a, col_b, col_c = st.columns(3)
with col_a: st.info("**方案1**：支付利差买“安全感”，适合现金不足用户。")
with col_b: st.success("**方案2**：消灭负债，最简单的风险对冲。")
with col_c: st.warning("**方案3**：利用低息杠杆持有高息资产，实现资产扩张。")