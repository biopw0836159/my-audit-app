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

# 3. 核心审计函数 (严谨逻辑 + 强力容错)
def run_audit(df):
    try:
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
            st.error(f"❌ 识别失败，识别到的列有：{list(df.columns)}")
            return None

        # 数据清洗：强制数值化并处理空值
        clean_df = pd.DataFrame()
        clean_df['用户名'] = df[actual_cols['用户名']].astype(str)
        for col in ['个人实际销量', '投注单数', '个人游戏盈亏', 'RTP']:
            clean_df[col] = pd.to_numeric(df[actual_cols[col]], errors='coerce').fillna(0)

        # 核心加权算法
        clean_df['返还额'] = clean_df['个人实际销量'] * clean_df['RTP']

        # 汇总数据
        grouped = clean_df.groupby('用户名').agg({
            '个人实际销量': 'sum', 
            '投注单数': 'sum', 
            '个人游戏盈亏': 'sum', 
            '返还额': 'sum'
        }).reset_index()

        # 计算加权 RTP
        grouped['RTP'] = grouped.apply(lambda x: x['返还额'] / x['个人实际销量'] if x['个人实际销量'] > 0 else 0, axis=1)

        # 异常规则
        def get_labels(row):
            m = []
            v, c, r, p = row['个人实际销量'], row['投注单数'], row['RTP'], row['个人游戏盈亏']
            if 1000 <= v <= 2000 and c < 12: m.append("疑似刷人数")
            if v > 500000 and 0.995 <= r <= 1: m.append("疑似刷量")
            if p > 100000: m.append("盈利大会员")
            if v > 2000 and c < 10: m.append("疑似对刷")
            return " | ".join(m) if m else None

        grouped['原因'] = grouped.apply(get_labels, axis=1)
        
        # 只保留异常用户
        flagged = grouped[grouped['原因'].notna()].copy()
        
        # 预先处理显示用的 3 位小数
        flagged['销量_显示'] = flagged['个人实际销量'].apply(lambda x: f"{x:.3f}")
        flagged['盈亏_显示'] = flagged['个人游戏盈亏'].apply(lambda x: f"{x:.3f}")
        flagged['RTP_显示'] = flagged['RTP'].apply(lambda x: f"{x:.3f}")
        flagged['单数_显示'] = flagged['投注单数'].astype(int)
        
        return flagged
    except Exception as e:
        st.error(f"⚠️ 审计计算时出错：{e}")
        return None

# 4. 界面显示层
st.title("📊 抓到嘿咕 (V9 终极稳定版)")

file = st.file_uploader("📂 请上传 Excel 文件", type=["xlsx"])

if file:
    # 状态控制：确保刷新和切换不丢失数据
    if "ghost_res" not in st.session_state or st.button("🔄 重新跑数据"):
        try:
            raw = pd.read_excel(file)
            result = run_audit(raw)
            if result is not None:
                st.session_state.ghost_res = result
                st.session_state.ghost_read = set()
        except Exception as e:
            st.error(f"❌ 读取 Excel 失败：{e}")

    res = st.session_state.get("ghost_res")

    if res is not None and not res.empty:
        done_num = len(st.session_state.ghost_read)
        st.warning(f"🎯 发现 {len(res)} 个异常账号 | 已处理: {done_num}")
        
        st.write("---")
        # 1. 表头 (固定 7 列)
        h_cols = st.columns([1, 2, 3, 2, 1, 2, 2])
        headers = ["确认", "用户名", "原因", "销量", "单数", "盈亏", "RTP"]
        for col, h in zip(h_cols, headers):
            col.write(f"**{h}**")

        # 2. 数据行
        for i, row in res.iterrows():
            u = row['用户名']
            is_read = u in st.session_state.ghost_read
            
            with st.container():
                r_cols = st.columns([1, 2, 3, 2, 1, 2, 2])
                
                # 第1列：勾选框
                if r_cols[0].checkbox(" ", key=f"k_{u}_{i}", value=is_read):
                    st.session_state.ghost_read.add(u)
                    is_read = True
                else:
                    st.session_state.ghost_read.discard(u)
                    is_read = False

                # 样式控制
                color = "#aaaaaa" if is_read else "#000000"
                decoration = "line-through" if is_read else "none"
                st_css = f"style='color:{color}; text-decoration:{decoration}; margin:0; padding:0;'"
                
                # 后面 6 列：内容渲染
                r_cols[1].markdown(f"<p {st_css}>{u}</p>", unsafe_allow_html=True)
                r_cols[2].markdown(f"<p {st_css}>{row['原因']}</p>", unsafe_allow_html=True)
                r_cols[3].markdown(f"<p {st_css}>{row['销量_显示']}</p>", unsafe_allow_html=True)
                r_cols[4].markdown(f"<p {st_css}>{row['单数_显示']}</p>", unsafe_allow_html=True)
                r_cols[5].markdown(f"<p {st_css}>{row['盈亏_显示']}</p>", unsafe_allow_html=True)
                r_cols[6].markdown(f"<p {st_css}>{row['RTP_显示']}</p>", unsafe_allow_html=True)

        st.write("---")
        # 导出按钮
        csv = res.drop(columns=['销量_显示','盈亏_显示','RTP_显示','单数_显示']).to_csv(index=False).encode('utf-8-sig')
        st.download_button("📥 导出分析报告", csv, "ghost_report_v9.csv", "text/csv")
    
    elif res is not None:
        st.success("✅ 扫描完毕，未发现异常账号。")
