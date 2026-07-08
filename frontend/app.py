import streamlit as st
import requests
import plotly.graph_objects as go
import plotly.express as px
import pandas as pd
import os

# Reads from Streamlit secrets in production
# Falls back to localhost in development
try:
    BACKEND_URL = st.secrets["BACKEND_URL"]
except:
    BACKEND_URL = os.getenv(
        "BACKEND_URL",
        "https://levelup-cp.onrender.com"
    )

API = BACKEND_URL + "/api"
st.set_page_config(
    page_title="CP Coach",
    page_icon="🏆",
    layout="wide"
)

st.title("🏆 CP Coach")
st.subheader("Your Personal Codeforces Mentor")

# ── Handle Input ──────────────────────────────────
col1, col2 = st.columns([3, 1])
with col1:
    handle = st.text_input(
        "Enter your Codeforces handle",
        placeholder="e.g. tourist"
    )
with col2:
    st.write("")
    st.write("")
    analyze = st.button("Analyze Profile", type="primary")

if analyze and handle:
    with st.spinner(f"Fetching and analyzing {handle}... (15–30 seconds)"):
        try:
            res = requests.post(
                f"{API}/full-analysis/{handle}",
                timeout=120
            )
            if res.status_code == 200:
                st.session_state['data']   = res.json()
                st.session_state['handle'] = handle
                st.success("Analysis complete!")
            elif res.status_code == 404:
                st.error(f"Handle '{handle}' not found on Codeforces")
            else:
                st.error(f"Error: {res.json().get('detail', 'Unknown error')}")
        except requests.exceptions.Timeout:
            st.error("Timed out. Try again.")
        except requests.exceptions.ConnectionError:
            st.error("Cannot connect to backend. Is FastAPI running on port 8000?")

# ── Main Dashboard ────────────────────────────────
if 'data' not in st.session_state:
    st.stop()

data          = st.session_state['data']
skill         = data['skill_profile']
stagnation    = data['stagnation']
breakthroughs = data.get('breakthrough_topics', [])

# ── Section 1: Profile Overview ───────────────────
st.divider()
st.subheader("📌 Profile Overview")

c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("Current Rating",  data['current_rating'])
c2.metric("Max Rating",      data['max_rating'])
c3.metric("Total Solved",    data['total_solved'])
c4.metric("Weekly Rate",     f"{data['weekly_solve_rate']}/wk")
c5.metric("Consistency",     data['consistency_score'])

c1, c2, c3, c4, c5, c6 = st.columns(6)
c1.metric("Contests",        data['contest_count'])
c2.metric("Tag Diversity",   data['tag_diversity'])
c3.metric("Weak Topics",     skill['summary']['weak'])
c4.metric("Moderate",        skill['summary']['moderate'])
c5.metric("Strong Topics",   skill['summary']['strong'])
c6.metric("Never Touched",   skill['summary']['never_touched'])

# ── Alerts ────────────────────────────────────────
if stagnation['is_stagnant']:
    st.warning(f"⚠️ **Stagnation Detected:** {stagnation['reason']}")

if breakthroughs:
    st.success(
        f"🚀 **Breakthrough Detected in {breakthroughs[0]['tag']}!** "
        f"{breakthroughs[0]['message']}"
    )

# ── Section 2: Skill Radar Chart ──────────────────
st.divider()
st.subheader("🕸️ Skill Radar Chart")

details  = skill['details']
top_tags = sorted(
    details,
    key=lambda x: x['total_attempted'],
    reverse=True
)[:12]

tags   = [t['tag'] for t in top_tags]
scores = [t['score'] for t in top_tags]

fig_radar = go.Figure()
fig_radar.add_trace(go.Scatterpolar(
    r         = scores,
    theta     = tags,
    fill      = 'toself',
    name      = data['handle'],
    line      = dict(color='royalblue', width=2),
    fillcolor = 'rgba(65, 105, 225, 0.20)'
))
fig_radar.update_layout(
    polar=dict(
        radialaxis=dict(
            visible  = True,
            range    = [0, 1],
            tickvals = [0.0, 0.30, 0.55, 1.0],
            ticktext = ['0', 'Weak', 'Moderate', 'Strong']
        )
    ),
    showlegend = True,
    height     = 500,
    title      = f"Skill Radar — {data['handle']}"
)
st.plotly_chart(fig_radar, use_container_width=True)

# ── Section 3: Weak / Moderate / Strong ───────────
st.divider()
st.subheader("📊 Topic Classification")

c1, c2, c3 = st.columns(3)

