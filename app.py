import streamlit as st
import requests
import sqlite3
import re
from deep_translator import GoogleTranslator

# --- 页面配置 ---
st.set_page_config(page_title="化学计算器Pro", page_icon="🧪", layout="centered")

# --- 深度定制 CSS (移动端友好型) ---
st.markdown("""
    <style>
    /* 全局背景 */
    .stApp {
        background-color: #ffffff;
        background-image: radial-gradient(#e5e7eb 1px, transparent 1px);
        background-size: 24px 24px;
    }

    header {visibility: hidden;}
    
    /* 标题排版 */
    .hero-container {
        text-align: center;
        padding: 30px 0 10px 0;
    }
    .title-main {
        font-size: 2.8rem !important;
        font-weight: 800;
        color: #1f2937;
        margin-bottom: 0;
        letter-spacing: -1px;
    }
    .title-sub {
        color: #3b82f6;
    }
    .description {
        color: #6b7280;
        font-size: 1rem;
        margin-bottom: 20px;
    }

    /* 按钮大尺寸化，适合手机点击 */
    .stButton>button {
        width: 100% !important;
        border-radius: 12px !important;
        height: 3.5rem !important;
        font-size: 1.1rem !important;
        font-weight: 700 !important;
        border: none !important;
        transition: transform 0.1s;
    }
    .stButton>button:active {
        transform: scale(0.98);
    }

    /* 搜索按钮颜色 */
    div.stButton > button:first-child {
        background-color: #3b82f6 !important;
        color: white !important;
    }

    /* 模拟标签 Chips */
    .chip-container {
        display: flex;
        justify-content: center;
        gap: 8px;
        margin: 15px 0;
        flex-wrap: wrap;
    }
    .chip {
        background: #f3f4f6;
        color: #6b7280;
        padding: 5px 12px;
        border-radius: 20px;
        font-size: 0.8rem;
        border: 1px solid #e5e7eb;
    }

    /* 计算结果大卡片 (移除气球后的核心视觉) */
    .result-section {
        background: #111827;
        color: #ffffff;
        padding: 30px;
        border-radius: 20px;
        text-align: center;
        margin-top: 25px;
        border: 2px solid #3b82f6;
    }
    .result-val {
        font-size: 3.5rem;
        font-weight: 800;
        color: #3b82f6;
        line-height: 1.1;
    }

    /* 历史记录卡片 */
    .history-card {
        background: white;
        border: 1px solid #e5e7eb;
        padding: 12px;
        border-radius: 12px;
        margin-bottom: 10px;
    }
    </style>
""", unsafe_allow_html=True)

# --- 核心逻辑与数据库修复 ---
def init_db():
    conn = sqlite3.connect('chem_cache.db', check_same_thread=False)
    c = conn.cursor()
    # 自动检查数据库结构，解决“无此类列: cas”的问题
    try:
        c.execute("SELECT cas FROM chemicals LIMIT 1")
    except sqlite3.OperationalError:
        # 如果报错，说明表结构旧了，直接删掉重建（简单粗暴解决列缺失）
        c.execute("DROP TABLE IF EXISTS chemicals")
    
    c.execute('''CREATE TABLE IF NOT EXISTS chemicals
                 (query_name TEXT PRIMARY KEY, en_name TEXT, mw REAL, formula TEXT, iupac_name TEXT, cas TEXT)''')
    conn.commit()
    return conn

def get_history():
    conn = init_db()
    c = conn.cursor()
    c.execute("SELECT query_name, formula FROM chemicals ORDER BY rowid DESC LIMIT 3")
    return c.fetchall()

def free_translate(text):
    if any('\u4e00' <= char <= '\u9fff' for char in text):
        try: return GoogleTranslator(source='auto', target='en').translate(text)
        except: return text
    return text

def fetch_from_pubchem(identifier):
    try:
        url = f"https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/name/{identifier}/property/MolecularWeight,MolecularFormula,IUPACName/JSON"
        r = requests.get(url, timeout=10)
        if r.status_code == 200:
            return r.json()['PropertyTable']['Properties'][0]
    except: return None

# --- UI 布局 ---

