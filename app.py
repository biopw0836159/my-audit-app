import streamlit as st
import pandas as pd

# 1. 页面配置
st.set_page_config(page_title="抓鬼用户", layout="wide")

# 2. 登录逻辑
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

# 3. 核心审计函数 (严谨原始逻辑)
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
    if not all(r in actual_cols for r in required):
        st.error("❌ Excel 列名识别失败")
        return None

    clean_df = pd.DataFrame()
    clean_df['用户名'] = df[actual_cols['用户名']].astype(str)
    for col in ['个人实际销量', '投注单数', '个人游戏盈亏', 'RTP']:
        clean_df[col] = pd.to_numeric(df[actual_cols[col]], errors='coerce').fillna(0)

    clean_df['返还额'] = clean_df['个人实际销量'] * clean_df['RTP']
    grouped = clean_df.groupby('用户名').agg({
        '个人实际销量': 'sum', '投注单数': 'sum', '个人游戏盈亏': 'sum', '返还额': 'sum'
    }).reset_index()
    grouped['RTP'] = grouped.apply(lambda x: x['返还额'] / x['个人实际销量'] if x['个人实际销量'] > 0 else 0, axis=1)

    def get_labels(row):
        m = []
        v, c, r, p = row['个人实际销量'], row['投注单数'], row['RTP'], row['个人游戏盈亏']
        if 1000 <= v <= 2000 and c < 12: m.append("疑似刷人数")
        if v > 500000 and 0.995 <= r <= 1: m.append("疑似刷量")
        if p > 100000: m.append("盈利大会员")
        if v > 2000 and c < 10: m.append("疑似对刷")
        return " | ".join(m) if m else None

    grouped['原因'] = grouped.apply(get_labels, axis=1)
    return grouped[grouped['原因'].notna()]

# 4. 界面
st.title("📊 抓到嘿咕 (反色标记版)")

file = st.file_uploader("上传 Excel", type=["xlsx"])

if file:
    # 强制点击按钮才刷新数据
    if "ghost_res" not in st.session_state or st.button("重新跑数据"):
        raw = pd.read_excel(file)
        st.session_state.ghost_res = run_audit(raw)
        st.session_state.ghost_read = set()

    res = st.session_state.get("ghost_res")

    if res is not None and not res.empty:
        st.warning(f"🎯 发现 {len(res)} 个异常")
        
        # 建立表头
        cols = st.columns([1, 2, 3, 2, 2, 2, 2])
        cols[0].write("确认")
        cols[1].write("用户名")
        cols[2].write("原因")
        cols[3].write("销量")
        cols[4].write("单数")
        cols[5].write("盈亏")
        cols[6].write("RTP")

        for i, row in res.iterrows():
            u = row['用户名']
            is_read = u in st.session_state.ghost_read
            
            c = st.columns([1, 2, 3, 2, 2, 2, 2])
            
            # 勾选框
            if c[0].checkbox(" ", key=f"k_{u}", value=is_read):
                st.session_state.ghost_read.add(u)
                is_read = True
            else:
                st.session_state.ghost_read.discard(u)
                is_read = False

            # 显示内容 (如果勾选了就变淡)
            color = "#ccc" if is_read else "#000"
            text_style = f"style='color:{color};'"
            
            c[1].markdown(f"<p {text_style}>{u}</p>", unsafe_allow_html=True)
            c[2].markdown(f"<p {text_style}>{row['原因']}</p>", unsafe_allow_html=True)
            c[3].markdown(f"<p {text_style}>{row['个人实际销量']}</p>", unsafe_allow_html=True)
            c[4].markdown(f"<p {text_style}>{row['投注单数']}</p>", unsafe_allow_html=True)
            c[5].markdown(f"<p {text_style}>{row['个人游戏盈亏']}</p>", unsafe_allow_html=True)
            c[6].markdown(f"<p {text_style}>{row['RTP']}</p>", unsafe_allow_html=True)

        st.write("---")
        csv = res.to_csv(index=False).encode('utf-8-sig')
        st.download_button("导出 CSV", csv, "report.csv")