with c1:
    st.markdown("### 🔴 Weak Topics")
    st.caption("Focus your practice here first")
    if skill['weak']:
        for tag in skill['weak']:
            score    = skill['scores'][tag]
            momentum = skill['momentum'].get(tag, 0)
            mom_icon = "📈" if momentum > 50 else ("📉" if momentum < -50 else "➡️")
            st.markdown(f"- **{tag}** `{score:.2f}` {mom_icon}")
    else:
        st.success("No weak topics!")

with c2:
    st.markdown("### 🟡 Moderate Topics")
    st.caption("Getting there, keep pushing")
    for tag in skill['moderate'][:10]:
        score    = skill['scores'][tag]
        momentum = skill['momentum'].get(tag, 0)
        mom_icon = "📈" if momentum > 50 else ("📉" if momentum < -50 else "➡️")
        st.markdown(f"- {tag} `{score:.2f}` {mom_icon}")

with c3:
    st.markdown("### 🟢 Strong Topics")
    st.caption("You have mastered these")
    for tag in skill['strong'][:10]:
        score    = skill['scores'][tag]
        st.markdown(f"- {tag} `{score:.2f}`")

# ── Section: Never Touched Topics ─────────────────
if 'data' in st.session_state:
    data  = st.session_state['data']
    skill = data['skill_profile']

    never_touched      = skill.get('never_touched', [])
    untouched_summary  = skill.get('untouched_summary', {})

    if never_touched:
        st.divider()
        st.subheader("🚫 Topics You Have Never Touched")
        st.caption(
            "These are CF problem tags that don't appear "
            "anywhere in your submission history."
        )

        # ── Summary Metrics ────────────────────────
        col1, col2, col3, col4, col5 = st.columns(5)
        col1.metric(
            "Total Untouched",
            untouched_summary.get('total', 0)
        )
        col2.metric(
            "🔴 Critical",
            len(untouched_summary.get('critical', []))
        )
        col3.metric(
            "🟠 Important",
            len(untouched_summary.get('important', []))
        )
        col4.metric(
            "🟡 Learn Soon",
            len(untouched_summary.get('learn_soon', []))
        )
        col5.metric(
            "🔵 Advanced",
            len(untouched_summary.get('advanced', []))
        )

        st.divider()

        # ── Critical Alert ─────────────────────────
        critical = untouched_summary.get('critical', [])
        if critical:
            st.error(
                f"⚠️ **Critical gaps detected:** "
                f"You have never attempted: "
                f"**{', '.join(critical)}**. "
                f"These are fundamental topics at your rating level."
            )

        # ── Tabs by Priority ───────────────────────
        tab1, tab2, tab3, tab4, tab5 = st.tabs([
            f"🔴 Critical ({len(untouched_summary.get('critical', []))})",
            f"🟠 Important ({len(untouched_summary.get('important', []))})",
            f"🟡 Learn Soon ({len(untouched_summary.get('learn_soon', []))})",
            f"🔵 Advanced ({len(untouched_summary.get('advanced', []))})",
            f"⚪ Optional ({len(untouched_summary.get('optional', []))})"
        ])

        def render_untouched_tab(tab, priority_key, priority_label):
            with tab:
                tags_in_priority = [
                    t for t in never_touched
                    if priority_label in t['priority']
                ]

                if not tags_in_priority:
                    st.success(f"No {priority_label.lower()} gaps!")
                    return

                for item in tags_in_priority:
                    col1, col2, col3 = st.columns([2, 4, 2])

                    with col1:
                        st.markdown(f"**{item['tag']}**")

                    with col2:
                        st.caption(item['reason'])

                    with col3:
                        # Link to CF problems for this tag
                        cf_tag_url = (
                            f"https://codeforces.com/problemset"
                            f"?tags={item['tag'].replace(' ', '+')}"
                        )
                        st.link_button(
                            "Practice →",
                            cf_tag_url,
                            use_container_width=True
                        )

        render_untouched_tab(tab1, 'critical',   'Critical')
        render_untouched_tab(tab2, 'important',  'Important')
        render_untouched_tab(tab3, 'learn_soon', 'Learn Soon')
        render_untouched_tab(tab4, 'advanced',   'Advanced')
        render_untouched_tab(tab5, 'optional',   'Optional')

        # ── Full Table View ────────────────────────
        st.divider()
        with st.expander("📋 View All Untouched Topics as Table"):
            import pandas as pd
            table = pd.DataFrame([
                {
                    "Topic":    t['tag'],
                    "Priority": t['priority'],
                    "Reason":   t['reason']
                }
                for t in never_touched
            ])
            st.dataframe(table, use_container_width=True, height=400)

# ── Section: Rating Prediction ─────────────────────

