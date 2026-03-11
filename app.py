import streamlit as st
import requests, base64, pandas as pd
import plotly.express as px
from datetime import datetime, timedelta

# --- 設定（画像の内容を反映済み） ---
ASANA_TOKEN = '2/1202260582260384/1213620305884302:3b2113ab646543840f0e4192076e7c08'
ASANA_WORKSPACE_ID = '1200313649553191'
TOGGL_TOKEN = '2236bb0c27861b351b5546732733043e'
TOGGL_WORKSPACE_ID = '8358873'

st.set_page_config(page_title="Work Analysis", layout="wide")
st.title("📊 業務パフォーマンス・ダッシュボード")

days = st.sidebar.slider("分析期間（過去何日間）", 1, 30, 7)
start_date_str = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d')

@st.cache_data(ttl=300)
def get_analysis_data(days_val):
    # Toggl実績取得（Colabで成功したロジック）
    auth = base64.b64encode(f"{TOGGL_TOKEN}:api_token".encode()).decode()
    t_url = f"https://api.track.toggl.com/reports/api/v3/workspace/{TOGGL_WORKSPACE_ID}/summary/time_entries"
    t_res = requests.post(t_url, headers={'Authorization': f'Basic {auth}', 'Content-Type': 'application/json'}, 
                          json={"start_date": start_date_str, "end_date": datetime.now().strftime('%Y-%m-%d')}).json()
    
    toggl_actuals = {}
    if 'groups' in t_res:
        for group in t_res['groups']:
            # sub_groupsを徹底的に探す
            sub_list = group.get('sub_groups', [])
            for sub in sub_list:
                title = sub.get('title') or group.get('title') or "名称未設定"
                sec = 0
                if 'rates' in sub and sub['rates']:
                    sec = sub['rates'][0].get('billable_seconds', 0)
                elif 'seconds' in sub:
                    sec = sub['seconds']
                toggl_actuals[title] = toggl_actuals.get(title, 0) + (sec / 3600)

    # Asanaタスク取得
    a_url = f"https://app.asana.com/api/1.0/tasks?workspace={ASANA_WORKSPACE_ID}&assignee=me&opt_fields=name,custom_fields"
    a_res = requests.get(a_url, headers={'Authorization': f'Bearer {ASANA_TOKEN}'}).json()
    
    asana_plans = {}
    for t in a_res.get('data', []):
        plan_h = 0
        for cf in t.get('custom_fields', []):
            if "見積" in cf['name']:
                plan_h = float(cf.get('number_value') or cf.get('display_value') or 0)
        asana_plans[t['name']] = plan_h

    # 突合
    results = []
    for name, actual in toggl_actuals.items():
        if actual < 0.05: continue
        plan = asana_plans.get(name, 0)
        results.append({
            "タスク名": name, 
            "予定(h)": plan if plan > 0 else 0, 
            "実績(h)": round(actual, 1), 
            "乖離(h)": round(actual - plan, 1) if plan > 0 else 0
        })
    return pd.DataFrame(results)

df = get_analysis_data(days)

if not df.empty:
    df = df.sort_values("実績(h)", ascending=False)
    # メトリクス表示
    c1, c2 = st.columns(2)
    c1.metric("総稼働時間", f"{df['実績(h)'].sum():.1f} 時間")
    c2.metric("最大タスク", f"{df.iloc[0]['タスク名']}")

    # グラフ表示
    fig = px.bar(df, x="実績(h)", y="タスク名", orientation='h', title="タスク別時間投下量", 
                 color="実績(h)", color_continuous_scale="Blues")
    st.plotly_chart(fig, use_container_width=True)
    
    # 詳細テーブル
    st.dataframe(df, use_container_width=True)
else:
    st.info("指定期間にデータが見つかりませんでした。Togglの記録を確認してください。")