# 1. 头部
st.markdown('''
    <div class="hero-container">
        <h1 class="title-main">化学<span class="title-sub">计算器</span></h1>
        <p class="description">输入姓名、公式或CAS编号，点击下方按钮开始。</p>
    </div>
''', unsafe_allow_html=True)

# 2. 输入与搜索（手机端优化：输入框+大按钮）
query = st.text_input("搜索框", label_visibility="collapsed", placeholder="输入化学名(如:阿司匹林)...")

st.markdown('''
    <div class="chip-container">
        <span class="chip">CAS号</span> <span class="chip">IUPAC名称</span> <span class="chip">分子式</span>
    </div>
''', unsafe_allow_html=True)

# 手机端核心搜索按钮
search_trigger = st.button("🚀 立即分析物质信息")

# 3. 核心业务逻辑
if search_trigger and query:
    conn = init_db()
    with st.spinner("正在检索全球数据库..."):
        # 尝试翻译（因为我们要增强鲁棒性，默认开启AI转译逻辑）
        en_query = free_translate(query)
        res = fetch_from_pubchem(en_query)
        
        if res:
            mw = res['MolecularWeight']
            formula = res['MolecularFormula']
            iupac = res.get('IUPACName', 'N/A')
            
            # 存入数据库
            c = conn.cursor()
            c.execute("INSERT OR REPLACE INTO chemicals (query_name, mw, formula, iupac_name) VALUES (?, ?, ?, ?)", 
                      (query, mw, formula, iupac))
            conn.commit()
            
            # 存储在 session 状态中，防止刷新丢失
            st.session_state.current_item = {"name": query, "mw": mw, "formula": formula, "iupac": iupac}
        else:
            st.error("未能匹配该物质。建议尝试英文名或CAS号。")

# 4. 结果展示与计算
if 'current_item' in st.session_state:
    item = st.session_state.current_item
    st.write("---")
    
    # 物质信息卡片
    st.markdown(f"### 📦 {item['name']}")
    c1, c2 = st.columns(2)
    c1.metric("化学式", item['formula'])
    c2.metric("分子量", f"{item['mw']} g/mol")
    st.caption(f"**IUPAC全称:** {item['iupac']}")

    # 计算模块（大按钮触发）
    st.write("#### ⚖️ 质量称重计算")
    calc_c1, calc_c2 = st.columns(2)
    m_val = calc_c1.number_input("物质的量 (mol)", min_value=0.0, step=0.001, format="%.4f")
    p_val = calc_c2.number_input("纯度 (%)", value=100.0)
    
    # 单位选择
    u_val = st.radio("选择输出单位", ["g", "mg", "kg"], horizontal=True)
    
    calc_trigger = st.button("🧮 执行质量换算")
    
    if calc_trigger:
        if m_val > 0:
            res_g = (m_val * float(item['mw'])) / (p_val/100)
            if u_val == "mg": final_m, unit = res_g * 1000, "mg"
            elif u_val == "kg": final_m, unit = res_g / 1000, "kg"
            else: final_m, unit = res_g, "g"
            
            # 结果显示（去掉了气球，使用了醒目的深色大卡片）
            st.markdown(f'''
                <div class="result-section">
                    <div style="font-size: 1.1rem; opacity: 0.8; margin-bottom:10px;">应称取质量 ({unit})</div>
                    <div class="result-val">{final_m:.4f}</div>
                    <div style="margin-top:15px; font-size:0.8rem; opacity:0.6;">计算逻辑: ({m_val}mol × {item['mw']}g/mol) / {p_val}%</div>
                </div>
            ''', unsafe_allow_html=True)
        else:
            st.warning("请输入有效的物质的量")

# 5. 近期检索 (底部手机适配)
st.write("")
st.markdown("##### 🕒 最近查询记录")
history = get_history()
for h_item in history:
    st.markdown(f'''
        <div class="history-card">
            <span style="font-weight:600;">{h_item[0]}</span> 
            <span style="color:#9ca3af; font-size:0.8rem; margin-left:10px;">{h_item[1]}</span>
        </div>
    ''', unsafe_allow_html=True)