if 'data' in st.session_state:
    data       = st.session_state['data']
    prediction = data.get('rating_prediction', {})

    if prediction and not prediction.get('error'):

        st.divider()
        st.subheader("📈 Rating Prediction")

        current = prediction.get('current_rating', 0)
        pred_3m = prediction.get('3_months', {})
        pred_6m = prediction.get('6_months', {})
        explain = prediction.get('explanation', {})

        # ── Prediction Cards ───────────────────────
        col1, col2, col3 = st.columns(3)

        with col1:
            st.metric(
                label   = "Current Rating",
                value   = current
            )

        with col2:
            if pred_3m:
                change_3m = pred_3m['mid'] - current
                st.metric(
                    label  = "Predicted in 3 Months",
                    value  = f"{pred_3m['low']} – {pred_3m['high']}",
                    delta  = f"{change_3m:+d} from now"
                )

        with col3:
            if pred_6m:
                change_6m = pred_6m['mid'] - current
                st.metric(
                    label  = "Predicted in 6 Months",
                    value  = f"{pred_6m['low']} – {pred_6m['high']}",
                    delta  = f"{change_6m:+d} from now"
                )

        # ── Model Accuracy Note ────────────────────
        mae_3m = prediction.get('model_mae_3m', 0)
        st.caption(
            f"ℹ️ Model accuracy: ±{mae_3m:.0f} rating points. "
            f"{prediction.get('confidence_note', '')}"
        )

        # ── Rating Trajectory Graph ────────────────
        import plotly.graph_objects as go
        import pandas as pd

        st.subheader("📉 Rating Trajectory")

        rating_history = data.get('rating_history', [])

        if rating_history:
            hist_df           = pd.DataFrame(rating_history)
            hist_df['date']   = pd.to_datetime(hist_df['timestamp'], unit='s')
            hist_df           = hist_df.sort_values('date')

            fig = go.Figure()

            # Past rating (solid line)
            fig.add_trace(go.Scatter(
                x     = hist_df['date'],
                y     = hist_df['new_rating'],
                mode  = 'lines+markers',
                name  = 'Historical Rating',
                line  = dict(color='royalblue', width=2),
                marker = dict(size=4)
            ))

            # Future prediction (dotted line with range)
            import time
            now      = pd.Timestamp.now()
            date_3m  = now + pd.DateOffset(months=3)
            date_6m  = now + pd.DateOffset(months=6)

            last_rating = hist_df['new_rating'].iloc[-1]

            if pred_3m and pred_6m:
                # Predicted midpoint line
                fig.add_trace(go.Scatter(
                    x    = [now, date_3m, date_6m],
                    y    = [last_rating, pred_3m['mid'], pred_6m['mid']],
                    mode = 'lines+markers',
                    name = 'Predicted (midpoint)',
                    line = dict(color='green', width=2, dash='dot'),
                    marker = dict(size=8, symbol='diamond')
                ))

                # Upper bound
                fig.add_trace(go.Scatter(
                    x    = [now, date_3m, date_6m],
                    y    = [last_rating, pred_3m['high'], pred_6m['high']],
                    mode = 'lines',
                    name = 'Prediction upper bound',
                    line = dict(color='rgba(0,200,0,0.3)', width=1, dash='dot'),
                    showlegend = False
                ))

                # Lower bound with fill
                fig.add_trace(go.Scatter(
                    x          = [now, date_3m, date_6m],
                    y          = [last_rating, pred_3m['low'], pred_6m['low']],
                    mode       = 'lines',
                    name       = 'Prediction range',
                    line       = dict(color='rgba(0,200,0,0.3)', width=1, dash='dot'),
                    fill       = 'tonexty',
                    fillcolor  = 'rgba(0,200,0,0.1)'
                ))

                # Add annotations for prediction points
                fig.add_annotation(
                    x    = date_3m,
                    y    = pred_3m['mid'],
                    text = f"3M: {pred_3m['low']}–{pred_3m['high']}",
                    showarrow = True,
                    arrowhead = 2,
                    bgcolor   = 'rgba(255,255,255,0.8)'
                )
                fig.add_annotation(
                    x    = date_6m,
                    y    = pred_6m['mid'],
                    text = f"6M: {pred_6m['low']}–{pred_6m['high']}",
                    showarrow = True,
                    arrowhead = 2,
                    bgcolor   = 'rgba(255,255,255,0.8)'
                )

            fig.update_layout(
                title  = f"Rating History + Prediction — {data['handle']}",
                xaxis_title = "Date",
                yaxis_title = "Rating",
                height = 450,
                hovermode = 'x unified'
            )
            st.plotly_chart(fig, use_container_width=True)

        # ── Explanation ────────────────────────────
        st.subheader("🔍 What's Driving This Prediction")

        if explain:
            col1, col2 = st.columns(2)

            with col1:
                st.markdown("**Factors affecting your prediction:**")
                for factor in explain.get('factors', []):
                    if factor['impact'] == 'positive':
                        st.success(f"✅ **{factor['feature']}**: {factor['detail']}")
                    elif factor['impact'] == 'neutral':
                        st.warning(f"⚠️ **{factor['feature']}**: {factor['detail']}")
                    else:
                        st.error(f"❌ **{factor['feature']}**: {factor['detail']}")

            with col2:
                suggestions = explain.get('suggestions', [])
                if suggestions:
                    st.markdown("**To push your prediction higher:**")
                    for suggestion in suggestions:
                        st.markdown(f"→ {suggestion}")
                else:
                    st.success("You're on the right track! Keep up the current pace.")

        # ── Feature Values Used ────────────────────
        with st.expander("🔧 Model Input Values (what was passed to the model)"):
            features_used = prediction.get('features_used', {})
            if features_used:
                feat_df = pd.DataFrame([
                    {"Feature": k, "Value": round(v, 3)}
                    for k, v in features_used.items()
                ])
                st.dataframe(feat_df, use_container_width=True)

    elif prediction and prediction.get('error'):
        st.warning(
            f"⚠️ Rating prediction unavailable: {prediction['error']}"
        )
