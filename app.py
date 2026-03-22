def get_toggl_analysis(target_date_val, mode="日次"):
    try:
        # 日本時間の開始と終了を ISO8601 形式（秒まで）で作成
        if mode == "日次":
            start_dt = datetime.combine(target_date_val, datetime.min.time())
            end_dt = datetime.combine(target_date_val, datetime.max.time())
        else:
            start_of_week = target_date_val - timedelta(days=target_date_val.weekday())
            start_dt = datetime.combine(start_of_week, datetime.min.time())
            end_dt = datetime.combine(start_of_week + timedelta(days=6), datetime.max.time())

        # Toggl v3 は "2026-03-18T00:00:00Z" 形式を好みます
        start_date_str = start_dt.strftime('%Y-%m-%dT%H:%M:%SZ')
        end_date_str = end_dt.strftime('%Y-%m-%dT%H:%M:%SZ')

        url = f"https://api.track.toggl.com/reports/api/v3/workspace/{TOGGL_WORKSPACE_ID}/search/time_entries"
        auth = base64.b64encode(f"{TOGGL_TOKEN}:api_token".encode()).decode()
        headers = {"Authorization": f"Basic {auth}", "Content-Type": "application/json"}
        
        # 確実にデータを取るために、空のリストを投げるのではなく明示的に範囲指定
        payload = {
            "start_date": start_date_str,
            "end_date": end_date_str
        }
        
        res = requests.post(url, headers=headers, json=payload)
        
        if res.status_code != 200:
            st.error(f"Toggl通信エラー: {res.status_code}")
            return None
        
        raw_data = res.json()
        
        # データがリスト形式で届いているか確認
        if not isinstance(raw_data, list) or len(raw_data) == 0:
            return None
        
        entries = []
        for item in raw_data:
            # 作業内容の取得
            desc = item.get('description') or "名称未設定"
            
            # 秒数の計算（durがミリ秒で入っているケースに対応）
            # v3 search API では 'seconds' が無い場合があるため 'dur' を見る
            dur = item.get('dur', 0)
            # 計測中のデータ（負の値）は除外
            if dur > 0:
                entries.append({'作業内容': desc, 'sec': dur / 1000})
            elif item.get('seconds'):
                entries.append({'作業内容': desc, 'sec': item.get('seconds')})
        
        if not entries:
            return None
            
        df = pd.DataFrame(entries)
        df_res = df.groupby('作業内容')['sec'].sum().reset_index()
        df_res['時間(h)'] = (df_res['sec'] / 3600).round(2)
        
        return df_res[['作業内容', '時間(h)']].sort_values('時間(h)', ascending=False)
        
    except Exception as e:
        st.error(f"解析エラー: {e}")
        return None
