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

# 3. 核心审计函数
def run_audit(df):
    try:
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
            st.error(f"❌ 列名匹配失败，请检查 Excel 表头。")
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
        return grouped[grouped['原因'].notna()].copy()
    except Exception as e:
        st.error(f"审计出错：{e}")
        return None

# 4. 界面显示层
st.title("📊 抓")

file = st.file_uploader("📂 上传 Excel 文件", type=["xlsx"])

if file:
    if "ghost_res" not in st.session_state or st.button("🔄 重新扫描文件"):
        try:
            raw = pd.read_excel(file)
            result = run_audit(raw)
            if result is not None:
                st.session_state.ghost_res = result
                st.session_state.ghost_read = set()
        except Exception as e:
            st.error(f"加载文件失败：{e}")

    res = st.session_state.get("ghost_res")

    if res is not None and not res.empty:
        # 排序功能
        st.write("---")
        sort_col, sort_order = st.columns([2, 1])
        sort_by = sort_col.selectbox("选择排序字段", ["默认 (账号)", "个人实际销量", "个人游戏盈亏", "RTP", "投注单数"])
        order = sort_order.selectbox("排序方式", ["从大到小", "从小到大"])
        
        mapping = {"默认 (账号)": "用户名", "个人实际销量": "个人实际销量", "个人游戏盈亏": "个人游戏盈亏", "RTP": "RTP", "投注单数": "投注单数"}
        res = res.sort_values(by=mapping[sort_by], ascending=(order == "从小到大"))

        done_num = len(st.session_state.ghost_read)
        st.warning(f"🎯 发现 {len(res)} 个异常账号 | 已核查: {done_num}")
        
        st.write("---")
        h_cols = st.columns([1, 2, 3, 2, 1, 2, 2])
        headers = ["确认", "用户名", "原因", "销量", "单数", "盈亏", "RTP"]
        for col, h in zip(h_cols, headers): col.write(f"**{h}**")

        for i, row in res.iterrows():
            u = row['用户名']
            is_read = u in st.session_state.ghost_read
            
            with st.container():
                r_cols = st.columns([1, 2, 3, 2, 1, 2, 2])
                if r_cols[0].checkbox(" ", key=f"k_{u}_{i}", value=is_read):
                    st.session_state.ghost_read.add(u)
                    is_read = True
                else:
                    st.session_state.ghost_read.discard(u)
                    is_read = False

                color = "#aaaaaa" if is_read else "#000000"
                decoration = "line-through" if is_read else "none"
                style = f"style='color:{color}; text-decoration:{decoration}; margin:0; padding:0;'"
                
                r_cols[1].markdown(f"<p {style}>{u}</p>", unsafe_allow_html=True)
                r_cols[2].markdown(f"<p {style}>{row['原因']}</p>", unsafe_allow_html=True)
                r_cols[3].markdown(f"<p {style}>{row['个人实际销量']:.3f}</p>", unsafe_allow_html=True)
                r_cols[4].markdown(f"<p {style}>{int(row['投注单数'])}</p>", unsafe_allow_html=True)
                r_cols[5].markdown(f"<p {style}>{row['个人游戏盈亏']:.3f}</p>", unsafe_allow_html=True)
                r_cols[6].markdown(f"<p {style}>{row['RTP']:.3f}</p>", unsafe_allow_html=True)

        st.write("---")
        # 导出 CSV 逻辑
        csv_data = res.to_csv(index=False).encode('utf-8-sig')
        st.download_button("📥 导出排序后的报告", csv_data, "ghost_report.csv", "text/csv")
    
    elif res is not None:
        st.success("✅ 扫描完毕，未发现异常。")