# ── Section 4: Full Tag Table ──────────────────────
st.divider()
st.subheader("📋 Full Tag Analysis — All Metrics")
st.caption("All 8 features used in scoring, plus momentum and contest mastery insights")

table_rows = []
for item in skill['details']:
    table_rows.append({
        "Topic":           item['tag'],
        "Level":           item['level'],
        "Score":           item['score'],
        "Solve Rate":      f"{item['solve_rate']*100:.1f}%",
        "Avg Attempts":    item['avg_attempts'],
        "Highest Rating":  item['highest_rating'],
        "Avg Rating":      round(item['avg_rating_solved']),
        "Volume":          item['total_solved'],
        "First-Try %":     f"{item['first_try_ac_rate']*100:.1f}%",
        "Contest %":       f"{item['contest_solve_percentage']*100:.1f}%",
        "Recency (days)":  round(item['recency_days']),
        "Momentum":        item['momentum_label'],
        "Recent Avg":      round(item['recent_avg_rating'])
    })

df = pd.DataFrame(table_rows)

def color_level(val):
    if val == 'Weak':
        return 'background-color: #ffcccc'
    elif val == 'Moderate':
        return 'background-color: #fff3cc'
    elif val == 'Strong':
        return 'background-color: #ccffcc'
    return ''

styled = df.style.apply(lambda col: [color_level(v) for v in col], subset=['Level'])
st.dataframe(styled, use_container_width=True, height=450)

# ── Section 5: New Metric Insights ────────────────
st.divider()
st.subheader("🔍 Deep Metric Insights")

tab1, tab2, tab3, tab4 = st.tabs([
    "📈 Momentum",
    "🏆 Contest Mastery",
    "⚡ First-Try Rate",
    "📦 Volume"
])

with tab1:
    st.markdown("**Momentum = Recent Avg Rating − All-Time Avg Rating**")
    st.caption("Positive = you are currently solving harder than your average (breaking through!)")

    mom_data = [
        {
            "tag":         item['tag'],
            "all_time_avg": round(item['avg_rating_solved']),
            "recent_avg":  round(item['recent_avg_rating']),
            "momentum":    item['momentum'],
            "status":      item['momentum_label']
        }
        for item in skill['details']
        if item['total_solved'] >= 5
    ]
    mom_df = pd.DataFrame(mom_data).sort_values('momentum', ascending=False)

    fig_mom = px.bar(
        mom_df,
        x     = 'tag',
        y     = 'momentum',
        color = 'momentum',
        color_continuous_scale = ['red', 'gray', 'green'],
        title = "Momentum Per Topic",
        labels = {'momentum': 'Momentum (rating pts)'}
    )
    fig_mom.add_hline(y=0, line_dash="dash", line_color="black")
    fig_mom.update_layout(height=400)
    st.plotly_chart(fig_mom, use_container_width=True)

    st.dataframe(mom_df, use_container_width=True)

