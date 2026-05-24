from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import pandas as pd
import json
import httpx
import os

from backend.config import GROQ_API_KEY, GROQ_MODEL, GROQ_API_URL
from backend.database import ingest_pipeline, db_exists, get_schema, get_sample_rows, run_query

app = FastAPI(title="EduPulse API", version="1.0.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

class NLQueryRequest(BaseModel):
    question: str

def to_python(obj):
    """Convert numpy types to plain Python for JSON serialization."""
    import numpy as np
    if isinstance(obj, (np.integer,)):
        return int(obj)
    if isinstance(obj, (np.floating,)):
        return float(obj)
    if isinstance(obj, np.ndarray):
        return obj.tolist()
    return obj

def build_schema_context():
    schema = get_schema()
    lines = ["You have access to a SQLite database with these tables:\n"]
    for table, info in schema.items():
        cols = ", ".join([f"{c['name']} ({c['type']})" for c in info["columns"]])
        lines.append(f"TABLE: {table} ({info['row_count']} rows)")
        lines.append(f"  COLUMNS: {cols}")
        samples = get_sample_rows(table, n=2)
        if samples:
            lines.append(f"  SAMPLE ROW: {json.dumps(samples[0])}")
        lines.append("")
    return "\n".join(lines)

async def call_groq(system_prompt, user_message, temperature=0.1):
    if not GROQ_API_KEY:
        raise HTTPException(status_code=500, detail="GROQ_API_KEY not set.")
    headers = {"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"}
    payload = {
        "model": GROQ_MODEL,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ],
        "temperature": temperature,
        "max_tokens": 1024,
    }
    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.post(GROQ_API_URL, headers=headers, json=payload)
        response.raise_for_status()
        return response.json()["choices"][0]["message"]["content"].strip()

@app.get("/")
def root():
    return {"status": "EduPulse API running", "db_ready": db_exists()}

@app.post("/ingest")
def ingest():
    try:
        audit = ingest_pipeline()
        return {"status": "success", "audit": audit}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/schema")
def schema():
    if not db_exists():
        raise HTTPException(status_code=400, detail="Call /ingest first.")
    return get_schema()

@app.get("/profile")
def profile():
    if not db_exists():
        raise HTTPException(status_code=400, detail="Call /ingest first.")
    schema = get_schema()
    profile_data = {}
    total_cells = 0
    null_cells = 0
    for table in schema:
        try:
            df = run_query(f"SELECT * FROM {table}")
            null_counts = df.isnull().sum().to_dict()
            null_pct = {col: round(n / len(df) * 100, 1) for col, n in null_counts.items() if n > 0}
            total_cells += df.size
            null_cells += int(df.isnull().sum().sum())
            profile_data[table] = {
                "rows": len(df),
                "columns": len(df.columns),
                "null_percentages": null_pct,
                "completeness_score": round((1 - df.isnull().sum().sum() / df.size) * 100, 1),
            }
        except Exception as e:
            profile_data[table] = {"error": str(e)}
    overall_health = round((1 - null_cells / total_cells) * 100, 1) if total_cells > 0 else 0
    return {"overall_health_score": overall_health, "tables": profile_data}

