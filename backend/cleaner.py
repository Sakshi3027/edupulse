import pandas as pd
import numpy as np
from datetime import datetime

DATE_FORMATS = [
    "%Y-%m-%d", "%m/%d/%Y", "%m-%d-%Y",
    "%d %b %Y", "%B %d, %Y", "%b %d, %Y",
    "%d-%b-%Y", "%Y/%m/%d", "%d/%m/%Y",
]

def parse_date(val):
    if pd.isna(val) or str(val).strip() in ("", "nan", "None"):
        return None
    val = str(val).strip()
    for fmt in DATE_FORMATS:
        try:
            return datetime.strptime(val, fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    return None

GRADE_MAP = {
    "6": "6th", "grade 6": "6th", "g6": "6th", "sixth": "6th",
    "7": "7th", "grade 7": "7th", "g7": "7th", "seventh": "7th",
    "8": "8th", "grade 8": "8th", "g8": "8th", "eighth": "8th",
    "9": "9th", "grade 9": "9th", "g9": "9th", "freshman": "9th",
    "10": "10th", "grade 10": "10th", "g10": "10th", "sophomore": "10th",
    "11": "11th", "grade 11": "11th", "g11": "11th", "junior": "11th",
    "12": "12th", "grade 12": "12th", "g12": "12th", "senior": "12th",
}

def normalize_grade(val):
    if pd.isna(val):
        return None
    return GRADE_MAP.get(str(val).strip().lower(), str(val).strip())

def normalize_status(val):
    if pd.isna(val):
        return None
    v = str(val).strip().lower()
    if v in ("active", "1", "true", "enrolled"):
        return "Active"
    if v in ("completed", "complete", "done", "graduated"):
        return "Completed"
    if v in ("dropped", "dropout", "inactive", "withdrawn", "0", "false"):
        return "Dropped"
    return str(val).strip().title()

def normalize_bool(val):
    if pd.isna(val):
        return None
    v = str(val).strip().lower()
    if v in ("yes", "y", "1", "true"):
        return 1
    if v in ("no", "n", "0", "false"):
        return 0
    return None

def normalize_attendance_rate(val):
    if pd.isna(val):
        return None
    val = str(val).strip()
    if val.endswith("%"):
        try:
            return round(float(val[:-1]) / 100, 4)
        except ValueError:
            return None
    try:
        f = float(val)
        return round(f if f <= 1.0 else f / 100, 4)
    except ValueError:
        return None

def normalize_name(val):
    if pd.isna(val) or str(val).strip() == "":
        return None
    val = str(val).strip()
    if "," in val:
        parts = val.split(",", 1)
        val = f"{parts[1].strip()} {parts[0].strip()}"
    return val.title()

def deduplicate(df, id_col="student_id"):
    dupe_report = df[df.duplicated(subset=[id_col], keep=False)].copy()
    clean = df.drop_duplicates(subset=[id_col], keep="first").copy()
    return clean, dupe_report

def clean_students(df):
    issues = {}
    df["student_name"] = df["student_name"].apply(normalize_name)
    df["date_of_birth"] = df["date_of_birth"].apply(parse_date)
    df["enrollment_date"] = df["enrollment_date"].apply(parse_date)
    df["grade_level"] = df["grade_level"].apply(normalize_grade)
    df["free_reduced_lunch"] = df["free_reduced_lunch"].apply(normalize_bool)
    before = len(df)
    df, dupe_report = deduplicate(df, "student_id")
    issues["duplicates_removed"] = before - len(df)
    issues["null_counts"] = df.isnull().sum().to_dict()
    return df, issues

def clean_enrollments(df):
    issues = {}
    df["start_date"] = df["start_date"].apply(parse_date)
    df["end_date"] = df["end_date"].apply(parse_date)
    df["status"] = df["status"].apply(normalize_status)
    if "program_name" in df.columns and "program" in df.columns:
        df["program_name"] = df["program_name"].fillna(df["program"])
        df.drop(columns=["program"], inplace=True)
    issues["null_counts"] = df.isnull().sum().to_dict()
    issues["status_values"] = df["status"].value_counts().to_dict()
    return df, issues

def clean_attendance(df):
    issues = {}
    df["week_of"] = df["week_of"].apply(parse_date)
    df["attendance_rate"] = df["attendance_rate"].apply(normalize_attendance_rate)
    issues["null_counts"] = df.isnull().sum().to_dict()
    return df, issues

def clean_assessments(df):
    issues = {}
    df["score"] = pd.to_numeric(df["score"], errors="coerce")
    df["percentile"] = pd.to_numeric(df["percentile"], errors="coerce")
    issues["null_counts"] = df.isnull().sum().to_dict()
    return df, issues

def clean_grants(df):
    issues = {}
    df["report_due_date"] = df["report_due_date"].apply(parse_date)
    issues["null_counts"] = df.isnull().sum().to_dict()
    return df, issues

def clean_staff(df):
    issues = {}
    df["hire_date"] = df["hire_date"].apply(parse_date)
    df["name"] = df["name"].apply(normalize_name)
    issues["null_counts"] = df.isnull().sum().to_dict()
    return df, issues

CLEANERS = {
    "students": clean_students,
    "enrollments": clean_enrollments,
    "attendance": clean_attendance,
    "assessments": clean_assessments,
    "grants": clean_grants,
    "staff": clean_staff,
}

def run_all_cleaners(raw_dfs):
    clean_dfs = {}
    audit = {}
    for name, df in raw_dfs.items():
        if name in CLEANERS:
            clean_df, issues = CLEANERS[name](df.copy())
            clean_dfs[name] = clean_df
            audit[name] = {"rows_before": len(df), "rows_after": len(clean_df), "issues": issues}
        else:
            clean_dfs[name] = df
            audit[name] = {"rows_before": len(df), "rows_after": len(df), "issues": {}}
    return clean_dfs, audit
