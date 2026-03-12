import streamlit as st
import requests, base64, pandas as pd
from datetime import datetime, date, timedelta

# --- 設定（そのまま維持） ---
ASANA_TOKEN = '2/1202260582260384/1213620305884302:3b2113ab646543840f0e4192076e7c08'
ASANA_WORKSPACE_ID = '1200313649553191'
TOGGL_TOKEN = '2236bb0c27861b351b5546732733043e'
TOGGL_WORKSPACE_ID = '8358873'

st.set_page_config(page_title="Work Analysis", layout="wide")

# サイドバーで「日付」を直接選べるように変更
st.sidebar.header("表示設定")
target_date = st.sidebar.date_input("分析したい日を選択:", date.today())
mode = st.sidebar.radio("表示モード:", ["その日のみ", "その日までの7日間"])

# 取得範囲の計算
if mode == "その日のみ":
    start_dt = datetime.combine(target_date, datetime.min.time())
    end_dt = datetime.combine(target_date, datetime.max.time())
else:
    start_dt = datetime.combine(target_date - timedelta(days=6), datetime.min.time())
    end_dt = datetime.combine(target_date, datetime.max.time())

st.title(f"📊 業務分析: {start_dt.strftime('%m/%d')} ~ {end_dt.strftime('%m/%d')}")

# --- データ取得ロジック（以下はColab版をベースに最適化） ---
@st.cache_data(ttl=300)
def get_analysis_data(start_str, end_str):
    auth = base64.b64encode(f"{TOGGL_TOKEN}:api_token".encode()).decode()
    t_url = f"https://api.track.toggl.com/reports/api/v3/workspace/{TOGGL_WORKSPACE_ID}/summary/time_entries"
    t_res = requests.post(t_url, headers={'Authorization': f'Basic {auth}', 'Content-Type': 'application/json'}, 
                          json={"start_date": start_str, "end_date": end_str}).json()
    
    toggl_actuals = {}
    if 'groups' in t_res:
        for group in t_res['groups']:
            for sub in group.get('sub_groups', []):
                title = sub.get('title') or group.get('title') or "名称未設定"
                sec = sub.get('rates', [{}])[0].get('billable_seconds', 0) if sub.get('rates') else 0
                toggl_actuals[title] = toggl_actuals.get(title, 0) + (sec / 3600)

    # Asanaから予定取得
    a_url = f"https://app.asana.com/api/1.0/tasks?workspace={ASANA_WORKSPACE_ID}&assignee=me&opt_fields=name,custom_fields"
    a_res = requests.get(a_url, headers={'Authorization': f'Bearer {ASANA_TOKEN}'}).json()
    asana_plans = {t['name']: next((float(cf.get('number_value') or 0) for cf in t.get('custom_fields', []) if "見積" in cf['name']), 0) for t in a_res.get('data', [])}

    results = []
    for name, actual in toggl_actuals.items():
        if actual < 0.01: continue
        plan = asana_plans.get(name, 0)
        results.append({"タスク名": name, "予定(h)": plan, "実績(h)": round(actual, 2), "乖離(h)": round(actual - plan, 2) if plan > 0 else 0})
    return pd.DataFrame(results)

# 実行
df = get_analysis_data(start_dt.strftime('%Y-%m-%d'), end_dt.strftime('%Y-%m-%d'))

if not df.empty:
    df = df.sort_values("実績(h)", ascending=False)
    st.metric("この期間の総稼働時間", f"{df['実績(h)'].sum():.2f} 時間")
    st.bar_chart(df.set_index("タスク名")[["予定(h)", "実績(h)"]])
    st.dataframe(df, use_container_width=True)
else:
    st.info(f"{target_date} の記録は見つかりませんでした。")
