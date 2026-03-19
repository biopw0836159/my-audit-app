import streamlit as st
import pandas as pd
import io

# 1. 页面配置
st.set_page_config(page_title="抓鬼", layout="wide")

# 2. 登录逻辑 (0224 密码)
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

# 3. 核心审计逻辑 (加入严谨的数据清理)
def run_audit(df):
    # 【严谨步骤 1】清理列名：转字符串、去空格、去回车
    df.columns = [str(c).strip().replace('\n', '').replace('\r', '') for c in df.columns]
    
    # 【严谨步骤 2】自动匹配可能的列名 (防止转档后名字微变)
    name_map = {
        '个人实际销量': ['个人实际销量', '个人销量', '实际销量', '销量'],
        '用户名': ['用户名', '会员账号', '账号', '会员'],
        '投注单数': ['投注单数', '单数', '总注单数'],
        '个人游戏盈亏': ['个人游戏盈亏', '盈亏', '游戏盈亏'],
        'RTP': ['RTP', '返还率', 'rtp']
    }
    
    actual_cols = {}
    for standard_name, aliases in name_map.items():
        for alias in aliases:
            if alias in df.columns:
                actual_cols[standard_name] = alias
                break
    
    # 检查是否找齐了核心列
    required = ['用户名', '个人实际销量', '投注单数', '个人游戏盈亏', 'RTP']
    missing = [r for r in required if r not in actual_cols]
    
    if missing:
        st.error(f"❌ 识别失败：转档后的 Excel 缺少列：{', '.join(missing)}")
        st.write("🔍 我看到的列名有：", list(df.columns))
        return pd.DataFrame(), False

    # 【严谨步骤 3】提取数据并强制数值化 (解决 arg must be a list 报错)
    clean_df = pd.DataFrame()
    clean_df['用户名'] = df[actual_cols['用户名']].astype(str)
    
    for col in ['个人实际销量', '投注单数', '个人游戏盈亏', 'RTP']:
        # 强制转换为数字，无法转换的变 0
        clean_df[col] = pd.to_numeric(df[actual_cols[col]], errors='coerce').fillna(0)

    # 【严谨步骤 4】汇总计算
    grouped = clean_df.groupby('用户名').agg({
        '个人实际销量': 'sum',
        '投注单数': 'sum',
        '个人游戏盈亏': 'sum',
        'RTP': 'mean'
    }).reset_index()

    # 执行 4 项标记
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

# 4. 界面
st.title("📊 异常用户自动筛查系统")
st.info("💡 请上传【另存为】后的 .xlsx 文件，系统会自动识别并汇总。")

uploaded_file = st.file_uploader("请上传 Excel (.xlsx)", type=["xlsx"])

if uploaded_file:
    try:
        # 读取文件
        data = pd.read_excel(uploaded_file)
        
        # 运行审计
        res_all, success = run_audit(data)
        
        if success:
            res_flagged = res_all[res_all['异常标记'].notna()]
            
            if not res_flagged.empty:
                st.warning(f"✅ 扫描完成：发现 {len(res_flagged)} 个异常账户")
                st.dataframe(res_flagged, use_container_width=True)
                csv = res_flagged.to_csv(index=False).encode('utf-8-sig')
                st.download_button("📥 导出审计结果", csv, "report.csv", "text/csv")
            else:
                st.success("✅ 扫描完毕，未发现符合条件的异常用户。")
                with st.expander("查看已汇总的所有数据预览"):
                    st.dataframe(res_all)
                
    except Exception as e:
        st.error(f"致命错误：{e
