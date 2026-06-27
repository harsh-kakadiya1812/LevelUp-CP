import streamlit as st
import requests
import plotly.graph_objects as go
import plotly.express as px
import pandas as pd

API = "http://localhost:8000/api"

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