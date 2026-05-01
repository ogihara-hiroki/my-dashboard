import streamlit as st
import requests, base64, pandas as pd
import plotly.express as px
from datetime import datetime, date, timedelta
import urllib3
import pytz  # ★日本時間計算に必須

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# --- 設定 ---
GITHUB_TOKEN = st.secrets["MY_GITHUB_TOKEN"]
REPO_NAME = 'ogihara-hiroki/my-dashboard'
STATUS_FILE = 'status.txt'
TOGGL_TOKEN = '2236bb0c27861b351b5546732733043e'
ASANA_TOKEN = '2/1202260582260384/1213620305884302:3b2113ab646543840f0e4192076e7c08'
ASANA_WORKSPACE_ID = '1200313649553191'

st.set_page_config(page_title="Work PDCA Dashboard", layout="wide")

# --- 1. GitHubリモコン ---
def update_github_status(status_text):
    try:
        url = f"https://api.github.com/repos/{REPO_NAME}/contents/{STATUS_FILE}"
        headers = {"Authorization": f"token {GITHUB_TOKEN}"}
        res = requests.get(url, headers=headers).json()
        if 'sha' not in res: return
        sha = res['sha']
        content = base64.b64encode(status_text.encode('utf-8')).decode('utf-8')
        data = {"message": f"Switch to {status_text}", "content": content, "sha": sha}
        requests.put(url, headers=headers, json=data)
    except: pass

# --- 2. Asana予定取得 ---
def get_asana_plan(target_date_val):
    try:
        url = "https://app.asana.com/api/1.0/tasks"
        headers = {"Authorization": f"Bearer {ASANA_TOKEN}"}
        params = {
            "workspace": ASANA_WORKSPACE_ID, 
            "assignee": "me", 
            "opt_fields": "name,due_on,custom_fields,completed",
            "completed_since": "2024-01-01T00:00:00.000Z"
        }
        res = requests.get(url, headers=headers, params=params)
        if res.status_code != 200: return None
        
        tasks = res.json().get('data', [])
        plan_data = []
        target_date_str = target_date_val.strftime('%Y-%m-%d')
        
        for t in tasks:
            if t.get('due_on') == target_date_str:
                raw_name = t['name']
                mark = "✅ " if t.get('completed') else "⏳ "
                display_name = mark + raw_name
                
                estimate = 0
                act_memo = "" 
                for cf in t.get('custom_fields', []):
                    field_name = cf.get('name', '')
                    if any(key in field_name for key in ['見積', '予定', 'Estimate']):
                        estimate = cf.get('number_value') or 0
                    if any(key in field_name for key in ['対策', 'メモ']):
                        act_memo = cf.get('text_value') or ""
                
                plan_data.append({
                    "作業内容": raw_name, 
                    "表示名": display_name, 
                    "予定(h)": float(estimate),
                    "次回の対策": act_memo
                })
        return pd.DataFrame(plan_data) if plan_data else None
    except: return None

# --- 3. Toggl実績取得 ---
def get_toggl_do(target_date_val):
    try:
        start_dt = datetime.combine(target_date_val, datetime.min.time()) - timedelta(hours=9)
        end_dt = datetime.combine(target_date_val, datetime.max.time()) - timedelta(hours=9)
        url = "https://api.track.toggl.com/api/v9/me/time_entries"
        auth = base64.b64encode(f"{TOGGL_TOKEN}:api_token".encode()).decode()
        headers = {"Authorization": f"Basic {auth}", "Content-Type": "application/json"}
        params = {"start_date": start_dt.strftime('%Y-%m-%dT%H:%M:%SZ'), "end_date": end_dt.strftime('%Y-%m-%dT%H:%M:%SZ')}
        res = requests.get(url, headers=headers, params=params)
        if res.status_code != 200: return None
        raw_data = res.json()
        if not raw_data: return None
        entries = [{'作業内容': i.get('description') or "未設定", '実績(h)': round(i.get('duration', 0) / 3600, 1)} for i in raw_data if i.get('duration', 0) > 0]
        return pd.DataFrame(entries).groupby('作業内容')['実績(h)'].sum().reset_index()
    except: return None