with tab2:
    st.markdown("**Contest % = How often you solved these problems during a LIVE contest**")
    st.caption("Higher = deeper mastery. Anyone can solve on a couch with music. Contest solving = real skill.")

    contest_data = [
        {
            "tag":           item['tag'],
            "contest_%":     round(item['contest_solve_percentage']*100, 1),
            "total_solved":  item['total_solved'],
            "level":         item['level']
        }
        for item in skill['details']
        if item['total_solved'] >= 5
    ]
    contest_df = pd.DataFrame(contest_data).sort_values('contest_%', ascending=False)

    fig_ct = px.bar(
        contest_df,
        x     = 'tag',
        y     = 'contest_%',
        color = 'level',
        color_discrete_map = {
            'Weak': 'red', 'Moderate': 'orange', 'Strong': 'green'
        },
        title  = "Contest Solve % Per Topic",
        labels = {'contest_%': 'Contest Solve %'}
    )
    fig_ct.update_layout(height=400)
    st.plotly_chart(fig_ct, use_container_width=True)

with tab3:
    st.markdown("**First-Try % = How often your FIRST submission was an AC**")
    st.caption("90%+ first-try on a topic = you are a precision master in that area")

    ft_data = [
        {
            "tag":           item['tag'],
            "first_try_%":   round(item['first_try_ac_rate']*100, 1),
            "total_solved":  item['total_solved'],
            "level":         item['level']
        }
        for item in skill['details']
        if item['total_solved'] >= 5
    ]
    ft_df = pd.DataFrame(ft_data).sort_values('first_try_%', ascending=False)

    fig_ft = px.bar(
        ft_df,
        x     = 'tag',
        y     = 'first_try_%',
        color = 'level',
        color_discrete_map = {
            'Weak': 'red', 'Moderate': 'orange', 'Strong': 'green'
        },
        title  = "First-Try AC Rate Per Topic",
        labels = {'first_try_%': 'First-Try AC %'}
    )
    fig_ft.update_layout(height=400)
    st.plotly_chart(fig_ft, use_container_width=True)

with tab4:
    st.markdown("**Volume = How many problems solved (capped at 50 for scoring)**")
    st.caption("Low volume = possible fluke. High volume = consistent, proven skill")

    vol_data = [
        {
            "tag":       item['tag'],
            "solved":    item['total_solved'],
            "attempted": item['total_attempted'],
            "level":     item['level']
        }
        for item in skill['details']
    ]
    vol_df = pd.DataFrame(vol_data).sort_values('solved', ascending=False)

    fig_vol = px.bar(
        vol_df,
        x     = 'tag',
        y     = 'solved',
        color = 'level',
        color_discrete_map = {
            'Weak': 'red', 'Moderate': 'orange', 'Strong': 'green'
        },
        title  = "Problems Solved Per Topic",
        labels = {'solved': 'Total Solved'}
    )
    fig_vol.add_hline(
        y=50, line_dash="dash",
        line_color="blue",
        annotation_text="Volume cap (50)"
    )
    fig_vol.update_layout(height=400)
    st.plotly_chart(fig_vol, use_container_width=True)

# ── Section 6: Rating History ──────────────────────
st.divider()
st.subheader("📈 Rating History")

if data['rating_history']:
    hist_df = pd.DataFrame(data['rating_history'])
    hist_df['date'] = pd.to_datetime(hist_df['timestamp'], unit='s')

    fig_r = px.line(
        hist_df,
        x       = 'date',
        y       = 'new_rating',
        title   = f"Rating History — {data['handle']}",
        labels  = {'new_rating': 'Rating', 'date': 'Date'},
        markers = True
    )
    fig_r.update_traces(line_color='royalblue', line_width=2)
    fig_r.update_layout(height=400)
    st.plotly_chart(fig_r, use_container_width=True)

# ── Section 7: Neglected Topics ───────────────────
st.divider()
c1, c2 = st.columns(2)

with c1:
    st.subheader("😴 Neglected Topics")
    st.caption("Not practiced in 60+ days")
    neglected = data.get('neglected_topics', [])
    if neglected:
        neg_df = pd.DataFrame(neglected[:8])
        st.dataframe(neg_df, use_container_width=True)
    else:
        st.success("All topics practiced recently!")

with c2:
    st.subheader("🚀 Breakthrough Topics")
    st.caption("You're solving harder than your average here — push further!")
    bts = data.get('breakthrough_topics', [])
    if bts:
        for bt in bts[:5]:
            st.info(f"**{bt['tag']}**: {bt['message']}")
    else:
        st.info("No active breakthroughs detected right now.")

# ── Section 8: Comfort Rating ─────────────────────
st.divider()
st.info(
    f"🎯 **Comfort Rating: {data['comfort_rating']}** — "
    f"Daily problem recommendations will be at "
    f"**{data['comfort_rating'] + 100}–{data['comfort_rating'] + 200}** difficulty"
)

