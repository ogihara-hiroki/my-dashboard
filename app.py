import streamlit as st
import requests, base64, pandas as pd
import plotly.express as px
from datetime import datetime, date, timedelta
import urllib3

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

# --- 2. Asana予定取得 (見積時間の取得を強化) ---
def get_asana_plan(target_date_val):
    try:
        url = "https://app.asana.com/api/1.0/tasks"
        headers = {"Authorization": f"Bearer {ASANA_TOKEN}"}
        # 全取得のために条件を緩和
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
                
                # カスタムフィールドから見積時間を探す
                estimate = 0
                for cf in t.get('custom_fields', []):
                    field_name = cf.get('name', '')
                    # フィールド名に以下のキーワードが含まれているかチェック
                    if any(key in field_name for key in ['見積', '予定', 'Estimate', '期待', '工数']):
                        # 数値(number_value)があれば取得
                        estimate = cf.get('number_value') or 0
                        break
                
                plan_data.append({"作業内容": raw_name, "表示名": display_name, "予定(h)": float(estimate)})
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
        
        entries = []
        for item in raw_data:
            desc = item.get('description') or "名称未設定"
            dur = item.get('duration', 0)
            if dur > 0:
                entries.append({'作業内容': desc, '実績(h)': round(dur / 3600, 1)})
        
        df = pd.DataFrame(entries).groupby('作業内容')['実績(h)'].sum().reset_index()
        return df
    except: return None

# --- UIメイン ---
st.sidebar.header("🗓️ PDCA設定")
target_date = st.sidebar.date_input("基準日:", date.today())

st.title(f"🚀 Work PDCA Dashboard")

df_plan = get_asana_plan(target_date)
df_do = get_toggl_do(target_date)

st.header("🔍 予実分析 (Plan vs Do)")

df_merge = None
if df_plan is not None and df_do is not None:
    df_merge = pd.merge(df_plan, df_do, on="作業内容", how="outer").fillna(0)
    df_merge['表示名'] = df_merge.apply(
        lambda r: r['表示名'] if isinstance(r['表示名'], str) else "⚡ " + str(r['作業内容']), axis=1
    )
elif df_plan is not None:
    df_merge = df_plan.copy()
    df_merge["実績(h)"] = 0.0
elif df_do is not None:
    df_merge = df_do.copy()
    df_merge["予定(h)"] = 0.0
    df_merge["表示名"] = "⚡ " + df_merge["作業内容"]

if df_merge is not None:
    # 差分計算
    df_merge['差分(h)'] = (df_merge['実績(h)'] - df_merge['予定(h)']).round(1)
    # 予定があるものを優先し、実績順に並べる
    df_merge = df_merge.sort_values(['予定(h)', '実績(h)'], ascending=False)
    
    c1, c2 = st.columns([2, 1])
    with c1:
        fig = px.bar(df_merge, x="表示名", y=["予定(h)", "実績(h)"], 
                     barmode="group", text_auto='.1f',
                     category_orders={"表示名": df_merge["表示名"].tolist()})
        st.plotly_chart(fig, use_container_width=True)
        st.metric(label="本日の総実績", value=f"{df_merge['実績(h)'].sum():.1f} h")
        
    with c2:
        st.write("📊 予実詳細（h）")
        st.table(df_merge[['表示名', '予定(h)', '実績(h)', '差分(h)']].style.format("{:.1f}", subset=["予定(h)", "実績(h)", "差分(h)"]))
        st.markdown(f"**予定合計: {df_merge['予定(h)'].sum():.1f} h / 実績合計: {df_merge['実績(h)'].sum():.1f} h**")
else:
    st.info(f"💡 {target_date} の予定（Asana）または実績（Toggl）が見つかりません。")
