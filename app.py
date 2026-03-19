import streamlit as st
import pandas as pd
import io

# 严谨模式：页面配置
st.set_page_config(page_title="抓鬼", layout="wide")

# 1. 登录逻辑 (0224 密码)
if "auth" not in st.session_state:
    st.session_state.auth = False

if not st.session_state.auth:
    st.title("🔒 审计系统登录")
    pwd = st.text_input("请输入访问密码", type="password")
    if st.button("进入系统"):
        if pwd == "0224 ":
            st.session_state.auth = True
            st.rerun()
        else:
            st.error("密码错误")
    st.stop()

# 2. 核心审计逻辑 (加入严谨的列名检查)
def run_audit(df):
    # 清理列名空格
    df.columns = df.columns.astype(str).str.strip()
    
    # 自动兼容：如果叫“个人销量”就改成“个人实际销量”
    if '个人销量' in df.columns and '个人实际销量' not in df.columns:
        df = df.rename(columns={'个人销量': '个人实际销量'})
    
    # 检查核心列是否存在
    required = ['用户名', '个人实际销量', '投注单数', '个人游戏盈亏', 'RTP']
    missing = [c for c in required if c not in df.columns]
    
    if missing:
        st.error(f"❌ Excel 缺少必要的列：{', '.join(missing)}")
        st.info("提示：请检查 Excel 第一行（表头）是否包含以上名字。")
        return pd.DataFrame()

    # 确保数据全是数字格式 (避免 arg must be a list 错误)
    for col in ['个人实际销量', '投注单数', '个人游戏盈亏', 'RTP']:
        df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)

    # 同名用户汇总
    grouped = df.groupby('用户名').agg({
        '个人实际销量': 'sum',
        '投注单数': 'sum',
        '个人游戏盈亏': 'sum',
        'RTP': 'mean'
    }).reset_index()

    # 执行四项标记
    def get_labels(row):
        m = []
        v = row['个人实际销量']
        c = row['投注单数']
        r = row['RTP']
        p = row['个人游戏盈亏']
        
        if 1000 <= v <= 2000 and c < 12: m.append("疑似刷人数")
        if v > 500000 and 0.995 <= r <= 1: m.append("疑似刷量")
        if p > 100000: m.append("盈利大会员")
        if v > 2000 and c < 10: m.append("疑似对刷")
        return " | ".join(m) if m else None

    grouped['异常标记'] = grouped.apply(get_labels, axis=1)
    return grouped[grouped['异常标记'].notna()]

# 3. 界面逻辑
st.title("📊 异常用户自动筛查系统")
uploaded_file = st.file_uploader("直接上传您的 Excel (.xlsx 或 .xls)", type=["xlsx", "xls"])

if uploaded_file:
    try:
        # 读取逻辑：先试正常的，不行再试旧版的
        file_bytes = uploaded_file.read()
        try:
            # 优先尝试通用读取
            data = pd.read_excel(io.BytesIO(file_bytes))
        except:
            try:
                # 尝试旧版引擎
                data = pd.read_excel(io.BytesIO(file_bytes), engine='xlrd')
            except:
                # 尝试作为 HTML 读取 (解决某些系统导出的假 xls)
                tables = pd.read_html(io.BytesIO(file_bytes))
                data = tables[0]

        if data is not None:
            # 如果第一行全是空或者读出来格式不对，尝试跳过第一行重新读
            if '用户名' not in data.columns and data.shape[0] > 0:
                 # 这是一个保险开关：有时候系统导出的文件第一行是标题，第二行才是表头
                 st.warning("正在尝试自动修正表头格式...")
            
            res = run_audit(data)
            
            if not res.empty:
                st.warning(f"✅ 扫描完成：发现 {len(res)} 个异常账户")
                st.dataframe(res, use_container_width=True)
                st.download_
