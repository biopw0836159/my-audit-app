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
    
    # --- 自动兼容列名逻辑 ---
    # 如果你的 Excel 列名不叫这些，请在这里添加映射
    rename_dict = {
        '个人销量': '个人实际销量',
        '实际销量': '个人实际销量',
        '盈亏': '个人游戏盈亏',
        '会员账号': '用户名',
        '账号': '用户名'
    }
    df = df.rename(columns=rename_dict)
    
    # 检查核心列
    required = ['用户名', '个人实际销量', '投注单数', '个人游戏盈亏', 'RTP']
    missing = [c for c in required if c not in df.columns]
    
    if missing:
        st.error(f"❌ 识别失败：表格中缺少列 {', '.join(missing)}")
        st.write("💡 我在你的 Excel 里看到的列名有：", list(df.columns))
        return pd.DataFrame(), False # 返回失败信号

    # 强制转换数值
    for col in ['个人实际销量', '投注单数', '个人游戏盈亏', 'RTP']:
        df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)

    # 汇总计算
    grouped = df.groupby('用户名').agg({
        '个人实际销量': 'sum',
        '投注单数': 'sum',
        '个人游戏盈亏': 'sum',
        'RTP': 'mean'
    }).reset_index()

    # 审计标记
    def get_labels(row):
        m = []
        v, c, r, p = row['个人实际销量'], row['投注单数'], row['RTP'], row['个人游戏盈亏']
        if 1000 <= v <= 2000 and c < 12: m.append("疑似刷人数")
        if v > 500000 and 0.995 <= r <= 1: m.append("疑似刷量")
        if p > 100000: m.append("盈利大会员")
        if v > 2000 and c < 10: m.append("疑似对刷")
        return " | ".join(m) if m else None

    grouped['异常标记'] = grouped.apply(get_labels, axis=1)
    return grouped, True

# 4. 界面与暴力读取
st.title("📊 异常用户自动筛查系统")
uploaded_file = st.file_uploader("请上传 Excel (.xlsx 或 .xls)", type=["xlsx", "xls"])

if uploaded_file:
    try:
        file_bytes = uploaded_file.read()
        data = None
        
        # 依次尝试各种读取引擎
        try:
            data = pd.read_excel(io.BytesIO(file_bytes))
        except:
            try:
                data = pd.read_excel(io.BytesIO(file_bytes), engine='xlrd')
            except:
                try:
                    tables = pd.read_html(io.BytesIO(file_bytes), flavor='html5lib')
                    data = tables[0]
                except:
                    st.error("❌ 还是读不了这个文件。请确保它不是加密文件。")

        if data is not None:
            # --- 诊断环节：先看看原始数据读得对不对 ---
            with st.expander("🔍 点击查看原始数据预览（诊断用）"):
                st.write("前 5 行数据：")
                st.dataframe(data.head())
                st.write("所有列名：", list(data.columns))

            # 运行分析
            res_all, success = run_audit(data)
            
            if success:
                # 只过滤出有问题的
                res_flagged = res_all[res_all['异常标记'].notna()]
                
                if not res_flagged.empty:
                    st.warning(f"✅ 发现 {len(res_flagged)} 个异常账户")
                    st.dataframe(res_flagged, use_container_width=True)
                    csv = res_flagged.to_csv(index=False).encode('utf-8-sig')
                    st.download_button("📥 导出审计结果", csv, "report.csv", "text/csv")
                else:
                    st.success("✅ 扫描完毕，原始数据读取正常，但【没有用户】符合异常条件。")
                    st.write("你可以检查一下汇总后的数据：")
                    st.dataframe(res_all.head(10)) # 显示前10个用户看看
                
    except Exception as e:
        st.error(f"解析过程中发生错误：{e}")
