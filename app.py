import streamlit as st
import pandas as pd
import io
import warnings

# 忽略干扰警告
warnings.filterwarnings('ignore')

st.set_page_config(page_title="抓鬼", layout="wide")

# 1. 登录逻辑 (维持 0224密码)
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

# 2. 审计核心逻辑
def run_audit(df):
    df.columns = df.columns.str.strip()
    # 自动处理表头：如果名字是“个人销量”，自动当成“个人实际销量”
    name_map = {'个人销量': '个人实际销量'}
    df = df.rename(columns=name_map)
    
    agg_rules = {
        '个人实际销量': 'sum',
        '投注单数': 'sum',
        '个人游戏盈亏': 'sum',
        'RTP': 'mean'
    }
    
    if '用户名' not in df.columns:
        st.error("❌ 找不到 '用户名' 列，请检查 Excel 内容。")
        return pd.DataFrame()
    
    existing_cols = [c for c in agg_rules.keys() if c in df.columns]
    for col in existing_cols:
        df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)

    grouped = df.groupby('用户名')[existing_cols].agg({k: agg_rules[k] for k in existing_cols}).reset_index()

    def get_labels(row):
        m = []
        v = row.get('个人实际销量', 0); c = row.get('投注单数', 0)
        r = row.get('RTP', 0); p = row.get('个人游戏盈亏', 0)
        # 你的四项严谨条件
        if 1000 <= v <= 2000 and c < 12: m.append("疑似刷人数")
        if v > 500000 and 0.995 <= r <= 1: m.append("疑似刷量")
        if p > 100000: m.append("盈利大会员")
        if v > 2000 and c < 10: m.append("疑似对刷")
        return " | ".join(m) if m else None

    grouped['异常标记'] = grouped.apply(get_labels, axis=1)
    return grouped[grouped['异常标记'].notna()]

# 3. 界面逻辑
st.title("📊 异常用户自动筛查系统")
st.info("💡 已开启【全格式兼容】模式，直接上传 .xls 即可。")

uploaded_file = st.file_uploader("请上传 Excel 档案", type=["xlsx", "xls"])

if uploaded_file:
    data = None
    file_bytes = uploaded_file.read()
    
    # --- 严谨的暴力读取测试 ---
    # 尝试 1: 针对 Workbook corruption，强行指定 xlrd
    if not data:
        try:
            data = pd.read_excel(io.BytesIO(file_bytes), engine='xlrd')
        except:
            pass

    # 尝试 2: 针对普通的 xlsx 或规范的 xls
    if data is None:
        try:
            data = pd.read_excel(io.BytesIO(file_bytes))
        except:
            pass

    # 尝试 3: 针对“伪装成 xls 的 HTML”（之前报 html5lib 的那种）
    if data is None:
        try:
            tables = pd.read_html(io.BytesIO(file_bytes), flavor='html5lib')
            data = tables[0]
        except:
            pass

    # 尝试 4: 针对“伪装成 xls 的文本/CSV”（解决 utf-8 报错）
    if data is None:
        try:
            # 自动探测编码尝试读取
            data = pd.read_csv(io.BytesIO(file_bytes), encoding='gbk')
        except:
            try:
                data = pd.read_csv(io.BytesIO(file_bytes), encoding='utf-8')
            except:
                pass

    # --- 最终判断 ---
    if data is not None:
        try:
            res = run_audit(data)
            if not res.empty:
                st.warning(f"分析完成：发现 {len(res)} 个异常账户")
                st.dataframe(res, use_container_width=True)
                st.download_button("📥 导出结果", res.to_csv(index=False).encode('utf-8-sig'), "report.csv")
            else:
                st.success("✅ 未发现异常。")
        except Exception as e:
            st.error(f"分析逻辑出错：{e}")
    else:
        st.error("❌ 这种 .xls 文件的内部结构太特殊了，目前所有解析器都失效。")