# ── Section: Daily Recommendations ────────────────
if 'data' in st.session_state:
    data  = st.session_state['data']
    recs  = data.get('recommendations', {})
    daily = recs.get('daily', [])

    st.divider()
    st.subheader("📚 Today's 3 Problems")
    st.caption(
        f"Personalized for your skill gaps. "
        f"Comfort rating: **{data.get('comfort_rating', '?')}**"
    )

    if not daily:
        st.warning(
            "No recommendations available. "
            "Make sure problems are cached via /api/cache-problems"
        )
    else:
        cols = st.columns(3)
        for i, (col, prob) in enumerate(zip(cols, daily)):
            if not prob:
                continue
            with col:
                # Color code by type
                if i == 0:
                    st.error(f"**Problem {i+1} — Weak Tag**")
                elif i == 1:
                    st.warning(f"**Problem {i+2} — Practice**")
                else:
                    st.success(f"**Problem {i+3} — Quick Win ⚡**")

                st.markdown(f"### {prob['title']}")
                st.markdown(f"**Rating:** {prob['rating']}")
                st.markdown(f"**Focus Tag:** `{prob['tag_focused']}`")
                st.markdown(f"**Tags:** {', '.join(prob['tags'][:3])}")
                st.caption(prob['reason'])
                st.link_button(
                    "Solve on Codeforces →",
                    prob['cf_url'],
                    use_container_width=True
                )

    # ── Section: Problem Ladder ────────────────────
    st.divider()
    st.subheader("🪜 Problem Ladder — Solve This Before That")
    st.caption(
        "Sequenced learning path based on your current level. "
        "Follow this order to build skills systematically."
    )

    ladder = recs.get('ladder', {})
    if ladder:
        if ladder.get('ready'):
            st.info(f"🎯 **Next topic to master: `{ladder['next_topic']}`**")
            st.markdown(ladder.get('message', ''))

            ladder_problems = ladder.get('problems', [])
            if ladder_problems:
                for i, prob in enumerate(ladder_problems, 1):
                    with st.expander(
                        f"Step {i}: {prob['title']} "
                        f"(Rating: {prob['rating']})"
                    ):
                        st.markdown(f"**Tags:** {', '.join(prob['tags'])}")
                        st.caption(prob['reason'])
                        st.link_button(
                            "Solve →",
                            prob['cf_url'],
                            use_container_width=True
                        )
        else:
            st.warning(f"⚠️ {ladder.get('message', '')}")
            prereqs = ladder.get('prereq_problems', [])
            if prereqs:
                st.markdown("**Learn these first:**")
                for prob in prereqs:
                    col1, col2 = st.columns([3, 1])
                    with col1:
                        st.markdown(
                            f"**{prob['title']}** "
                            f"(Rating: {prob['rating']}) — "
                            f"{prob['reason']}"
                        )
                    with col2:
                        st.link_button(
                            "Solve →",
                            prob['cf_url'],
                            use_container_width=True
                        )
    else:
        st.info("Ladder will appear after problems are cached.")

    # ── Section: Topic Problem Sets ────────────────
    st.divider()
    st.subheader("📖 Topic Mastery Sets")
    st.caption(
        "Pick a topic and work through problems "
        "at increasing difficulty levels."
    )

    available_topics = [
        "dp", "graphs", "binary search", "dsu",
        "segment tree", "greedy", "strings",
        "trees", "math"
    ]
    weak_tags   = data.get('skill_profile', {}).get('weak', [])
    # Put weak tags first in the list
    ordered_topics = (
        [t for t in weak_tags if t in available_topics] +
        [t for t in available_topics if t not in weak_tags]
    )

    selected_topic = st.selectbox(
        "Choose a topic to master:",
        ordered_topics,
        index=0
    )

    if st.button(f"Load {selected_topic} Problem Set"):
        with st.spinner(f"Loading {selected_topic} problems..."):
            import requests
            handle   = st.session_state.get('handle', '')
            res      = requests.get(
                f"https://levelup-cp.onrender.com/api/topic-set/{handle}/{selected_topic}",
                timeout=30
            )

            if res.status_code == 200:
                topic_data = res.json()
                st.success(f"**{topic_data['title']}**")
                st.caption(topic_data['description'])

                topic_problems = topic_data.get('problems', [])
                if topic_problems:
                    for prob in topic_problems:
                        col1, col2, col3 = st.columns([3, 2, 1])
                        with col1:
                            st.markdown(f"**{prob['title']}**")
                        with col2:
                            st.caption(
                                f"Rating: {prob['rating']} — "
                                f"{prob.get('level_description', '')}"
                            )
                        with col3:
                            st.link_button(
                                "Solve →",
                                prob['cf_url'],
                                use_container_width=True
                            )
                else:
                    st.warning("No problems found for this topic at your level.")
            else:
                st.error("Could not load topic set.")

    # ── Section: Unsolved Contest Problems ─────────
    with st.expander("🏆 Unsolved Problems from Your Contests"):
        st.caption(
            "Problems you saw during live contests but never solved. "
            "Upsolving these is the highest-ROI practice you can do."
        )

        if st.button("Load Unsolved Contest Problems"):
            with st.spinner("Finding unsolved contest problems..."):
                import requests
                handle = st.session_state.get('handle', '')
                res    = requests.get(
                    f"https://levelup-cp.onrender.com/api/recommendations/{handle}",
                    timeout=60
                )
                if res.status_code == 200:
                    rec_data = res.json()
                    unsolved = rec_data.get('unsolved_contests', [])

                    if unsolved:
                        import pandas as pd
                        df = pd.DataFrame(unsolved)
                        if 'cf_url' in df.columns:
                            df = df.drop('cf_url', axis=1)
                        st.dataframe(df, use_container_width=True)
                    else:
                        st.info(
                            "No unsolved contest problems found. "
                            "Either you solved everything or no data available."
                        )

    # ── Section: Struggled Problems ────────────────
    with st.expander("😤 Problems You Struggled On (3+ WA/TLE)"):
        st.caption(
            "Problems where you made many wrong attempts. "
            "Understanding why you struggled reveals specific pattern gaps."
        )

        if st.button("Load Struggled Problems"):
            with st.spinner("Analyzing struggle patterns..."):
                import requests
                handle = st.session_state.get('handle', '')
                res    = requests.get(
                    f"https://levelup-cp.onrender.com/api/recommendations/{handle}",
                    timeout=60
                )
                if res.status_code == 200:
                    rec_data  = res.json()
                    struggled = rec_data.get('struggled', [])

                    if struggled:
                        for item in struggled[:8]:
                            col1, col2, col3, col4 = st.columns([2, 1, 1, 1])
                            with col1:
                                st.markdown(f"**{item['problem_id']}**")
                                st.caption(
                                    f"Tags: {', '.join(item['tags'][:2])}"
                                )
                            with col2:
                                st.metric(
                                    "WA",
                                    item['wa_count']
                                )
                            with col3:
                                st.metric(
                                    "TLE",
                                    item['tle_count']
                                )
                            with col4:
                                st.link_button(
                                    "Revisit →",
                                    item['cf_url'],
                                    use_container_width=True
                                )
                    else:
                        st.success(
                            "No heavily struggled problems found!"
                        )

