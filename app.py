import streamlit as st
import pandas as pd

st.set_page_config(page_title="阿贤", layout="wide")

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

def run_audit(df):
    df.columns = df.columns.str.strip()
    agg_rules = {
        '个人实际销量': 'sum',
        '投注单数': 'sum',
        '个人游戏盈亏': 'sum',
        'RTP': 'mean'
    }
    existing_cols = [c for c in agg_rules.keys() if c in df.columns]
    if '用户名' not in df.columns:
        st.error("Excel 中缺少 '用户名' 这一列！")
        return pd.DataFrame()

    grouped = df.groupby('用户名')[existing_cols].agg({k: agg_rules[k] for k in existing_cols}).reset_index()

    def get_labels(row):
        m = []
        v = row.get('个人实际销量', 0); c = row.get('投注单数', 0)
        r = row.get('RTP', 0); p = row.get('个人游戏盈亏', 0)
        if 1000 <= v <= 2000 and c < 12: m.append("疑似刷人数")
        if v > 500000 and 0.995 <= r <= 1: m.append("疑似刷量")
        if p > 100000: m.append("盈利大会员")
        if v > 2000 and c < 10: m.append("疑似对刷")
        return " | ".join(m) if m else None

    grouped['异常标记'] = grouped.apply(get_labels, axis=1)
    return grouped[grouped['异常标记'].notna()]

st.title("📊 异常用户自动筛查系统")
uploaded_file = st.file_uploader("请上传 Excel 档案", type=["xlsx", "xls"])

if uploaded_file:
    try:
        # 兼容性读取逻辑
        if uploaded_file.name.endswith('.xls'):
            try:
                data = pd.read_excel(uploaded_file, engine='xlrd')
            except:
                # 针对损坏或伪装 xls 的二次尝试
                data = pd.read_excel(uploaded_file)
        else:
            data = pd.read_excel(uploaded_file)
            
        res = run_audit(data)
        if not res.empty:
            st.warning(f"发现 {len(res)} 个异常账户")
            st.dataframe(res, use_container_width=True)
            csv = res.to_csv(index=False).encode('utf-8-sig')
            st.download_button("📥 导出审计结果", csv, "report.csv")
        else:
            st.success("✅ 未发现异常。")
    except Exception as e:
        st.error(f"文件解析失败。请尝试将文件【另存为】.xlsx 格式再上传。错误详情：{e}")
