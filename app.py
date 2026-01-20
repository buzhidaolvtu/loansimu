import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
import numpy as np

# 设置页面配置
st.set_page_config(page_title="房贷资金决策专业版", layout="wide")

# 1. 侧边栏：核心参数配置
st.sidebar.header("⚙️ 贷款与投资参数")
total_principal = st.sidebar.number_input("待处理资金本金 (元)", 10000, 1000000, 50000, 5000)
years = st.sidebar.slider("剩余贷款期限 (年)", 1, 30, 27)
loan_rate = st.sidebar.slider("房贷年利率 (%)", 1.0, 6.0, 3.15, 0.05) / 100
repayment_type = st.sidebar.radio("还款方式", ["等额本息", "等额本金"])

st.sidebar.header("📈 投资参数")
cash_yield = st.sidebar.slider("方案1：现金理财收益率 (%)", 0.5, 5.0, 2.0, 0.1) / 100
stock_dividend_annual = st.sidebar.number_input("方案3：预计每年分红总额 (元)", 0, 50000, 2800)


# 2. 核心数学计算逻辑
def calculate_loan_details(p, r, t, mode):
    months = t * 12
    monthly_r = r / 12
    if mode == "等额本息":
        monthly_payment = (p * monthly_r * (1 + monthly_r) ** months) / ((1 + monthly_r) ** months - 1)
        total_interest = monthly_payment * months - p
        first_month_payment = monthly_payment
    else:  # 等额本金
        monthly_p = p / months
        payments = []
        for i in range(months):
            interest = (p - i * monthly_p) * monthly_r
            payments.append(monthly_p + interest)
        total_interest = sum(payments) - p
        first_month_payment = payments[0]
    return total_interest, first_month_payment


total_interest_cost, first_month_payment = calculate_loan_details(total_principal, loan_rate, years, repayment_type)
stock_roi = stock_dividend_annual / total_principal

# 3. 页面标题
st.title("🏠 房贷资金方案仿真模拟器")
st.info(f"分析目标：将 **{total_principal:,}元** 用于不同方案。贷款模式：**{repayment_type}**，期限 **{years}年**。")

# 4. 数据仪表盘
m1, m2, m3 = st.columns(3)
with m1:
    st.metric("方案2节省总利息", f"{total_interest_cost:,.2f} 元")
with m2:
    st.metric("当前月供压力 (首月)", f"{first_month_payment:,.2f} 元")
with m3:
    st.metric("方案3套利空间 (对比贷款利率)", f"{(stock_roi - loan_rate) * 100:.2f}%")

# 5. 方案定性对比 (3颗星模块)
st.divider()
st.subheader("📊 方案定性对比 (维度评价)")
stars_data = {
    "评价维度": ["降低债务 (Debt Reduction)", "持有现金流 (Cash Flow)", "持有资产 (Assets)"],
    "方案1：持有现金": ["★☆☆", "★★★", "★☆☆"],
    "方案2：提前还贷": ["★★★", "☆☆☆", "☆☆☆"],
    "方案3：购买股票": ["☆☆☆", "★☆☆", "★★★"]
}
st.table(pd.DataFrame(stars_data))

# 6. 综合风险-收益坐标系
st.subheader("🎯 风险-收益量化对比")
col_plot, col_text = st.columns([2, 1])

with col_plot:
    plot_data = {
        "方案1：持有现金": {"roi": cash_yield, "risk": 2, "color": '#1f77b4', "marker": 'o'},
        "方案2：提前还贷": {"roi": loan_rate, "risk": 7, "color": '#2ca02c', "marker": 's'},
        "方案3：购买股票": {"roi": stock_roi, "risk": 9, "color": '#d62728', "marker": 'D'}
    }
    fig, ax = plt.subplots(figsize=(10, 5))
    plt.rcParams['font.sans-serif'] = ['SimHei'];
    plt.rcParams['axes.unicode_minus'] = False
    ax.axvline(x=loan_rate, color='gray', linestyle='--', alpha=0.5)
    ax.fill_between([0, loan_rate], 0, 12, color='red', alpha=0.05)
    ax.fill_between([loan_rate, 0.1], 0, 12, color='green', alpha=0.05)
    for name, data in plot_data.items():
        ax.scatter(data['roi'], data['risk'], s=300, c=data['color'], marker=data['marker'], label=name, edgecolors='black', zorder=5)
        ax.annotate(f"{name}\n(ROI: {data['roi'] * 100:.2f}%)", (data['roi'], data['risk']), xytext=(5, 5), textcoords='offset points')
    ax.set_xlabel("预期收益率 (ROI)");
    ax.set_ylabel("综合风险 (生活+市场)");
    ax.set_ylim(0, 12)
    st.pyplot(fig)

with col_text:
    st.markdown(f"### 📑 决策拆解")
    st.write(f"在{repayment_type}模式下，这{total_principal:,}元本金对应的利息总支出为 **{total_interest_cost:,.2f}元**。")
    annual_loan_cost = total_interest_cost / years
    if stock_dividend_annual > annual_loan_cost:
        st.success(f"方案3年分红高于年均利息支出({annual_loan_cost:.0f}元)，实现财务套利。")
    else:
        st.warning(f"方案3分红无法完全覆盖平均利息成本。")

# 7. 长期价值增长推演 (修正逻辑并联动标题)
st.divider()
st.subheader(f"⏳ 长期价值增长推演 ({years}年终值预测)")

# 采用净资产视角 (净资产 = 投资终值 - 贷款利息成本)
# 方案1: (本金复利增值) - (总利息支出)
fv_1_net = (total_principal * (1 + cash_yield) ** years) - total_interest_cost
# 方案2: 基准线 (还贷后利息支出为0，本金保全)
fv_2_net = total_principal
# 方案3: (分红复利增值) - (总利息支出)
fv_3_net = (total_principal * (1 + stock_roi) ** years) - total_interest_cost

fv_df = pd.DataFrame({
    "方案": ["方案1 (现金净值)", "方案2 (提前还贷基准)", "方案3 (投资净值)"],
    "金额": [fv_1_net, fv_2_net, fv_3_net]
})

st.bar_chart(fv_df.set_index("方案"))

if fv_1_net < fv_2_net:
    st.write(f"💡 **结果分析：** 方案1的终值低于方案2，是因为在这 **{years}** 年间，现金收益率未能覆盖 **{loan_rate*100:.2f}%** 的复利贷款成本。")

# 8. 详细评价结论
st.divider()
st.subheader("📋 综合决策建议")
t1, t2, t3 = st.columns(3)
with t1:
    st.info("**方案1：现金为王**\n\n适合近期有不确定支出（如医疗、择业）的用户。你支付的利差实质上是“流动性保险费”。")
with t2:
    st.success("**方案2：稳健首选**\n\n无风险锁定收益。如果你的备用金已经充足，且没有稳定的高收益投资渠道，这是最理性的选择。")
with t3:
    st.warning("**方案3：杠杆套利**\n\n适合长期投资者。利用低息房贷作为杠杆持有高股息资产，只要能扛住股价波动，这是资产跨越式增长的唯一途径。")