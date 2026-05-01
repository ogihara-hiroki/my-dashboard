# （前略：インポートや関数部分は app(11).py と同じ）

# --- UIメイン ---
jst = pytz.timezone('Asia/Tokyo')
today_jst = datetime.now(jst).date()

st.sidebar.header("🗓️ PDCA設定")
target_date = st.sidebar.date_input("基準日:", value=today_jst)
st.title(f"🚀 Work PDCA Dashboard")

df_plan = get_asana_plan(target_date)
df_do = get_toggl_do(target_date)

st.header("🔍 予実分析 & 改善 (PDCA)")

# 1. データ結合
df_merge = None
if df_plan is not None and df_do is not None:
    df_merge = pd.merge(df_plan, df_do, on="作業内容", how="outer").fillna(0)
    df_merge['表示名'] = df_merge.apply(lambda r: r['表示名'] if isinstance(r['表示名'], str) else "⚡ " + str(r['作業内容']), axis=1)
    df_merge['次回の対策'] = df_merge['次回の対策'].replace(0, "")
elif df_plan is not None:
    df_merge = df_plan.copy()
    df_merge["実績(h)"] = 0.0
elif df_do is not None:
    df_merge = df_do.copy()
    df_merge["予定(h)"] = 0.0
    df_merge["表示名"] = "⚡ " + df_merge["作業内容"]
    df_merge["次回の対策"] = ""

# 2. サマリー表示 (ここが「一目でわかる」追加ポイント)
if df_merge is not None:
    # 各種数値の計算
    total_plan = df_merge['予定(h)'].sum()
    total_do = df_merge['実績(h)'].sum()
    
    # 予定していた作業の実績（⚡以外）
    planned_task_do = df_merge[~df_merge['表示名'].str.contains("⚡")]['実績(h)'].sum()
    # 飛び込み作業の実績（⚡のみ）
    urgent_do = df_merge[df_merge['表示名'].str.contains("⚡")]['実績(h)'].sum()
    
    # 達成率計算
    achievement_rate = (planned_task_do / total_plan * 100) if total_plan > 0 else 0
    urgent_ratio = (urgent_do / total_do * 100) if total_do > 0 else 0

    # サマリーメトリクスの表示
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("総実績時間", f"{total_do:.1f} h")
    m2.metric("計画達成率", f"{achievement_rate:.0f} %", help="予定していた作業をどれだけこなせたか")
    m3.metric("飛び込み比率", f"{urgent_ratio:.0f} %", delta=f"{urgent_do:.1f} h", delta_color="inverse", help="全作業のうち、予定外の作業が占める割合")
    m4.metric("予定合計", f"{total_plan:.1f} h")

    st.divider() # 区切り線

    # 3. 整形と詳細表示
    df_merge['差分(h)'] = (df_merge['実績(h)'] - df_merge['予定(h)']).round(1)
    df_merge['グラフ用名称'] = df_merge['表示名'].apply(lambda x: x[:15] + "..." if len(x) > 15 else x)
    df_merge = df_merge.sort_values(['予定(h)', '実績(h)'], ascending=False)
    
    c1, c2 = st.columns([1, 1])
    with c1:
        # メインの棒グラフ
        fig = px.bar(df_merge, x="グラフ用名称", y=["予定(h)", "実績(h)"], barmode="group", text_auto='.1f',
                     hover_data={"表示名": True, "グラフ用名称": False},
                     category_orders={"グラフ用名称": df_merge["グラフ用名称"].tolist()})
        fig.update_layout(title="作業別 予実比較")
        st.plotly_chart(fig, use_container_width=True)
        
        # 内訳を円グラフで表示
        pie_df = pd.DataFrame({
            "分類": ["計画通り", "飛び込み"],
            "時間": [planned_task_do, urgent_do]
        })
        fig_pie = px.pie(pie_df, values="時間", names="分類", hole=0.4, 
                         color_discrete_map={"計画通り": "#1f77b4", "飛び込み": "#ff7f0e"})
        fig_pie.update_layout(title="今日の時間の使い道")
        st.plotly_chart(fig_pie, use_container_width=True)
        
    with c2:
        st.write("📋 PDCA詳細テーブル")
        st.table(df_merge[['表示名', '予定(h)', '実績(h)', '差分(h)', '次回の対策']].style.format("{:.1f}", subset=["予定(h)", "実績(h)", "差分(h)"]))
else:
    st.info("💡 データがありません。")