@app.post("/query")
async def nl_query(request: NLQueryRequest):
    if not db_exists():
        raise HTTPException(status_code=400, detail="Call /ingest first.")
    schema_context = build_schema_context()
    system_prompt = f"""You are a SQL expert for an education nonprofit database.
Convert natural language questions into correct SQLite SQL queries.

{schema_context}

RULES:
- Return ONLY the SQL query, nothing else. No explanation, no markdown, no backticks.
- Use LOWER() for string comparisons.
- Limit results to 100 rows unless asking for aggregates.
- attendance_rate is stored as decimals (0.83 = 83%).
- grade_level values are like '6th', '7th', etc.
- Pre/Post scores are in the assessment_period column.
- assessments table has NO program column. To get program per student, JOIN assessments with enrollments on student_id, then use enrollments.program_name.
- To find math improvement: AVG(post.score) - AVG(pre.score) by joining assessments twice filtering by assessment_period.
- Example: SELECT e.program_name, AVG(CASE WHEN a.assessment_period='Post' THEN a.score END) - AVG(CASE WHEN a.assessment_period='Pre' THEN a.score END) as improvement FROM assessments a JOIN enrollments e ON a.student_id = e.student_id GROUP BY e.program_name ORDER BY improvement DESC
- assessments table has NO program column. To get program per student, JOIN assessments with enrollments on student_id, then use enrollments.program_name.
- To find math improvement: AVG(post.score) - AVG(pre.score) by joining assessments twice filtering by assessment_period.
- Example: SELECT e.program_name, AVG(CASE WHEN a.assessment_period='Post' THEN a.score END) - AVG(CASE WHEN a.assessment_period='Pre' THEN a.score END) as improvement FROM assessments a JOIN enrollments e ON a.student_id = e.student_id GROUP BY e.program_name ORDER BY improvement DESC
- Always use simple column aliases with no spaces e.g. avg_score not avg(score).
"""
    try:
        sql = await call_groq(system_prompt, f"Question: {request.question}", temperature=0.0)
        sql = sql.replace("```sql", "").replace("```", "").strip()
        if not sql.upper().strip().startswith("SELECT"):
            raise HTTPException(status_code=400, detail="Only SELECT queries allowed.")
        df = run_query(sql)
        return {
            "question": request.question,
            "sql": sql,
            "rows": len(df),
            "columns": list(df.columns),
            "data": df.to_dict(orient="records"),
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Query failed: {str(e)}")

@app.get("/insights/overview")
async def insights_overview():
    if not db_exists():
        raise HTTPException(status_code=400, detail="Call /ingest first.")
    try:
        total_students = int(run_query("SELECT COUNT(DISTINCT student_id) as n FROM students").iloc[0]["n"])
        sites = run_query("SELECT site, COUNT(*) as student_count FROM students WHERE site IS NOT NULL GROUP BY site ORDER BY student_count DESC").to_dict(orient="records")
        programs = run_query("SELECT program_name, COUNT(*) as enrolled FROM enrollments WHERE program_name IS NOT NULL GROUP BY program_name ORDER BY enrolled DESC").to_dict(orient="records")
        avg_math_pre = float(run_query("SELECT ROUND(AVG(CAST(score AS FLOAT)),1) as avg_score FROM assessments WHERE subject='Math' AND assessment_period='Pre' AND score IS NOT NULL").iloc[0]["avg_score"] or 0)
        avg_math_post = float(run_query("SELECT ROUND(AVG(CAST(score AS FLOAT)),1) as avg_score FROM assessments WHERE subject='Math' AND assessment_period='Post' AND score IS NOT NULL").iloc[0]["avg_score"] or 0)
        avg_att = float(run_query("SELECT ROUND(AVG(CAST(attendance_rate AS FLOAT))*100,1) as avg_att FROM attendance WHERE attendance_rate IS NOT NULL").iloc[0]["avg_att"] or 0)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Stats query failed: {str(e)}")

    stats_context = f"""
Total students: {total_students}
Sites: {sites}
Programs: {programs}
Avg Math Pre-score: {avg_math_pre}
Avg Math Post-score: {avg_math_post}
Avg attendance rate: {avg_att}%
"""
    system_prompt = """You are a data analyst writing for an education nonprofit grant report.
Write a professional 3-paragraph program overview based on the stats provided.
Use specific numbers. Be honest about gaps. Clear human tone, no jargon.
Do not invent numbers not provided."""
    narrative = await call_groq(system_prompt, stats_context, temperature=0.4)
    return {
        "narrative": narrative,
        "stats": {
            "total_students": total_students,
            "sites": sites,
            "programs": programs,
            "avg_math_pre": avg_math_pre,
            "avg_math_post": avg_math_post,
            "avg_attendance_pct": avg_att,
        }
    }

@app.get("/insights/data-quality-report")
async def data_quality_narrative():
    if not db_exists():
        raise HTTPException(status_code=400, detail="Call /ingest first.")
    profile_data = profile()
    system_prompt = """You are a data consultant presenting a data quality audit to a nonprofit program director.
Write a plain-English summary of data quality issues. Be specific — mention table names, column names, percentages.
Prioritize the most impactful issues. End with 3 concrete recommended fixes.
Tone: professional but direct. This person is not a data expert."""
    narrative = await call_groq(
        system_prompt,
        f"Audit results:\n{json.dumps(profile_data, indent=2)}",
        temperature=0.3
    )
    return {"narrative": narrative, "profile": profile_data}
