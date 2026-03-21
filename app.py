import streamlit as st
import pandas as pd
import io

# 1. 页面配置
st.set_page_config(page_title="抓鬼轻松版", layout="wide")

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
    # 清理列名
    df.columns = [str(c).strip().replace('\n', '').replace('\r', '') for c in df.columns]
    
    # 名目映射表
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
        return pd.DataFrame(), False

    # 数据预处理
    clean_df = pd.DataFrame()
    clean_df['用户名'] = df[actual_cols['用户名']].astype(str)
    
    for col in ['个人实际销量', '投注单数', '个人游戏盈亏', 'RTP']:
        clean_df[col] = pd.to_numeric(df[actual_cols[col]], errors='coerce').fillna(0)

    # 加权 RTP 算法
    clean_df['返还额'] = clean_df['个人实际销量'] * clean_df['RTP']

    # 汇总
    grouped = clean_df.groupby('用户名').agg({
        '个人实际销量': 'sum',
        '投注单数': 'sum',
        '个人游戏盈亏': 'sum',
        '返还额': 'sum'
    }).reset_index()

    # 计算最终加权 RTP
    grouped['RTP'] = grouped.apply(
        lambda x: x['返还额'] / x['个人实际销量'] if x['个人实际销量'] > 0 else 0, 
        axis=1
    )

    # 异常标记
    def get_labels(row):
        m = []
        v, c, r, p = row['个人实际销量'], row['投注单数'], row['RTP'], row['个人游戏盈亏']
        if 1000 <= v <= 2000 and c < 12: m.append("疑似刷人数")
        if v > 500000 and 0.995 <= r <= 1: m.append("疑似刷量")
        if p > 100000: m.append("盈利大会员")
        if v > 2000 and c < 10: m.append("疑似对刷")
        return " | ".join(m) if m else None

    grouped['异常标记'] = grouped.apply(get_labels, axis=1)
    
    final_display = grouped.drop(columns=['返还额'])
    # 调整顺序：用户名和标记放在最前面，方便查看和复制
    cols = ['用户名', '异常标记', '个人实际销量', '投注单数', '个人游戏盈亏', 'RTP']
    return final_display[cols], True

# 4. 界面
st.title("📊 抓到爆炸")

uploaded_file = st.file_uploader("上传另存为的 .xlsx 文件", type=["xlsx"])

if uploaded_file:
    try:
        data = pd.read_excel(uploaded_file)
        if data is not None:
            res_all, success = run_audit(data)
            if success:
                res_flagged = res_all[res_all['异常标记'].notna()]
                
                if not res_flagged.empty:
                    st.warning(f"✅ 发现 {len(res_flagged)} 个异常账户")
                    
                    # --- 新增：快速复制区 ---
                    with st.expander("📋 点击展开：待查用户名列表（方便快速复制）"):
                        user_list_str = "\n".join(res_flagged['用户名'].tolist())
                        st.text_area("直接选中下方文字复制，或点击右上角图标全选复制：", 
                                     value=user_list_str, height=200)
                    
                    # --- 数据表格 ---
                    st.write("### 详细审计报表")
                    st.info("💡 技巧：双击下方表格中的【用户名】单元格即可直接复制。")
                    st.dataframe(res_flagged, use_container_width=True, hide_index=True)
                    
                    csv = res_flagged.to_csv(index=False).encode('utf-8-sig')
                    st.download_button("📥 导出审计结果", csv, "report.csv", "text/csv")
                else:
                    st.success("✅ 扫描完毕，未发现符合条件的异常用户。")
                    with st.expander("查看所有汇总数据"):
                        st.dataframe(res_all, hide_index=True)
    except Exception as e:
        st.error(f"发生错误：{e}")
