import streamlit as st
import requests, base64, pandas as pd
import plotly.express as px
from datetime import datetime, date, timedelta
import urllib3
import pytz
from streamlit_calendar import calendar

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# --- 0. 設定 ---
GITHUB_TOKEN = st.secrets["MY_GITHUB_TOKEN"]
REPO_NAME = 'ogihara-hiroki/my-dashboard'
STATUS_FILE = 'status.txt'
TOGGL_TOKEN = '2236bb0c27861b351b5546732733043e'
ASANA_TOKEN = '2/1202260582260384/1213620305884302:3b2113ab646543840f0e4192076e7c08'
ASANA_WORKSPACE_ID = '1200313649553191'

st.set_page_config(page_title="Work PDCA Dashboard", layout="wide")

# --- 1. データ取得関数 (単日用) ---
def get_asana_plan(target_date_val):
    try:
        url = "https://app.asana.com/api/1.0/tasks"
        headers = {"Authorization": f"Bearer {ASANA_TOKEN}"}
        params = {
            "workspace": ASANA_WORKSPACE_ID, "assignee": "me",
            "opt_fields": "name,due_on,custom_fields,completed",
            "completed_since": "2024-01-01T00:00:00.000Z"
        }
        res = requests.get(url, headers=headers, params=params)
        if res.status_code != 200: return None
        tasks = res.json().get('data', [])
        plan_data = []
        t_str = target_date_val.strftime('%Y-%m-%d')
        for t in tasks:
            if t.get('due_on') == t_str:
                est = 0
                memo = ""
                for cf in t.get('custom_fields', []):
                    if any(k in cf.get('name', '') for k in ['見積', '予定', 'Estimate']): est = cf.get('number_value') or 0
                    if any(k in cf.get('name', '') for k in ['対策', 'メモ']): memo = cf.get('text_value') or ""
                plan_data.append({"作業内容": t['name'], "表示名": ("✅ " if t.get('completed') else "⏳ ") + t['name'], "予定(h)": float(est), "次回の対策": memo})
        return pd.DataFrame(plan_data) if plan_data else None
    except: return None

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
        raw = res.json()
        if not raw: return None
        entries = [{'作業内容': i.get('description') or "未設定", '実績(h)': round(i.get('duration', 0) / 3600, 1)} for i in raw if i.get('duration', 0) > 0]
        return pd.DataFrame(entries).groupby('作業内容')['実績(h)'].sum().reset_index()
    except: return None

# --- 2. 高速一括取得関数 (週次/カレンダー用・実績判定修正済み) ---
def get_bulk_pdca_data(start_d, end_d):
    p_map, do_map = {}, {}
    s_str = start_d.strftime('%Y-%m-%d')
    e_str = end_d.strftime('%Y-%m-%d')
    
    # Asana一括 (取得範囲を今日の前後に限定)
    try:
        headers = {"Authorization": f"Bearer {ASANA_TOKEN}"}
        params = {"workspace": ASANA_WORKSPACE_ID, "assignee": "me", "opt_fields": "name,due_on,custom_fields", "completed_since": s_str + "T00:00:00Z"}
        res = requests.get("https://app.asana.com/api/1.0/tasks", headers=headers, params=params)
        if res.status_code == 200:
            for t in res.json().get('data', []):
                due = t.get('due_on')
                if due and s_str <= due <= e_str:
                    est = 0
                    for cf in t.get('custom_fields', []):
                        if any(k in cf.get('name', '') for k in ['見積', '予定', 'Estimate']): est += (cf.get('number_value') or 0)
                    p_map[due] = p_map.get(due, 0) + est
    except: pass

    # Toggl一括 (日付の判定を強化)
    try:
        s_utc = (datetime.combine(start_d, datetime.min.time()) - timedelta(hours=9)).strftime('%Y-%m-%dT%H:%M:%SZ')
        e_utc = (datetime.combine(end_d, datetime.max.time()) - timedelta(hours=9)).strftime('%Y-%m-%dT%H:%M:%SZ')
        auth = base64.b64encode(f"{TOGGL_TOKEN}:api_token".encode()).decode()
        res = requests.get("https://api.track.toggl.com/api/v9/me/time_entries", headers={"Authorization": f"Basic {auth}"}, params={"start_date": s_utc, "end_date": e_utc})
        if res.status_code == 200:
            for i in res.json():
                dur = i.get('duration', 0)
                if dur > 0:
                    # 日本時間に変換して日付を取得
                    start_dt = datetime.fromisoformat(i['start'].replace('Z', '+00:00')).astimezone(pytz.timezone('Asia/Tokyo'))
                    d_jst = start_dt.strftime('%Y-%m-%d')
                    if s_str <= d_jst <= e_str:
                        do_map[d_jst] = do_map.get(d_jst, 0) + (dur / 3600)
    except: pass
    return p_map, do_map

