import streamlit as st
import pandas as pd
import io

# 1. 页面配置：设置网页标题和宽屏模式
st.set_page_config(page_title="抓鬼用户", layout="wide")

# 2. 自定义 CSS 样式：处理“已读”后的灰色删除线效果
st.markdown("""
    <style>
    .processed-text { color: #aaaaaa; text-decoration: line-through; }
    .stCheckbox { margin-bottom: 0px; }
    </style>
    """, unsafe_allow_html=True)

# 3. 登录逻辑 (密码 0224)
if "auth" not in st.session_state:
    st.session_state.auth = False

if not st.session_state.auth:
    st.title("🔒 系统登录")
    pwd = st.text_input("请输入访问密码", type="password")
    if st.button("进入系统"):
        if pwd == "0224":
            st.session_state.auth = True
            st.rerun()
        else:
            st.error("密码错误")
    st.stop()

# 4. 核心审计函数 (完全保留你原本的加权算法和名目映射)
def run_audit(df):
    # 清理列名：去空格、去换行
    df.columns = [str(c).strip().replace('\n', '').replace('\r', '') for c in df.columns]
    
    # 兼容名目字典
    name_map = {
        '个人实际销量': ['个人实际销量', '投注', '个人销量', '实际销量', '销量'],
        '用户名': ['用户名', '会员账号', '账号', '会员', '用户'],
        '投注单数': ['投注单数', '投注次数', '单数', '总注单数', '次数'],
        '个人游戏盈亏': ['个人游戏盈亏', '盈亏', '游戏盈亏', '盈亏金额'],
        'RTP': ['RTP', '返还率', 'rtp', '返奖率']
    }
    
    actual_cols = {}
    for standard_name, aliases in name_map.items():
        for alias in aliases:
            if alias in df.columns:
                actual_cols[standard_name] = alias
                break
    
    # 必填项检查
    required = ['用户名', '个人实际销量', '投注单数', '个人游戏盈亏', 'RTP']
    missing = [r for r in required if r not in actual_cols]
    
    if missing:
        st.error(f"❌ 识别失败：Excel 缺少必要列：{', '.join(missing)}")
        return None

    # 数据提取与转换
    clean_df = pd.DataFrame()
    clean_df['用户名'] = df[actual_cols['用户名']].astype(str)
    for col in ['个人实际销量', '投注单数', '个人游戏盈亏', 'RTP']:
        clean_df[col] = pd.to_numeric(df[actual_cols[col]], errors='coerce').fillna(0)

    # 算法：返还额 = 销量 * RTP
    clean_df['返还额'] = clean_df['个人实际销量'] * clean_df['RTP']

    # 按用户名汇总
    grouped = clean_df.groupby('用户名').agg({
        '个人实际销量': 'sum',
        '投注单数': 'sum',
        '个人游戏盈亏': 'sum',
        '返还额': 'sum'
    }).reset_index()

    # 加权 RTP 计算 (保持原始数值，不转百分比)
    grouped['RTP'] = grouped.apply(
        lambda x: x['返还额'] / x['个人实际销量'] if x['个人实际销量'] > 0 else 0, axis=1
    )

    # 异常判断标准
    def get_labels(row):
        m = []
        v, c, r, p = row['个人实际销量'], row['投注单数'], row['RTP'], row['个人游戏盈亏']
        if 1000 <= v <= 2000 and c < 12: m.append("疑似刷人数")
        if v > 500000 and 0.995 <= r <= 1: m.append("疑似刷量")
        if p > 100000: m.append("盈利大会员")
        if v > 2000 and c < 10: m.append("疑似对刷")
        return " | ".join(m) if m else None

    grouped['异常标记'] = grouped.apply(get_labels, axis=1)
    
    # 筛选有标记的异常用户
    flagged = grouped[grouped['异常标记'].notna()].copy()
    
    # 返回精简字段
    return flagged[['用户名', '异常标记', '个人实际销量', '投注单数', '个人游戏盈亏', 'RTP']]

# 5. 界面显示
st.title("📊 抓到嘿咕 (反色标记版)")
st.info("💡 提示：点击左侧勾选框可将已处理的会员标记为灰色。")

uploaded_file = st.file_uploader("上传 Excel (.xlsx)", type=["xlsx"])

if uploaded_file:
    # 使用 session_state 存储数据，防止点击勾选时页面重置计算
    if "ghost_data" not in st.session_state or st.button("🔄 重新扫描文件"):
        try:
            raw_data = pd.read_excel(uploaded_file)
            st.session_state.ghost_data = run_audit(raw_data)
            st.session_state.ghost_read = set() # 初始化已读集合
        except Exception as e:
            st.error(f"文件读取错误：{e}")

    res = st.session