# ── Section: Progressive Hint System ──────────────

if 'data' in st.session_state:

    st.divider()
    st.subheader("💡 Progressive Hint System")
    st.caption(
        "Stuck on a problem? Get hints one at a time. "
        "The system will never reveal the full solution."
    )

    handle = st.session_state.get('handle', '')

    # ── Problem Input ──────────────────────────────
    col1, col2 = st.columns([3, 1])

    with col1:
        problem_id = st.text_input(
            "Problem ID (any unique name for this problem)",
            placeholder = "e.g. 1234A or two-sum or contest-div2-C",
            key         = "hint_problem_id"
        )

    with col2:
        st.write("")
        st.write("")
        if st.button("🔄 Reset Hints", key="reset_hints_btn"):
            if problem_id and handle:
                res = requests.post(
                    f"{API}/hint/reset",
                    json    = {
                        "handle":     handle,
                        "problem_id": problem_id
                    },
                    timeout = 10
                )
                if res.status_code == 200:
                    # Clear session state for this problem
                    if 'hints_shown' in st.session_state:
                        del st.session_state['hints_shown']
                    st.success("Hints reset! Starting fresh.")
                    st.rerun()

    problem_text = st.text_area(
        "Paste the full problem statement here",
        placeholder = (
            "Paste the complete problem statement here...\n"
            "Include: problem description, input format, "
            "output format, constraints, and examples."
        ),
        height = 200,
        key    = "hint_problem_text"
    )

    # ── Restore Previous Hints ─────────────────────
    # When user comes back to same problem
    if problem_id and handle:
        if st.button("📜 Restore Previous Hints", key="restore_btn"):
            res = requests.get(
                f"{API}/hint/history/{handle}/{problem_id}",
                timeout = 10
            )
            if res.status_code == 200:
                history = res.json()
                if history['has_session']:
                    st.session_state['hints_shown'] = history['hints']
                    st.success(
                        f"Restored {len(history['hints'])} previous hints"
                    )
                else:
                    st.info("No previous hints found for this problem.")

    # ── Display Previously Given Hints ────────────
    if 'hints_shown' not in st.session_state:
        st.session_state['hints_shown'] = []

    if st.session_state['hints_shown']:
        st.markdown("**Hints given so far:**")
        for hint in st.session_state['hints_shown']:
            hint_num = hint['hint_number']

            if hint_num == 1:
                color = "🟡"
                label = "Hint 1 — Gentle Nudge"
            elif hint_num == 2:
                color = "🟠"
                label = "Hint 2 — Specific Direction"
            else:
                color = "🔴"
                label = "Hint 3 — Near Complete Approach"

            with st.expander(
                f"{color} {label}",
                expanded = (hint_num == len(st.session_state['hints_shown']))
            ):
                st.markdown(hint['hint_text'])

    # ── Get Next Hint Button ───────────────────────
    hints_so_far  = len(st.session_state['hints_shown'])
    max_hints     = 3
    hints_left    = max_hints - hints_so_far

    st.write("")

    # Show appropriate button based on hint level
    if hints_so_far == 0:
        btn_label = "💡 Get Hint 1"
        btn_help  = "Get a gentle nudge toward the right approach"
    elif hints_so_far == 1:
        btn_label = "💡 Get Hint 2"
        btn_help  = "Get a more specific direction"
    elif hints_so_far == 2:
        btn_label = "💡 Get Hint 3 (Final)"
        btn_help  = "Get the near-complete approach (no code)"
    else:
        btn_label = "🚫 No More Hints Available"
        btn_help  = "You have received all 3 hints"

    col1, col2, col3 = st.columns([2, 1, 2])

    with col1:
        get_hint_btn = st.button(
            btn_label,
            disabled        = (hints_so_far >= max_hints or not problem_text or not problem_id),
            use_container_width = True,
            type            = "primary" if hints_so_far < max_hints else "secondary",
            key             = "get_hint_btn"
        )

    with col2:
        # Progress indicator
        st.write("")
        if hints_so_far < max_hints:
            st.caption(
                f"{hints_left} hint{'s' if hints_left > 1 else ''} remaining"
            )
        else:
            st.caption("All hints used")

    # ── Handle Get Hint Click ──────────────────────
    if get_hint_btn:
        if not problem_text.strip():
            st.error("Please paste the problem statement first.")

        elif not problem_id.strip():
            st.error("Please enter a Problem ID first.")

        elif hints_so_far >= max_hints:
            st.warning(
                "You have already received all 3 hints. "
                "Try implementing Hint 3. You are closer than you think!"
            )

        else:
            with st.spinner(
                f"Generating Hint {hints_so_far + 1}... "
                f"(thinking like a coach)"
            ):
                try:
                    res = requests.post(
                        f"{API}/hint/next",
                        json = {
                            "handle":       handle,
                            "problem_id":   problem_id.strip(),
                            "problem_text": problem_text.strip()
                        },
                        timeout = 30
                    )

                    if res.status_code == 200:
                        result   = res.json()
                        hint_num = result['hint_number']
                        hint_txt = result['hint_text']
                        is_final = result['is_final']

                        # Add to shown hints
                        st.session_state['hints_shown'].append({
                            "hint_number": hint_num,
                            "hint_text":   hint_txt
                        })

                        # Show success message
                        if is_final:
                            st.success(
                                "💡 Final hint given! "
                                "Try implementing this approach. "
                                "You can do it!"
                            )
                        else:
                            remaining = result.get('hints_remaining', 0)
                            st.info(
                                f"Hint {hint_num} ready. "
                                f"{remaining} more hint{'s' if remaining > 1 else ''} "
                                f"available if needed."
                            )

                        # Rerun to show new hint
                        st.rerun()

                    elif res.status_code == 400:
                        st.error(res.json().get('detail', 'Invalid request'))

                    else:
                        st.error(
                            "Failed to generate hint. "
                            "Check if Gemini API key is set correctly."
                        )

                except requests.exceptions.Timeout:
                    st.error(
                        "Request timed out. "
                        "Gemini is taking too long. Try again."
                    )
                except requests.exceptions.ConnectionError:
                    st.error(
                        "Cannot connect to backend. "
                        "Make sure FastAPI is running."
                    )

    # ── Hint Usage Tips ────────────────────────────
    with st.expander("ℹ️ How to use hints effectively"):
        st.markdown("""
        **Best practices for using the hint system:**

        1. **Try for at least 20-30 minutes before asking for Hint 1.**
           The struggle is where learning happens.

        2. **After each hint, close this panel and try again.**
           Don't rush to the next hint immediately.

        3. **Hint 1** gives you the general direction.
           If you can figure it out from here, you've learned the most.

        4. **Hint 2** gives you the specific algorithm category.
           Try to implement it before asking for Hint 3.

        5. **Hint 3** is near the full approach.
           If you still can't implement after Hint 3, read the editorial.

        6. **After solving**, upsolve similar problems.
           Check your Daily Recommendations for suggestions.
        """)