# --- UIメイン ---
jst = pytz.timezone('Asia/Tokyo')
today_jst = datetime.now(jst).date()

st.sidebar.header("🗓️ PDCA設定")
target_date = st.sidebar.date_input("基準日:", value=today_jst)
st.title(f"🚀 Work PDCA Dashboard")

df_plan = get_asana_plan(target_date)
df_do = get_toggl_do(target_date)

st.header("🔍 予実分析 & 改善 (PDCA)")

# 1. データ結合
df_merge = None
if df_plan is not None and df_do is not None:
    df_merge = pd.merge(df_plan, df_do, on="作業内容", how="outer").fillna(0)
    df_merge['表示名'] = df_merge.apply(lambda r: r['表示名'] if isinstance(r['表示名'], str) else "⚡ " + str(r['作業内容']), axis=1)
    df_merge['次回の対策'] = df_merge['次回の対策'].replace(0, "")
elif df_plan is not None:
    df_merge = df_plan.copy()
    df_merge["実績(h)"] = 0.0
elif df_do is not None:
    df_merge = df_do.copy()
    df_merge["予定(h)"] = 0.0
    df_merge["表示名"] = "⚡ " + df_merge["作業内容"]
    df_merge["次回の対策"] = ""

# 2. サマリー表示 & 整形
if df_merge is not None:
    # 数値計算
    total_plan = df_merge['予定(h)'].sum()
    total_do = df_merge['実績(h)'].sum()
    planned_task_do = df_merge[~df_merge['表示名'].str.contains("⚡")]['実績(h)'].sum()
    urgent_do = df_merge[df_merge['表示名'].str.contains("⚡")]['実績(h)'].sum()
    
    achievement_rate = (planned_task_do / total_plan * 100) if total_plan > 0 else 0
    urgent_ratio = (urgent_do / total_do * 100) if total_do > 0 else 0

    # サマリー表示
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("総実績時間", f"{total_do:.1f} h")
    m2.metric("計画達成率", f"{achievement_rate:.0f} %")
    m3.metric("飛び込み比率", f"{urgent_ratio:.0f} %", delta=f"{urgent_do:.1f} h", delta_color="inverse")
    m4.metric("予定合計", f"{total_plan:.1f} h")

    st.divider()

    # データ整形
    df_merge['差分(h)'] = (df_merge['実績(h)'] - df_merge['予定(h)']).round(1)
    df_merge['グラフ用名称'] = df_merge['表示名'].apply(lambda x: x[:15] + "..." if len(x) > 15 else x)
    df_merge = df_merge.sort_values(['予定(h)', '実績(h)'], ascending=False)
    
    # 3. グラフと表
    c1, c2 = st.columns([1, 1])
    with c1:
        # 棒グラフ
        fig = px.bar(df_merge, x="グラフ用名称", y=["予定(h)", "実績(h)"], barmode="group", text_auto='.1f',
                     hover_data={"表示名": True, "グラフ用名称": False},
                     category_orders={"グラフ用名称": df_merge["グラフ用名称"].tolist()})
        fig.update_layout(title="作業別 予実比較")
        st.plotly_chart(fig, use_container_width=True)
        
        # 内訳円グラフ
        pie_df = pd.DataFrame({"分類": ["計画通り", "飛び込み"], "時間": [planned_task_do, urgent_do]})
        fig_pie = px.pie(pie_df, values="時間", names="分類", hole=0.4, 
                         color_discrete_map={"計画通り": "#1f77b4", "飛び込み": "#ff7f0e"})
        fig_pie.update_layout(title="今日の時間の使い道")
        st.plotly_chart(fig_pie, use_container_width=True)
        
    with c2:
        st.write("📋 PDCA詳細テーブル")
        st.table(df_merge[['表示名', '予定(h)', '実績(h)', '差分(h)', '次回の対策']].style.format("{:.1f}", subset=["予定(h)", "実績(h)", "差分(h)"]))
else:
    st.info("💡 データがありません。")
