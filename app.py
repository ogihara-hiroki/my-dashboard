import streamlit as st
import requests, base64, pandas as pd
import plotly.express as px
from datetime import datetime, date, timedelta
import urllib3

# SSL警告を非表示にする
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# --- 設定 ---
GITHUB_TOKEN = st.secrets["MY_GITHUB_TOKEN"]
REPO_NAME = 'ogihara-hiroki/my-dashboard'
STATUS_FILE = 'status.txt'
TOGGL_TOKEN = '2236bb0c27861b351b5546732733043e'
TOGGL_WORKSPACE_ID = '8358873'
ASANA_TOKEN = '2/1202260582260384/1213620305884302:3b2113ab646543840f0e4192076e7c08'
ASANA_WORKSPACE_ID = '1200313649553191'

st.set_page_config(page_title="Work PDCA Dashboard", layout="wide")

# --- 1. GitHubリモコン (Action) ---
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

# --- 2. Asanaから予定(Plan)を取得 ---
@st.cache_data(ttl=300)
def get_asana_plan(target_date_val):
    try:
        # 基準日が期限のタスクを取得
        url = "https://app.asana.com/api/1.0/tasks"
        headers = {"Authorization": f"Bearer {ASANA_TOKEN}"}
        params = {
            "workspace": ASANA_WORKSPACE_ID,
            "assignee": "me",
            "opt_fields": "name,due_on,custom_fields"
        }
        res = requests.get(url, headers=headers, params=params)
        if res.status_code != 200: return None
        
        tasks = res.json().get('data', [])
        plan_data = []
        for t in tasks:
            # 期限が選択日と一致するか（または期限未設定も一旦出す）
            if t.get('due_on') == target_date_val.strftime('%Y-%m-%d'):
                # 予定時間(カスタムフィールド)を探すロジック（適宜ID調整が必要）
                estimate = 0
                for cf in t.get('custom_fields', []):
                    if '予定' in cf.get('name', '') or 'Estimate' in cf.get('name', ''):
                        estimate = cf.get('number_value') or 0
                
                plan_data.append({"作業内容": t['name'], "予定(h)": estimate})
        return pd.DataFrame(plan_data) if plan_data else None
    except: return None

# --- 3. Togglから実績(Do)を取得 (完全安定版) ---
@st.cache_data(ttl=300)
def get_toggl_do(target_date_val, mode="日次"):
    try:
        # 日付形式を YYYY-MM-DD に統一
        if mode == "日次":
            start_str = target_date_val.strftime('%Y-%m-%d')
            end_str = target_date_val.strftime('%Y-%m-%d')
        else:
            start_of_week = target_date_val - timedelta(days=target_date_val.weekday())
            start_str = start_of_week.strftime('%Y-%m-%d')
            end_str = (start_of_week + timedelta(days=6)).strftime('%Y-%m-%d')

        url = f"https://api.track.toggl.com/reports/api/v3/workspace/{TOGGL_WORKSPACE_ID}/summary/time_entries"
        auth = base64.b64encode(f"{TOGGL_TOKEN}:api_token".encode()).decode()
        headers = {"Authorization": f"Basic {auth}", "Content-Type": "application/json"}
        
        # ★修正：無料プランでエラー（'str' object...）を回避するための必須パラメータ
        payload = {
            "start_date": start_str,
            "end_date": end_str,
            "group_by": "project"  # プロジェクト別に集計するよう明示
        }
        
        res = requests.post(url, headers=headers, json=payload)
        
        # 通信失敗時の処理
        if res.status_code != 200:
            return None
        
        raw_data = res.json()
        
        # もしデータがリスト形式でなければ（エラー文字列なら）終了
        if not isinstance(raw_data, list):
            return None
            
        entries = []
        for project_item in raw_data:
            # プロジェクトの下にある具体的な作業内容（sub_groups）をループ
            for sub in project_item.get('sub_groups', []):
                desc = sub.get('title') or "名称未設定"
                sec = sub.get('seconds', 0)
                if sec > 0:
                    entries.append({'作業内容': desc, '実績(h)': round(sec / 3600, 2)})
        
        if not entries:
            return None
            
        df = pd.DataFrame(entries)
        return df.groupby('作業内容')['実績(h)'].sum().reset_index()
        
    except Exception as e:
        # エラー発生時は内容を表示
        st.error(f"Toggl取得エラー: {e}")
        return None