# --- 3. UIメイン ---
jst = pytz.timezone('Asia/Tokyo')
today_jst = datetime.now(jst).date()

st.sidebar.header("🗓️ PDCA設定")
target_date = st.sidebar.date_input("基準日:", value=today_jst)

tab1, tab2, tab3 = st.tabs(["🎯 本日のPDCA", "📊 週次計画", "📅 カレンダー"])

# --- Tab 1: 本日のPDCA ---
with tab1:
    df_p = get_asana_plan(target_date)
    df_d = get_toggl_do(target_date)
    df_m = None
    if df_p is not None and df_d is not None:
        df_m = pd.merge(df_p, df_d, on="作業内容", how="outer").fillna(0)
        df_m['表示名'] = df_m.apply(lambda r: r['表示名'] if isinstance(r['表示名'], str) else "⚡ " + str(r['作業内容']), axis=1)
    elif df_p is not None:
        df_m = df_p.copy(); df_m["実績(h)"] = 0.0
    elif df_d is not None:
        df_m = df_d.copy(); df_m["予定(h)"] = 0.0; df_m["表示名"] = "⚡ " + df_m["作業内容"]; df_m["次回の対策"] = ""

    if df_m is not None:
        tp, td = df_m['予定(h)'].sum(), df_m['実績(h)'].sum()
        p_do = df_m[~df_m['表示名'].str.contains("⚡")]['実績(h)'].sum()
        u_do = df_m[df_m['表示名'].str.contains("⚡")]['実績(h)'].sum()
        
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("総実績", f"{td:.1f}h")
        c2.metric("計画達成率", f"{(p_do/tp*100) if tp>0 else 0:.0f}%")
        c3.metric("飛び込み率", f"{(u_do/td*100) if td>0 else 0:.0f}%", delta=f"{u_do:.1f}h", delta_color="inverse")
        c4.metric("予定合計", f"{tp:.1f}h")
        
        df_m['差分(h)'] = (df_m['実績(h)'] - df_m['予定(h)']).round(1)
        df_m['短縮名'] = df_m['表示名'].apply(lambda x: x[:15]+"..." if len(x)>15 else x)
        df_m = df_m.sort_values(['予定(h)', '実績(h)'], ascending=False)
        
        col1, col2 = st.columns([1, 1])
        with col1:
            st.plotly_chart(px.bar(df_m, x="短縮名", y=["予定(h)", "実績(h)"], barmode="group", text_auto='.1f'), use_container_width=True)
            st.plotly_chart(px.pie(pd.DataFrame({"分類":["計画通り","飛び込み"],"時間":[p_do,u_do]}), values="時間", names="分類", hole=0.4), use_container_width=True)
        with col2:
            st.write("📋 詳細")
            st.table(df_m[['表示名', '予定(h)', '実績(h)', '差分(h)', '次回の対策']].style.format("{:.1f}", subset=["予定(h)", "実績(h)", "差分(h)"]))
    else: st.info("データがありません")

# --- Tab 2: 週次計画 ---
with tab2:
    st.subheader("🗓️ 今週の予定負荷（Asana）")
    s_week = today_jst - timedelta(days=today_jst.weekday())
    e_week = s_week + timedelta(days=6)
    with st.spinner('週次データ取得中...'):
        p_map, _ = get_bulk_pdca_data(s_week, e_week)
        weekly_list = []
        for i in range(7):
            d_jst = s_week + timedelta(days=i)
            d_str = d_jst.strftime('%Y-%m-%d')
            # 土日は除外してグラフ化
            if d_jst.weekday() < 5:
                weekly_list.append({"日付": d_str[5:], "予定(h)": p_map.get(d_str, 0)})
        st.plotly_chart(px.line(pd.DataFrame(weekly_list), x="日付", y="予定(h)", text="予定(h)", markers=True), use_container_width=True)

# --- Tab 3: カレンダー ---
with tab3:
    st.subheader("📅 PDCAカレンダー (平日限定・高速版)")
    s_cal = today_jst - timedelta(days=today_jst.day + 7)
    e_cal = today_jst + timedelta(days=31)
    
    with st.spinner('データを同期中...'):
        pm, dm = get_bulk_pdca_data(s_cal, e_cal)
    
    events = []
    for d, v in pm.items():
        if v > 0: events.append({"title": f"P: {v:.1f}h", "start": d, "color": "#3B82F6", "allDay": True})
    for d, v in dm.items():
        if v > 0: events.append({"title": f"D: {v:.1f}h", "start": d, "color": "#10B981" if v <= 8 else "#EF4444", "allDay": True})
    
    cal_options = {
        "initialView": "dayGridMonth",
        "weekends": False,
        "headerToolbar": {"left": "prev,next today", "center": "title", "right": "dayGridMonth,dayGridWeek"},
    }
    calendar(events=events, options=cal_options)
