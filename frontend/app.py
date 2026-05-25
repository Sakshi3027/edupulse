import streamlit as st
import requests
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import json

API = "http://localhost:8000"

st.set_page_config(
    page_title="EduPulse",
    page_icon="🎓",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ─── SIDEBAR ──────────────────────────────────────────────────────────────────
st.sidebar.image("https://img.icons8.com/fluency/96/graduation-cap.png", width=60)
st.sidebar.title("EduPulse")
st.sidebar.caption("AI-powered data intelligence for education nonprofits")

page = st.sidebar.radio("Navigate", [
    "🏠 Overview",
    "🔍 Data Quality Audit",
    "💬 Ask Your Data",
    "📊 Program Analytics",
    "📄 Grant Report",
    "📁 Upload Your Data",
])

st.sidebar.divider()

# Ingest button in sidebar
if st.sidebar.button("🔄 Re-ingest Data", use_container_width=True):
    with st.spinner("Ingesting and cleaning CSVs..."):
        r = requests.post(f"{API}/ingest")
        if r.status_code == 200:
            st.sidebar.success("Data ingested successfully!")
        else:
            st.sidebar.error(f"Error: {r.text}")

# ─── HELPER ───────────────────────────────────────────────────────────────────
def check_db():
    try:
        r = requests.get(f"{API}/")
        return r.json().get("db_ready", False)
    except:
        return False

def get_profile():
    r = requests.get(f"{API}/profile")
    return r.json() if r.status_code == 200 else None

def get_schema():
    r = requests.get(f"{API}/schema")
    return r.json() if r.status_code == 200 else None

# ─── PAGE: OVERVIEW ───────────────────────────────────────────────────────────
if page == "🏠 Overview":
    st.title("🎓 EduPulse — Program Intelligence Platform")
    st.caption("Turning messy nonprofit data into grant-ready insights")

    if not check_db():
        st.warning("⚠️ Database not initialized. Click **Re-ingest Data** in the sidebar to get started.")
        st.stop()

    with st.spinner("Loading insights..."):
        r = requests.get(f"{API}/insights/overview")

    if r.status_code != 200:
        st.error(f"Error loading insights: {r.text}")
        st.stop()

    data = r.json()
    stats = data["stats"]

    # KPI row
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Total Students", stats["total_students"])
    col2.metric("Avg Math Growth",
        f"+{round(float(stats['avg_math_post'] or 0) - float(stats['avg_math_pre'] or 0), 1)} pts",
        delta_color="normal"
    )
    col3.metric("Avg Attendance", f"{stats['avg_attendance_pct']}%")
    col4.metric("Programs Running", len(stats["programs"]))

    st.divider()

    col_left, col_right = st.columns(2)

    with col_left:
        st.subheader("Students by Site")
        site_df = pd.DataFrame(stats["sites"])
        if not site_df.empty:
            fig = px.bar(site_df, x="site", y="student_count", color="student_count",
                        color_continuous_scale="Blues",
                        labels={"n": "Students", "site": "Site"})
            fig.update_layout(showlegend=False, height=300, margin=dict(t=20))
            st.plotly_chart(fig, use_container_width=True)

    with col_right:
        st.subheader("Enrollment by Program")
        prog_df = pd.DataFrame(stats["programs"])
        if not prog_df.empty:
            fig = px.pie(prog_df, names="program_name", values="enrolled",
                        color_discrete_sequence=px.colors.qualitative.Set3)
            fig.update_layout(height=300, margin=dict(t=20))
            st.plotly_chart(fig, use_container_width=True)

    st.divider()
    st.subheader("📝 AI-Generated Program Narrative")
    st.info(data["narrative"])

# ─── PAGE: DATA QUALITY ───────────────────────────────────────────────────────
elif page == "🔍 Data Quality Audit":
    st.title("🔍 Data Quality Audit")
    st.caption("This is what an FDE finds on day one — before anything can work.")

    if not check_db():
        st.warning("Click **Re-ingest Data** in the sidebar first.")
        st.stop()

    with st.spinner("Running data quality scan..."):
        profile = get_profile()

    if not profile:
        st.error("Could not load profile.")
        st.stop()

    # Overall health score
    score = profile["overall_health_score"]
    color = "green" if score > 85 else "orange" if score > 70 else "red"
    st.markdown(f"### Overall Data Health: :{color}[{score}%]")

    fig = go.Figure(go.Indicator(
        mode="gauge+number",
        value=score,
        gauge={
            "axis": {"range": [0, 100]},
            "bar": {"color": "#4CAF50" if score > 85 else "#FF9800" if score > 70 else "#F44336"},
            "steps": [
                {"range": [0, 60], "color": "#ffebee"},
                {"range": [60, 80], "color": "#fff3e0"},
                {"range": [80, 100], "color": "#e8f5e9"},
            ],
        },
        title={"text": "Data Completeness Score"},
    ))
    fig.update_layout(height=280, margin=dict(t=40, b=0))
    st.plotly_chart(fig, use_container_width=True)

    st.divider()
    st.subheader("Issues by Table")

    for table, info in profile["tables"].items():
        if "error" in info:
            continue
        completeness = info["completeness_score"]
        null_pct = info["null_percentages"]

        with st.expander(f"**{table}** — {info['rows']} rows — Completeness: {completeness}%", expanded=completeness < 90):
            if not null_pct:
                st.success("✅ No missing values detected")
            else:
                null_df = pd.DataFrame([
                    {"Column": col, "Missing %": pct}
                    for col, pct in null_pct.items()
                ]).sort_values("Missing %", ascending=False)

                fig = px.bar(null_df, x="Column", y="Missing %",
                            color="Missing %",
                            color_continuous_scale=["green", "orange", "red"],
                            range_color=[0, 50])
                fig.update_layout(height=250, margin=dict(t=10))
                st.plotly_chart(fig, use_container_width=True)

    st.divider()
    st.subheader("🤖 AI Data Quality Narrative")
    st.caption("What you'd tell the program director in plain English")

    if st.button("Generate Data Quality Report"):
        with st.spinner("Analyzing issues and generating report..."):
            r = requests.get(f"{API}/insights/data-quality-report")
        if r.status_code == 200:
            st.info(r.json()["narrative"])
        else:
            st.error(r.text)

# ─── PAGE: ASK YOUR DATA ──────────────────────────────────────────────────────
elif page == "💬 Ask Your Data":
    st.title("💬 Ask Your Data")
    st.caption("Type a question in plain English. Ask follow-ups like a real analyst.")

    if not check_db():
        st.warning("Click **Re-ingest Data** in the sidebar first.")
        st.stop()

    # Initialize conversation memory
    if "chat_history" not in st.session_state:
        st.session_state.chat_history = []
    if "last_result" not in st.session_state:
        st.session_state.last_result = None

    # Example questions
    st.markdown("**Try asking:**")
    examples = [
        "How many students are enrolled at each site?",
        "Which program has the highest average math improvement?",
        "What is the average attendance rate by program?",
        "How many students are in each grade level?",
        "Which site has the lowest attendance rate?",
    ]
    cols = st.columns(len(examples))
    selected_example = None
    for i, ex in enumerate(examples):
        if cols[i].button(ex, key=f"ex_{i}", use_container_width=True):
            selected_example = ex

    st.divider()

    # Show conversation history
    if st.session_state.chat_history:
        st.subheader("Conversation")
        for turn in st.session_state.chat_history:
            with st.chat_message("user"):
                st.write(turn["question"])
            with st.chat_message("assistant"):
                st.success(f"Found **{turn['rows']} rows**")
                with st.expander("SQL", expanded=False):
                    attempts_note = f" *(fixed in {turn['attempts']} attempts)*" if turn.get("attempts", 1) > 1 else ""
                    st.code(turn["sql"] + attempts_note, language="sql")
                if turn["data"]:
                    df = pd.DataFrame(turn["data"])
                    st.dataframe(df, use_container_width=True)
                    if len(df.columns) == 2:
                        num_cols = df.select_dtypes(include="number").columns.tolist()
                        str_cols = df.select_dtypes(exclude="number").columns.tolist()
                        if num_cols and str_cols:
                            fig = px.bar(df, x=str_cols[0], y=num_cols[0],
                                        color=num_cols[0], color_continuous_scale="Blues")
                            fig.update_layout(height=300, margin=dict(t=10))
                            st.plotly_chart(fig, use_container_width=True)

        if st.button("🗑️ Clear conversation", type="secondary"):
            st.session_state.chat_history = []
            st.session_state.last_result = None
            st.rerun()

        st.divider()

    # Build context from last result for follow-up questions
    followup_context = ""
    if st.session_state.last_result:
        last = st.session_state.last_result
        followup_context = f"\n\nCONTEXT FROM PREVIOUS QUESTION: The user previously asked: \"{last['question']}\" and got this result with columns: {last['columns']}. Use this context for follow-up questions."

    question = st.text_input(
        "Your question:" if not st.session_state.chat_history else "Follow-up or new question:",
        value=selected_example or "",
        placeholder="e.g. Now show me just the 9th graders in that program"
    )

    if st.button("Ask", type="primary") and question:
        # Pass conversation context
        full_question = question + followup_context
        with st.spinner("Thinking..."):
            r = requests.post(f"{API}/query", json={"question": full_question})

        if r.status_code == 200:
            result = r.json()
            result["question"] = question  # store clean question
            st.session_state.chat_history.append(result)
            st.session_state.last_result = result
            st.rerun()
        else:
            st.error(f"Error: {r.json().get('detail', r.text)}")

# ─── PAGE: PROGRAM ANALYTICS ──────────────────────────────────────────────────
elif page == "📊 Program Analytics":
    st.title("📊 Program Analytics")

    if not check_db():
        st.warning("Click **Re-ingest Data** in the sidebar first.")
        st.stop()

    tab1, tab2, tab3 = st.tabs(["Assessment Scores", "Attendance", "Enrollment"])

    with tab1:
        st.subheader("Math & Reading Score: Pre vs Post")
        r = requests.post(f"{API}/query", json={
            "question": "Show average score by subject and assessment_period"
        })
        if r.status_code == 200:
            df = pd.DataFrame(r.json()["data"])
            if not df.empty:
                fig = px.bar(df, x="subject", y="avg_score",
                            color="assessment_period", barmode="group",
                            color_discrete_map={"Pre": "#90CAF9", "Post": "#1565C0"},
                            labels={"avg(score)": "Avg Score"})
                fig.update_layout(height=350)
                st.plotly_chart(fig, use_container_width=True)

    with tab2:
        st.subheader("Attendance Rate by Site")
        r = requests.post(f"{API}/query", json={
            "question": "Show average attendance rate by student site, join students and attendance tables"
        })
        if r.status_code == 200 and r.json()["rows"] > 0:
            df = pd.DataFrame(r.json()["data"])
            st.dataframe(df, use_container_width=True)
        else:
            st.info("Run a custom query in 'Ask Your Data' to explore attendance.")

    with tab3:
        st.subheader("Enrollment Status Breakdown")
        r = requests.post(f"{API}/query", json={
            "question": "Count enrollments by status"
        })
        if r.status_code == 200:
            df = pd.DataFrame(r.json()["data"])
            if not df.empty:
                fig = px.pie(df, names=df.columns[0], values=df.columns[1],
                            color_discrete_sequence=px.colors.qualitative.Pastel)
                fig.update_layout(height=350)
                st.plotly_chart(fig, use_container_width=True)

# ─── PAGE: GRANT REPORT ───────────────────────────────────────────────────────
elif page == "📄 Grant Report":
    st.title("📄 Grant Report Generator")
    st.caption("Generate a grant-ready narrative from your program data in one click.")

    if not check_db():
        st.warning("Click **Re-ingest Data** in the sidebar first.")
        st.stop()

    st.markdown("""
    This generates the kind of program summary paragraph that goes into a grant report.
    Based on real data — not a template.
    """)

    if st.button("Generate Grant Narrative", type="primary"):
        with st.spinner("Pulling stats and generating narrative..."):
            r = requests.get(f"{API}/insights/overview")

        if r.status_code == 200:
            data = r.json()
            stats = data["stats"]

            st.divider()
            col1, col2, col3 = st.columns(3)
            col1.metric("Students Served", stats["total_students"])
            col2.metric("Math Score Growth",
                f"+{round(float(stats['avg_math_post'] or 0) - float(stats['avg_math_pre'] or 0), 1)} pts")
            col3.metric("Avg Attendance", f"{stats['avg_attendance_pct']}%")

            st.divider()
            st.subheader("Generated Narrative")
            st.markdown(data["narrative"])

            st.divider()
            st.download_button(
                label="📥 Download as .txt",
                data=data["narrative"],
                file_name="grant_narrative.txt",
                mime="text/plain"
            )
        else:
            st.error(f"Error: {r.text}")

# ─── PAGE: CSV UPLOAD ─────────────────────────────────────────────────────────
elif page == "📁 Upload Your Data":
    st.title("📁 Upload Your Own Data")
    st.caption("Drop in any messy CSV. EduPulse will profile it, clean it, and let you query it.")

    uploaded_file = st.file_uploader("Upload a CSV file", type=["csv"])

    if uploaded_file:
        import io

        # Load raw
        raw_df = pd.read_csv(uploaded_file, dtype=str)
        st.success(f"Loaded **{len(raw_df)} rows** and **{len(raw_df.columns)} columns**")

        st.subheader("Raw Data Preview")
        st.dataframe(raw_df.head(10), use_container_width=True)

        st.divider()
        st.subheader("🔍 Auto Data Profile")

        # Profile
        profile = {}
        total = raw_df.size
        null_total = int(raw_df.isnull().sum().sum())
        health = round((1 - null_total / total) * 100, 1) if total > 0 else 0

        col1, col2, col3 = st.columns(3)
        col1.metric("Rows", len(raw_df))
        col2.metric("Columns", len(raw_df.columns))
        col3.metric("Data Health", f"{health}%")

        # Null rates per column
        null_pct = {col: round(raw_df[col].isnull().sum() / len(raw_df) * 100, 1)
                    for col in raw_df.columns if raw_df[col].isnull().sum() > 0}

        if null_pct:
            st.markdown("**Missing Values by Column:**")
            null_df = pd.DataFrame([
                {"Column": c, "Missing %": p}
                for c, p in null_pct.items()
            ]).sort_values("Missing %", ascending=False)
            fig = px.bar(null_df, x="Column", y="Missing %",
                        color="Missing %",
                        color_continuous_scale=["green", "orange", "red"],
                        range_color=[0, 50])
            fig.update_layout(height=300, margin=dict(t=10))
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.success("✅ No missing values detected")

        # Duplicate detection
        dupe_count = int(raw_df.duplicated().sum())
        if dupe_count > 0:
            st.warning(f"⚠️ Found **{dupe_count} duplicate rows**")
        else:
            st.success("✅ No duplicate rows detected")

        # Value variety per column
        st.markdown("**Unique Values per Column:**")
        unique_df = pd.DataFrame([
            {"Column": col, "Unique Values": raw_df[col].nunique(),
             "Sample Values": ", ".join(raw_df[col].dropna().unique()[:3].tolist())}
            for col in raw_df.columns
        ])
        st.dataframe(unique_df, use_container_width=True)

        st.divider()
        st.subheader("🤖 AI Data Profile Narrative")
        if st.button("Generate AI Profile", type="primary"):
            profile_summary = {
                "rows": len(raw_df),
                "columns": list(raw_df.columns),
                "health_score": health,
                "null_percentages": null_pct,
                "duplicate_rows": dupe_count,
                "sample_values": {col: raw_df[col].dropna().unique()[:3].tolist()
                                 for col in raw_df.columns},
            }
            with st.spinner("Analyzing your data..."):
                r = requests.post(
                    f"{API}/insights/data-quality-report",
                    json={"profile": profile_summary}
                )
                # Use direct Groq call via backend
                narrative_r = requests.get(f"{API}/insights/data-quality-report")
            if narrative_r.status_code == 200:
                st.info(narrative_r.json().get("narrative", ""))

        st.divider()
        st.subheader("💬 Query This Data")
        st.caption("EduPulse will load your CSV into a temporary table and let you ask questions.")

        if st.button("Load into Query Engine", type="primary"):
            # Save to temp DB
            clean_df = raw_df.copy()
            clean_df.columns = [c.lower().replace(" ", "_").replace("-", "_") for c in clean_df.columns]
            clean_df = clean_df.drop_duplicates()

            import sqlite3
            conn = sqlite3.connect("/tmp/uploaded.db") if not check_db() else sqlite3.connect("/tmp/edupulse.db")

            # Use a fixed table name
            table_name = uploaded_file.name.replace(".csv", "").replace("-", "_").replace(" ", "_").lower()
            clean_df.to_sql(table_name, sqlite3.connect("/tmp/uploaded_data.db"), if_exists="replace", index=False)

            st.session_state["uploaded_table"] = table_name
            st.session_state["uploaded_db"] = "/tmp/uploaded_data.db"
            st.success(f"✅ Loaded as table `{table_name}` — go to **Ask Your Data** to query it, or ask below.")

        if "uploaded_table" in st.session_state:
            st.info(f"Table `{st.session_state['uploaded_table']}` is loaded. Ask a question:")
            q = st.text_input("Your question about this data:", key="csv_query")
            if st.button("Ask", key="csv_ask") and q:
                import sqlite3, json as _json
                conn = sqlite3.connect(st.session_state["uploaded_db"])
                cursor = conn.cursor()
                cursor.execute(f"PRAGMA table_info({st.session_state['uploaded_table']})")
                cols = [row[1] for row in cursor.fetchall()]
                cursor.execute(f"SELECT * FROM {st.session_state['uploaded_table']} LIMIT 2")
                sample = cursor.fetchall()
                conn.close()

                schema_ctx = f"TABLE: {st.session_state['uploaded_table']}\nCOLUMNS: {cols}\nSAMPLE: {sample}"

                r = requests.post(f"{API}/query", json={
                    "question": q + f"\n\nSCHEMA CONTEXT: {schema_ctx}\nNote: query the table named '{st.session_state['uploaded_table']}' in the database."
                })
                if r.status_code == 200:
                    result = r.json()
                    st.success(f"Found {result['rows']} rows")
                    with st.expander("SQL"):
                        st.code(result["sql"], language="sql")
                    st.dataframe(pd.DataFrame(result["data"]), use_container_width=True)
                else:
                    st.error(r.json().get("detail", "Query failed"))