# --- 4. PC操作ログ (Check/事実) ---
def get_pc_log(target_date_val, mode="日次"):
    try:
        url = f"https://raw.githubusercontent.com/{REPO_NAME}/main/pc_usage_log.csv"
        df = pd.read_csv(url, encoding='utf-8-sig', names=['timestamp', 'window_title'], header=None)
        df['timestamp'] = pd.to_datetime(df['timestamp'], errors='coerce')
        df = df.dropna(subset=['timestamp'])
        
        if mode == "日次":
            df = df[df['timestamp'].dt.date == target_date_val]
        else:
            start = target_date_val - timedelta(days=target_date_val.weekday())
            df = df[(df['timestamp'].dt.date >= start) & (df['timestamp'].dt.date <= start + timedelta(days=6))]
        
        if df.empty: return None
        def detect(t):
            t = str(t).lower()
            if 'automation studio' in t: return '設計'
            if 'visual studio' in t or 'vscode' in t: return '開発'
            if 'excel' in t: return '事務'
            if 'chrome' in t or 'edge' in t: return '調査'
            return 'その他'
        df['アプリ'] = df['window_title'].apply(detect)
        res = df['アプリ'].value_counts().reset_index()
        res.columns = ['アプリ', '時間(h)']
        res['時間(h)'] = round(res['時間(h)'] * 10 / 3600, 2)
        return res
    except: return None

# --- UIメイン ---
st.sidebar.header("🗓️ PDCA設定")
analysis_mode = st.sidebar.radio("分析範囲:", ["日次", "週次"])
target_date = st.sidebar.date_input("基準日:", date.today())

st.title(f"🚀 Work PDCA Dashboard: {analysis_mode}")

# データ取得
df_plan = get_asana_plan(target_date)
df_do = get_toggl_do(target_date, analysis_mode)
df_pc = get_pc_log(target_date, analysis_mode)

# --- PDCA 振り返りセクション (Check) ---
st.header("🔍 予実分析 (Plan vs Do)")

# Asanaの予定がない場合でも、Togglの実績をベースに表を作る
if df_do is not None:
    if df_plan is not None:
        # 両方ある場合は結合
        df_merge = pd.merge(df_plan, df_do, on="作業内容", how="outer").fillna(0)
    else:
        # Asanaがない場合は実績のみで表を作る
        df_merge = df_do.copy()
        df_merge["予定(h)"] = 0
        df_merge = df_merge[["作業内容", "予定(h)", "実績(h)"]]

    df_merge['差分(h)'] = df_merge['実績(h)'] - df_merge['予定(h)']
    
    col1, col2 = st.columns([2, 1])
    with col1:
        # 予定と実績を並べて表示
        fig = px.bar(df_merge, x="作業内容", y=["予定(h)", "実績(h)"], barmode="group", 
                     title=f"{target_date} の作業実績")
        st.plotly_chart(fig, use_container_width=True)
    with col2:
        st.write("📊 予実詳細データ")
        st.table(df_merge)
    
    # 改善アクションのアドバイス (Act)
    if df_plan is None:
        st.warning("💡 **Actのヒント:** Togglの記録はありますが、Asanaに本日の予定が見つかりませんでした。朝一番にAsanaで「予定（Plan）」を立てることで、より正確なPDCAが回せます。")
    else:
        st.info("💡 **Actのヒント:** 実績が予定を超えたものは、Asanaに理由をメモしておきましょう。")
else:
    st.warning("⚠️ Togglの記録が見つかりません。")
