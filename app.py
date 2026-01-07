
import streamlit as st
import pandas as pd
import requests
import re
from datetime import datetime

# ==========================================
# 1. 页面基础设置
# ==========================================
st.set_page_config(
    page_title="黄金溢价监测看板",
    layout="wide",
    page_icon="💰"
)

# 自定义CSS，让指标数值更大更醒目
st.markdown("""
<style>
    .big-font { font-size: 24px !important; font-weight: bold; }
    .highlight { color: #d63031; font-weight: bold; }
    /* 调整 Metric 样式 */
    [data-testid="stMetricValue"] {
        font-size: 2rem;
    }
</style>
""", unsafe_allow_html=True)

st.title("💰 黄金饰品溢价分析：周大福 vs 国际金")
st.markdown("---")

# ==========================================
# 2. 数据获取函数 (新浪财经实时接口)
# ==========================================
@st.cache_data(ttl=30) # 30秒刷新一次，保证汇率和金价实时性
def get_realtime_data():
    """
    同时获取：伦敦金(XAU) 和 美元兑人民币汇率(USDCNY)
    使用新浪财经最快的 Ticker 接口 (字符串格式)
    """
    # hf_XAU = 伦敦金, fx_susdcny = 美元兑人民币
    url = "http://hq.sinajs.cn/list=hf_XAU,fx_susdcny"
    headers = {'Referer': 'https://finance.sina.com.cn/'}
    
    try:
        r = requests.get(url, headers=headers, timeout=5)
        text = r.text
        # 返回格式示例: 
        # var hq_str_hf_XAU="2034.50, ...";
        # var hq_str_fx_susdcny="7.1534, ...";
        
        # 1. 解析黄金价格
        xau_str = re.search(r'hq_str_hf_XAU="(.*?)";', text).group(1)
        xau_list = xau_str.split(',')
        xau_price = float(xau_list[0]) # 实时价格
        
        # 2. 解析汇率
        rate_str = re.search(r'hq_str_fx_susdcny="(.*?)";', text).group(1)
        rate_list = rate_str.split(',')
        usd_cny_rate = float(rate_list[1]) # 现汇买入价/中间价
        
        return xau_price, usd_cny_rate
        
    except Exception as e:
        st.error(f"数据获取失败: {e}")
        return 0, 0

# ==========================================
# 3. 侧边栏：用户控制区
# ==========================================
with st.sidebar:
    st.header("⚙️ 参数设置")
    st.info("💡 品牌金价每日更新一次，建议手动校准")
    
    # 默认值给一个大概的市场价，防止报错
    ctf_price_input = st.number_input(
        "今日周大福金价 (元/克)", 
        min_value=500.0, 
        max_value=1000.0, 
        value=736.0, # 这里的默认值你可以随时改
        step=1.0,
        format="%.1f"
    )
    
    st.markdown("---")
    st.markdown("**计算公式说明：**")
    st.markdown("1. 金衡盎司 = 31.1035 克")
    st.markdown("2. 国际金成本 = (XAU × 汇率) ÷ 31.1035")
    st.markdown("3. 溢价率 = (品牌价 - 成本) ÷ 成本")
    
    if st.button("🔄 强制刷新行情"):
        st.cache_data.clear()

# ==========================================
# 4. 核心计算逻辑
# ==========================================
xau_price, exchange_rate = get_realtime_data()

if xau_price > 0:
    # 核心换算公式
    GRAMS_PER_OUNCE = 31.1035
    
    # 国际金价换算成人民币/克
    intl_gold_cny_g = (xau_price * exchange_rate) / GRAMS_PER_OUNCE
    
    # 计算差价和溢价
    price_diff = ctf_price_input - intl_gold_cny_g
    premium_rate = (price_diff / intl_gold_cny_g) * 100

    # ==========================================
    # 5. 界面展示
    # ==========================================
    
    # 第一排：基础数据源
    c1, c2, c3 = st.columns(3)
    c1.metric("🌍 伦敦金 (XAU)", f"${xau_price:,.2f}", delta="实时")
    c2.metric("💱 美元汇率 (USD/CNY)", f"{exchange_rate:.4f}")
    c3.metric("⚖️ 国际金折算价 (原料成本)", f"¥{intl_gold_cny_g:.2f} /克")
    
    st.markdown("---")
    
    # 第二排：对比分析 (重点区域)
    st.subheader("📊 品牌溢价分析")
    
    col_retail, col_diff, col_premium = st.columns(3)
    
    with col_retail:
        st.info("品牌零售端")
        st.metric("周大福今日金价", f"¥{ctf_price_input:.0f} /克")
        
    with col_diff:
        st.warning("每克价差 (工费+利润)")
        st.metric("价差金额", f"¥{price_diff:.2f} /克")
        
    with col_premium:
        # 根据溢价率变色
        color_state = "normal"
        if premium_rate > 30:
            state_msg = "🔴 溢价极高"
        elif premium_rate > 20:
            state_msg = "🟡 溢价适中"
        else:
            state_msg = "🟢 溢价较低"
            
        st.success(f"当前溢价率 ({state_msg})")
        st.metric("溢价幅度", f"{premium_rate:.2f}%")

    # ==========================================
    # 6. 可视化条形图
    # ==========================================
    st.markdown("### 💰 价格构成可视化")
    
    # 构造画图数据
    chart_data = pd.DataFrame({
        '价格构成': ['国际原料成本', '品牌溢价(工费/利润)'],
        '金额': [intl_gold_cny_g, price_diff]
    })
    
    # 使用 Plotly 画一个堆叠条形图或者饼图，这里用简单的柱状图对比
    import plotly.graph_objects as go

    fig = go.Figure()
    
    # 原料成本柱子
    fig.add_trace(go.Bar(
        x=['每克价格构成'], 
        y=[intl_gold_cny_g], 
        name='国际原料成本',
        marker_color='#b2bec3',
        text=f"{intl_gold_cny_g:.0f}",
        textposition='auto'
    ))
    
    # 溢价柱子
    fig.add_trace(go.Bar(
        x=['每克价格构成'], 
        y=[price_diff], 
        name='品牌溢价',
        marker_color='#ff7675',
        text=f"+{price_diff:.0f}",
        textposition='auto'
    ))

    fig.update_layout(
        barmode='stack', 
        height=300,
        title_text="你花的每一分钱去了哪里？",
        yaxis_title="人民币 (元)",
        showlegend=True
    )
    
    st.plotly_chart(fig, use_container_width=True)

    # 底部说明
    st.caption(f"注：数据最后更新于 {datetime.now().strftime('%H:%M:%S')}。周大福价格为手动录入/默认值，仅供参考。")

else:
    st.error("正在连接全球市场，请稍后...")
