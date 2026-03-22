import streamlit as st
import pandas as pd
import io

# 1. 页面配置
st.set_page_config(page_title="抓鬼用户", layout="wide")

# 自定义 CSS：用于实现勾选后的“淡化”效果
st.markdown("""
    <style>
    .processed-text { color: #aaaaaa; text-decoration: line-through; }
    .stCheckbox { margin-bottom: 0px; }
    </style>
    """, unsafe_allow_html=True)

# 2. 登录逻辑
if "auth" not in st.session_state:
    st.session_state.auth = False

if not st.session_state.auth:
    st.title("🔒 抓抓抓")
    pwd = st.text_input("请输入访问密码", type="password")
    if st.button("进入系统"):
        if pwd == "0224":
            st.session_state.auth = True
            st.rerun()
        else:
            st.error("密码错误")
    st.stop()

# 3. 核心审计逻辑 (完全还原原始逻辑)
def run_audit(df):
    df.columns = [str(c).strip().replace('\n', '').replace('\r', '') for c in df.columns]
    
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
    
    required = ['用户名', '个人实际销量', '投注单数', '个人游戏盈亏', 'RTP']
    missing = [r for r in required if r not in actual_cols]
    
    if missing:
        st.error(f"❌ 识别失败：Excel 缺少列：{', '.join(missing)}")
        return None

    clean_df = pd.DataFrame()
    clean_df['用户名'] = df[actual_cols['用户名']].astype(str)
    for col in ['个人实际销量', '投注单数', '个人游戏盈亏', 'RTP']:
        clean_df[col] = pd.to_numeric(df[actual_cols[col]], errors='coerce').fillna(0)

    clean_df['返还额'] = clean_df['个人实际销量'] * clean_df['RTP']

    grouped = clean_df.groupby('用户名').agg({
        '个人实际销量': 'sum',
        '投注单数': 'sum',
        '个人游戏盈亏': 'sum',
        '返还额': 'sum'
    }).reset_index()

    # 计算最终加权 RTP (保持原始数值)
    grouped['RTP'] = grouped.apply(
        lambda x: x['返还额'] / x['个人实际销量'] if x['个人实际销量'] > 0 else 0, axis=1
    )

    def get_labels(row):
        m = []
        v, c, r, p = row['个人实际销量'], row['投注单数'], row['RTP'], row['个人游戏盈亏']
        if 1000 <= v <= 2000 and c < 12: m.append("疑似刷人数")
        if v > 500000 and 0.995 <= r <= 1: m.append("疑似刷量")
        if p > 100000: m.append("盈利大会员")
        if v > 2000 and c < 10: m.append("疑似对刷")
        return " | ".join(m) if m else None

    grouped['异常标记'] = grouped.apply(get_labels, axis=1)
    
    # 筛选异常用户
    flagged = grouped[grouped['异常标记'].notna()].copy()
    
    # 【修正点】：移除之前的百分比转换代码，保留原始数值
    return flagged[['用户名', '异常标记', '个人实际销量', '投注单数', '个人游戏盈亏', 'RTP']]

# 4. 界面展示
st.title("📊 抓到嘿咕 (已读标记版)")

uploaded_file = st.file_uploader("上传 Excel (.xlsx)", type=["xlsx"])

if uploaded_file:
    if "ghost_data" not in st.session_state or st.button("🔄 重新扫描文件"):
        try:
            raw_data = pd.read_excel(uploaded_file)
            st.session_state.ghost_data = run_audit(raw_data)
            st.session_state.ghost_read = set()
        except Exception as e:
            st.error(f"发生错误：{e}")

    res = st.session_state.get("ghost_data")

    if res is not None and not res.empty:
        done_num = len(st.session_state.ghost_read)
        st.warning(f"🎯 发现 {len(res)} 个异常账户 | 已核查: {done_num}")

        st.write("---")
        # 增加一列给序号或确认框
        h = st.columns([1, 2, 4, 2, 2, 2, 2])
        h[0].write("**确认**")
        h[1].write("**用户名**")
        h[2].write("**原因**")
        h[3].write("**销量**")
        h[4].write("**单数**")
        h[5].write("**盈亏**")
        h[6].write("**RTP**")

        for i, row in res.iterrows():
            uname = row['用户名']
            is_read = uname in st.session_state.ghost_read
            
            with st.container():
                cols = st.columns([1, 2, 4, 2, 2, 2, 2])
                
                # 勾选逻辑
                if cols[0].checkbox(" ", key=f"gk_{uname}", value=is_read):
                    st.session_state.ghost_read.add(uname)
                    is_read = True
                else:
                    st
