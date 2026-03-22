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
    # 清理列名
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
    
    required = ['用户名', '个人实际销量', '投注单数', '个人游戏盈亏', 'RTP']
    if not all(r in actual_cols for r in required):
        st.error(f"❌ Excel 列名识别失败，请检查文件。")
        return None

    # 数据提取
    clean_df = pd.DataFrame()
    clean_df['用户名'] = df[actual_cols['用户名']].astype(str)
    for col in ['个人实际销量', '投注单数', '个人游戏盈亏', 'RTP']:
        clean_df[col] = pd.to_numeric(df[actual_cols[col]], errors='coerce').fillna(0)

    # 核心算法：返还额 = 销量 * RTP
    clean_df['返还额'] = clean_df['个人实际销量'] * clean_df['RTP']

    # 按用户名汇总
    grouped = clean_df.groupby('用户名').agg({
        '个人实际销量': 'sum', 
        '投注单数': 'sum', 
        '个人游戏盈亏': 'sum', 
        '返还额': 'sum'
    }).reset_index()

    # 计算加权 RTP
    grouped['RTP'] = grouped.apply(lambda x: x['返还额'] / x['个人实际销量'] if x['个人实际销量'] > 0 else 0, axis=1)

    # 异常判断标准
    def get_labels(row):
        m = []
        v, c, r, p = row['个人实际销量'], row['投注单数'], row['RTP'], row['个人游戏盈亏']
        if 1000 <= v <= 2000 and c < 12: m.append("疑似刷人数")
        if v > 500000 and 0.995 <= r <= 1: m.append("疑似刷量")
        if p > 100000: m.append("盈利大会员")
        if v > 2000 and c < 10: m.append("疑似对刷")
        return " | ".join(m) if m else None

    grouped['原因'] = grouped.apply(get_labels, axis=1)
    
    # 只过滤有问题的用户
    flagged = grouped
