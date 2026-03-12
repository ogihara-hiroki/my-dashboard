import streamlit as st
import requests, base64, pandas as pd
import plotly.express as px
from datetime import datetime, date

# --- 設定（★トークンをここに貼ってください） ---
GITHUB_TOKEN = 'あなたのトークンをここに貼る'
REPO_NAME = 'ogihara-hiroki/my-dashboard'
ASANA_TOKEN = '2/1202260582260384/1213620305884302:3b2113ab646543840f0e4192076e7c08'
TOGGL_TOKEN = '2236bb0c27861b351b5546732733043e'
TOGGL_WORKSPACE_ID = '8358873'

# --- GitHubのON/OFFを書き換える関数 ---
def update_github_status(status_text):
    url = f"https://api.github.com/repos/{REPO_NAME}/contents/status.txt"
    headers = {"Authorization": f"token {GITHUB_TOKEN}"}
    
    # 現在のSHAを取得
    res = requests.get(url, headers=headers).json()
    if 'sha' not in res: return # ファイルがない場合

    # 書き換え実行
    data = {
        "message": f"Switch to {status_text}",
        "content": base64.b64encode(status_text.encode()).decode(),
        "sha": res['sha']
    }
    requests.put(url, headers=headers, json=data)

# --- 画面構成 ---
st.set_page_config(page_title="Work Analysis Pro", layout="wide")
st.sidebar.header("表示設定")
target_date = st.sidebar.date_input("分析したい日を選択:", date.today())

# ★サイドバーにスイッチを追加
st.sidebar.markdown("---")
st.sidebar.subheader("PCログリモコン")
# セッション状態を使って、スイッチが押されたときだけ通信するようにする
if "last_status" not in st.session_state:
    st.session_state.last_status = "OFF"

toggle = st.sidebar.checkbox("PCログ記録を開始")
current_status = "ON" if toggle else "OFF"

# 状態が変わった時だけGitHubを更新
if current_status != st.session_state.last_status:
    update_github_status(current_status)
    st.session_state.last_status = current_status
    st.sidebar.success(f"指示を送信: {current_status}")

if toggle:
    st.sidebar.info("🚀 PC側で記録中です...")
else:
    st.sidebar.warning("💤 記録停止中")

# --- 以下、以前のToggl/PCログ表示コード（省略せずそのまま維持してください） ---
# (中略：前回の get_toggl_data や get_pc_analysis をここに繋げてください)
