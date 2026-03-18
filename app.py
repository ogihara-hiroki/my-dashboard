import streamlit as st
import requests, base64, pandas as pd
import plotly.express as px
from datetime import datetime, date, timedelta

# --- 設定（既存のものを維持） ---
GITHUB_TOKEN = st.secrets["MY_GITHUB_TOKEN"]
REPO_NAME = 'ogihara-hiroki/my-dashboard'
ASANA_TOKEN = '2/1202260582260384/1213620305884302:3b2113ab646543840f0e4192076e7c08'
TOGGL_TOKEN = '2236bb0c27861b351b5546732733043e'
TOGGL_WORKSPACE_ID = '8358873'

st.set_page_config(page_title="Work Analysis Pro", layout="wide")

# --- データ取得・解析関数（週次対応版） ---

def get_pc_analysis(target_date_val, mode="日次"):
    try:
        url = f"https://raw.githubusercontent.com/{REPO_NAME}/main/pc_usage_log.csv"
        # ★修正：列名を明示的に指定し、1行目を飛ばさないように設定を安定させる
        df_log = pd.read_csv(url, encoding='utf-8-sig', names=['timestamp', 'window_title'], header=None)
        
        # 列名のクリーンアップ
        df_log.columns = df_log.columns.str.strip()
        
        # timestamp列を日付型に変換（エラーデータは無視）
        df_log['timestamp'] = pd.to_datetime(df_log['timestamp'], errors='coerce')
        df_log = df_log.dropna(subset=['timestamp'])
        
        if mode == "日次":
            df_filtered = df_log[df_log['timestamp'].dt.date == target_date_val].copy()
            title_suffix = f"({target_date_val})"
        else:
            # 週次：月曜日〜日曜日の範囲で抽出
            start_of_week = target_date_val - timedelta(days=target_date_val.weekday())
            end_of_week = start_of_week + timedelta(days=6)
            df_filtered = df_log[(df_log['timestamp'].dt.date >= start_of_week) & 
                                 (df_log['timestamp'].dt.date <= end_of_week)].copy()
            title_suffix = f"({start_of_week} 〜 {end_of_week})"

        if df_filtered.empty:
            return None, ""

        def detect_app(title):
            title = str(title).lower()
            # ★改善：専門ソフトを先に判定させる
            if 'automation studio' in title: return 'Automation Studio (設計)'
            if 'visual studio' in title or 'vscode' in title: return 'IDE (開発)'
            if 'excel' in title: return 'Excel (作業/資料)'
            if 'chrome' in title or 'edge' in title: return 'ブラウザ (調査/メール)'
            if 'エクスプローラー' in title or 'folder' in title: return 'フォルダ (探す無駄)'
            return 'その他'

        df_filtered['アプリ'] = df_filtered['window_title'].apply(detect_app)
        df_res = df_filtered['アプリ'].value_counts().reset_index()
        df_res.columns = ['アプリ', '合計時間(h)']
        # 10秒間隔のログ（1行 = 10秒）を時間に変換
        df_res['合計時間(h)'] = round(df_res['合計時間(h)'] * 10 / 3600, 2)
        return df_res, title_suffix
    except Exception as e:
        # 具体的なエラーを表示
        st.error(f"解析エラーが発生しました: {e}")
        return None, ""

# --- サイドバー構成 ---
st.sidebar.header("表示設定")
# ★分析モードの切り替えを追加
analysis_mode = st.sidebar.radio("分析範囲を選択:", ["日次", "週次"])
target_date = st.sidebar.date_input("基準日を選択:", date.today())

# (PCログリモコンのコードはそのまま維持...)

# --- メイン表示エリア ---
st.title(f"📊 業務分析: {analysis_mode}")

# PCログ解析の実行
df_pc, period_text = get_pc_analysis(target_date, analysis_mode)

if df_pc is not None:
    st.subheader(f"💻 PC操作ログの内訳 {period_text}")
    
    col1, col2 = st.columns([2, 1])
    with col1:
        # 週次なら、より傾向が見やすい円グラフにするのもアリです
        fig = px.pie(df_pc, values='合計時間(h)', names='アプリ', title="アプリ利用割合", hole=0.4)
        st.plotly_chart(fig, use_container_width=True)
    with col2:
        st.write("詳細データ")
        st.table(df_pc)
else:
    st.info(f"選択された範囲 {target_date} のPCログが見つかりません。")

# (以下、Toggl連携などのコード...)
