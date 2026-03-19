import streamlit as st
import pandas as pd
import io

# 1. 页面配置
st.set_page_config(page_title="抓鬼", layout="wide")

# 2. 登录逻辑
if "auth" not in st.session_state:
    st.session_state.auth = False

if not st.session_state.auth:
    st.title("🔒 审计系统登录")
    pwd = st.text_input("请输入访问密码", type="password")
    if st.button("进入系统"):
        if pwd == "0224":
            st.session_state.auth = True
            st.rerun()
        else:
            st.error("密码错误")
    st.stop()

# 3. 核心审计逻辑
def run_audit(df):
    # 彻底清理：去掉全空行，清理表头空格
    df = df.dropna(how='all').reset_index(drop=True)
    df.columns = df.columns.astype(str).str.strip()
    
    # 自动兼容：常见列名转换映射
    rename_dict = {
        '个人销量': '个人实际销量',
        '实际销量': '个人实际销量',
        '盈亏': '个人游戏盈亏'
    }
    df = df.rename(columns=rename_dict)
    
    required = ['用户名', '个人实际销量', '投注单数', '个人游戏盈亏', 'RTP']
    missing = [c for c in required if c not in df.columns]
    
    if missing:
        st.error(f"❌ 识别失败：表格中缺少列 {', '.join(missing)}")
        st.write("当前检测到的列名有：", list(df.columns))
        return pd.DataFrame()

    # 强制转换数值，处理非数字字符
    for col in ['个人实际销量', '投注单数', '个人游戏盈亏', 'RTP']:
        df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)

    # 汇总计算
    grouped = df.groupby('用户名').agg({
        '个人实际销量': 'sum',
        '投注单数': 'sum',
        '个人游戏盈亏': 'sum',
        'RTP': 'mean'
    }).reset_index()

    # 审计标记逻辑 (4项核心条件)
    def get_labels(row):
        m = []
        v, c, r, p = row['个人实际销量'], row['投注单数'], row['RTP'], row['个人游戏盈亏']
        if 1000 <= v <= 2000 and c < 12: m.append("疑似刷人数")
        if v > 500000 and 0.995 <= r <= 1: m.append("疑似刷量")
        if p > 100000: m.append("盈利大会员")
        if v > 2000 and c < 10: m.append("疑似对刷")
        return " | ".join(m) if m else None

    grouped['异常标记'] = grouped.apply(get_labels, axis=1)
    return grouped[grouped['异常标记'].notna()]

# 4. 界面与暴力读取
st.title("📊 异常用户自动筛查系统")
uploaded_file = st.file_uploader("请上传 Excel (.xlsx 或 .xls)", type=["xlsx", "xls"])
