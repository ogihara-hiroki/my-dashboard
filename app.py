import streamlit as st
import requests, base64, pandas as pd
import plotly.express as px
from datetime import datetime, timedelta

# --- 設定（あなたの情報を入れてください） ---
ASANA_TOKEN = '2/1202260582260384/1213620305884302:3b2113ab646543840f0e4192076e7c08'
ASANA_WORKSPACE_ID = '1200313649553191'
TOGGL_TOKEN = '2236bb0c27861b351b5546732733043e'
TOGGL_WORKSPACE_ID = '8358873'

st.set_page_config(page_title="Work Analysis Dashboard", layout="wide")
st.title("📊 業務パフォーマンス・ダッシュボード")

# サイドバーで期間選択
days = st.sidebar.slider("分析期間（過去何日間）", 1, 30, 7)
start_date_str = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d')

if st.sidebar.button("データを更新"):
    st.cache_data.clear()

# データ取得処理
@st.cache_data(ttl=600)
def get_data(days_val):
    auth = base64.b64encode(f"{TOGGL_TOKEN}:api_token".encode()).decode()
    t_url = f"https://api.track.toggl.com/reports/api/v3/workspace/{TOGGL_WORKSPACE_ID}/summary/time_entries"
    t_res = requests.post(t_url, headers={'Authorization': f'Basic {auth}', 'Content-Type': 'application/json'}, 
                          json={"start_date": start_date_str, "end_date": datetime.now().strftime('%Y-%m-%d')}).json()
    
    toggl_actuals = {}
    if 'groups' in t_res:
        for group in t_res['groups']:
            for sub in group.get('sub_groups', []):
                title = sub.get('title') or "名称未設定"
                sec = sub.get('rates', [{}])[0].get('billable_seconds', 0) if sub.get('rates') else 0
                toggl_actuals[title] = toggl_actuals.get(title, 0) + (sec / 3600)

    a_url = f"https://app.asana.com/api/1.0/tasks?workspace={ASANA_WORKSPACE_ID}&assignee=me&opt_fields=name,custom_fields"
    a_res = requests.get(a_url, headers={'Authorization': f'Bearer {ASANA_TOKEN}'}).json()
    asana_plans = {t['name']: next((float(cf.get('number_value') or 0) for cf in t.get('custom_fields', []) if "見積" in cf['name']), 0) for t in a_res.get('data', [])}

    results = []
    for name, actual in toggl_actuals.items():
        if actual < 0.05: continue
        plan = asana_plans.get(name, 0)
        results.append({"タスク名": name, "予定(h)": plan, "実績(h)": round(actual, 1), "乖離(h)": round(actual - plan, 1) if plan > 0 else 0})
    return pd.DataFrame(results)

df = get_data(days)

if not df.empty:
    # サマリーカード
    col1, col2, col3 = st.columns(3)
    col1.metric("総実働時間", f"{df['実績(h)'].sum():.1f} h")
    col2.metric("タスク数", f"{len(df)} 件")
    col3.metric("最大投下タスク", df.sort_values("実績(h)", ascending=False).iloc[0]["タスク名"])

    # グラフ
    fig = px.bar(df.sort_values("実績(h)"), x="実績(h)", y="タスク名", orientation='h', 
                 title="タスク別実績時間", color="実績(h)", color_continuous_scale="Viridis")
    st.plotly_chart(fig, use_container_width=True)

    # テーブル
    st.write("### 詳細データ")
    st.dataframe(df.style.highlight_max(axis=0, subset=['実績(h)'], color='#f8d7da'))
else:
    st.warning("指定期間内にデータが見つかりませんでした。")
