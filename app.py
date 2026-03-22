def get_toggl_analysis(target_date_val, mode="日次"):
    try:
        if mode == "日次":
            start_date = target_date_val.strftime('%Y-%m-%d')
            end_date = target_date_val.strftime('%Y-%m-%d')
        else:
            start_of_week = target_date_val - timedelta(days=target_date_val.weekday())
            end_of_week = start_of_week + timedelta(days=6)
            start_date = start_of_week.strftime('%Y-%m-%d')
            end_date = end_of_week.strftime('%Y-%m-%d')

        url = f"https://api.track.toggl.com/reports/api/v3/workspace/{TOGGL_WORKSPACE_ID}/search/time_entries"
        auth = base64.b64encode(f"{TOGGL_TOKEN}:api_token".encode()).decode()
        headers = {"Authorization": f"Basic {auth}", "Content-Type": "application/json"}
        
        payload = {"start_date": start_date, "end_date": end_date}
        res = requests.post(url, headers=headers, json=payload)
        
        if res.status_code != 200:
            return None
        
        # ★修正ポイント：データの階層構造を正しく辿る
        raw_data = res.json()
        
        # v3 search API はリストで返ってくるはずですが、空の場合は None を返す
        if not raw_data or not isinstance(raw_data, list):
            return None
        
        entries = []
        for item in raw_data:
            # 作業内容（description）を取得
            desc = item.get('description') or "名称未設定"
            
            # 秒数の取得（seconds がない場合は dur を使用）
            # dur が負の値（計測中）の場合は 0 にする
            sec = item.get('seconds')
            if sec is None:
                dur = item.get('dur', 0)
                sec = dur / 1000 if dur > 0 else 0
            
            if sec > 0:
                entries.append({'作業内容': desc, 'sec': sec})
        
        if not entries:
            return None
            
        # 集計処理
        df = pd.DataFrame(entries)
        df_res = df.groupby('作業内容')['sec'].sum().reset_index()
        df_res['時間(h)'] = (df_res['sec'] / 3600).round(2)
        
        # 時間の多い順に並べ替え
        return df_res[['作業内容', '時間(h)']].sort_values('時間(h)', ascending=False)
        
    except Exception as e:
        # エラーが出た場合は画面に表示して原因を特定する
        st.error(f"Toggl解析エラー: {e}")
        return None
