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

# 3. 核心工具：智能列名匹配
def find_col(columns, keywords):
    for col in columns:
        for key in keywords:
            if key in str(col):
                return col
    return None

# 4. 核心审计逻辑
def run_audit(df):
    # 清理数据：删掉全空行，清理表头
    df = df.dropna(how='all').reset_index(drop=True)
    df.columns = [str(c).strip() for c in df.columns]
    
    # 智能定位关键列
    col_user = find_col(df.columns, ['用户名', '账号', '会员', 'User'])
    col_sales = find_col(df.columns, ['个人实际销量', '实际销量', '个人销量', '销量', 'Sales'])
    col_count = find_col(df.columns, ['投注单数', '单数', 'Count'])
    col_rtp = find_col(df.columns, ['RTP', '返还率'])
    col_profit = find_col(df.columns, ['个人游戏盈亏', '盈亏', 'Profit'])

    # 严谨检查
    mapping = {
        "用户名": col_user,
        "个人实际销量": col_sales,
        "投注单数": col_count,
        "RTP": col_rtp,
        "个人游戏盈亏": col_profit
    }
    
    missing = [k for k, v in mapping.items() if v is None]
    if missing:
        st.error(f"❌ 匹配失败！Excel 中找不到这些信息：{', '.join(missing)}")
        st.write("🔍 我在表格里看到的列名有：", list(df.columns))
        return pd.DataFrame(), False

    # 准备标准化的数据
    audit_df = pd.DataFrame()
    audit_df['用户名'] = df[col_user].astype(str)
    
    # 强制数值化，解决 "arg must be a list" 报错
    for target, source in [('销量', col_sales), ('单数', col_count), ('盈亏', col_profit), ('RTP', col_rtp)]:
        audit_df[target] = pd.to_numeric(df[source], errors='coerce').fillna(0)

    # 汇总计算
    grouped = audit_df.groupby('用户名').agg({
        '销量': 'sum',
        '单数': 'sum',
        '盈亏': 'sum',
        'RTP': 'mean'
    }).reset_index()

    # 审计标记
    def get_labels(row):
        m = []
        v, c, r, p = row['销量'], row['单数'], row['RTP'], row['盈亏']
        if 1000 <= v <= 2000 and c < 12: m.append("疑似刷人数")
        if v > 500000 and 0.995 <= r <= 1: m.append("疑似刷量")
        if p > 100000: m.append("盈利大会员")
        if v > 2000 and c < 10: m.append("疑似对刷")
        return " | ".join(m) if m else None

    grouped['异常标记'] = grouped.apply(get_labels, axis=1)
    return grouped, True

# 5. 界面
st.title("📊 异常用户自动筛查系统")
uploaded_file = st.file_uploader("请上传 Excel (.xlsx 或 .xls)", type=["xlsx", "xls"])

if uploaded_file:
    try:
        file_bytes = uploaded_file.read()
        data = None
        
        # 依次尝试读取方式
        engines = [None, 'xlrd', 'html5lib']
        for engine in engines:
            try:
                if engine == 'html5lib':
                    tables = pd.read_html(io.BytesIO(file_bytes), flavor='html5lib')
                    data = tables[0]
                else:
                    data = pd.read_excel(io.BytesIO(file_bytes), engine=engine)
                if data is not None: break
            except:
                continue

        if data is not None:
            # 自动跳过文件顶部的废话标题行
            if data.shape[1] < 2: # 只有一列肯定读错了
                st.error("读取到的列数太少，请检查文件格式。")
            else:
                res_all, success = run_audit(data)
                if success:
                    res_flagged = res_all[res_all['异常标记'].notna()]
                    if not res_flagged.empty:
                        st.warning(f"✅ 发现 {len(res_flagged)} 个异常账户")
                        st.dataframe(res_flagged, use_container_width=True)
                        st.download_button("📥 导出审计结果", res_flagged.to_csv(index=False).encode('utf-8-sig'), "report.csv")
                    else:
                        st.success("✅ 扫描完毕，未发现符合条件的异常用户。")
                        with st.expander("查看所有用户汇总数据"):
                            st.dataframe(res_all)
                
    except Exception as e:
        st.error(f"致命错误：{e}")
