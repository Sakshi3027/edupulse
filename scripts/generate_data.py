"""
EduPulse — Synthetic Messy Education Data Generator
Simulates the real chaos an FDE finds on day one at a nonprofit.
"""

import pandas as pd
import numpy as np
from faker import Faker
import random
import os
from datetime import datetime, timedelta

fake = Faker()
random.seed(42)
np.random.seed(42)

OUTPUT_DIR = os.path.join(os.path.dirname(__file__), '..', 'data', 'raw')
os.makedirs(OUTPUT_DIR, exist_ok=True)

# ─── CONFIG ───────────────────────────────────────────────────────────────────
N_STUDENTS = 300
PROGRAMS = ['STEM Bootcamp', 'Literacy First', 'College Prep 101', 'After School Math', 'Summer Bridge']
SITES = ['South Side', 'West Loop', 'Pilsen', 'Englewood', 'Hyde Park']
ETHNICITIES = ['Hispanic', 'Black or African American', 'White', 'Asian', 'Multiracial', None]
GRADE_LEVELS = ['6th', '7th', '8th', '9th', '10th', '11th', '12th', 'Grade 6', 'G7', 'eighth']  # intentional mess


# ─── HELPER: messy name formats ───────────────────────────────────────────────
def messy_name(first, last):
    """Simulate how real orgs store names — inconsistently."""
    formats = [
        f"{first} {last}",
        f"{last}, {first}",
        f"{first.lower()} {last.lower()}",
        f"{first.upper()} {last.upper()}",
        f"{first[0]}. {last}",
        f"{first} {last[0]}.",
    ]
    return random.choice(formats)


def messy_date(dt):
    """Multiple date formats in the same column — classic nonprofit CSV."""
    formats = ['%Y-%m-%d', '%m/%d/%Y', '%m-%d-%Y', '%d %b %Y', '%B %d, %Y']
    return dt.strftime(random.choice(formats))


def maybe_null(value, null_rate=0.12):
    """Randomly introduce missing values."""
    return None if random.random() < null_rate else value


def messy_grade(grade):
    """Same grade level stored 3 different ways."""
    if random.random() < 0.3:
        return grade
    variants = {
        '6th': ['Grade 6', 'G6', '6'],
        '7th': ['Grade 7', 'G7', '7'],
        '8th': ['Grade 8', 'eighth', '8'],
        '9th': ['Grade 9', 'freshman', '9'],
        '10th': ['Grade 10', 'sophomore', '10'],
        '11th': ['Grade 11', 'junior', '11'],
        '12th': ['Grade 12', 'senior', '12'],
    }
    return random.choice(variants.get(grade, [grade]))


# ─── 1. STUDENTS TABLE (2023-24) ──────────────────────────────────────────────
def generate_students_2024():
    rows = []
    student_ids = [f"STU{str(i).zfill(4)}" for i in range(1, N_STUDENTS + 1)]

    for sid in student_ids:
        first = fake.first_name()
        last = fake.last_name()
        dob_dt = fake.date_of_birth(minimum_age=11, maximum_age=19)
        grade = random.choice(['6th', '7th', '8th', '9th', '10th', '11th', '12th'])

        rows.append({
            'student_id': sid,
            'student_name': messy_name(first, last),
            'first_name': maybe_null(first),
            'last_name': maybe_null(last),
            'date_of_birth': maybe_null(messy_date(dob_dt)),
            'grade_level': messy_grade(grade),
            'site': maybe_null(random.choice(SITES)),
            'ethnicity': maybe_null(random.choice(ETHNICITIES), null_rate=0.18),
            'free_reduced_lunch': maybe_null(random.choice(['Yes', 'No', 'Y', 'N', '1', '0', 'yes', 'TRUE'])),
            'enrollment_date': messy_date(
                datetime(2023, random.randint(8, 9), random.randint(1, 28))
            ),
            'email': maybe_null(fake.email(), null_rate=0.25),
            'guardian_phone': maybe_null(fake.phone_number(), null_rate=0.20),
        })

    df = pd.DataFrame(rows)

    # Inject ~15 duplicate students (same kid, slightly different record)
    dupes = df.sample(15).copy()
    dupes['student_id'] = dupes['student_id']  # same ID, different name format
    dupes['student_name'] = dupes.apply(
        lambda r: messy_name(
            str(r['first_name']) if r['first_name'] else fake.first_name(),
            str(r['last_name']) if r['last_name'] else fake.last_name()
        ), axis=1
    )
    dupes['email'] = dupes['email'].apply(lambda x: maybe_null(fake.email()))
    df = pd.concat([df, dupes], ignore_index=True).sample(frac=1).reset_index(drop=True)

    path = os.path.join(OUTPUT_DIR, 'students_2023_24.csv')
    df.to_csv(path, index=False)
    print(f"✓ students_2023_24.csv — {len(df)} rows (includes {len(dupes)} dupes)")
    return student_ids


# ─── 2. PROGRAM ENROLLMENT ────────────────────────────────────────────────────
def generate_enrollments(student_ids):
    rows = []
    for sid in student_ids:
        n_programs = random.choices([1, 2, 3], weights=[0.6, 0.3, 0.1])[0]
        programs = random.sample(PROGRAMS, n_programs)
        for prog in programs:
            start = datetime(2023, random.randint(8, 10), random.randint(1, 28))
            rows.append({
                'enrollment_id': f"ENR{fake.unique.random_int(min=1000, max=9999)}",
                'student_id': sid,
                'program_name': maybe_null(prog, null_rate=0.05),
                # intentional: some stored as 'program', some as 'program_name'
                'program': prog,
                'start_date': messy_date(start),
                'end_date': maybe_null(messy_date(start + timedelta(days=random.randint(60, 180)))),
                'status': maybe_null(random.choice(['Active', 'active', 'ACTIVE', 'Completed', 'Dropped', 'dropout', 'completed'])),
                'cohort': maybe_null(random.choice(['Fall 2023', 'Fall23', 'Spring 2024', 'Sp24', None])),
                'site': maybe_null(random.choice(SITES)),
            })

    df = pd.DataFrame(rows)
    path = os.path.join(OUTPUT_DIR, 'program_enrollments.csv')
    df.to_csv(path, index=False)
    print(f"✓ program_enrollments.csv — {len(df)} rows")


# ─── 3. ATTENDANCE ────────────────────────────────────────────────────────────
def generate_attendance(student_ids):
    rows = []
    # Generate weekly attendance for ~20 weeks
    base_date = datetime(2023, 9, 5)
    sample_students = random.sample(student_ids, 200)  # not all students have attendance logged

    for sid in sample_students:
        for week in range(20):
            week_date = base_date + timedelta(weeks=week)
            if random.random() < 0.08:  # 8% weeks completely missing
                continue
            rows.append({
                'student_id': sid,
                'week_of': messy_date(week_date),
                'sessions_attended': maybe_null(random.randint(0, 3)),
                'sessions_scheduled': maybe_null(random.randint(2, 3)),
                # Some logged as percentage, some as fraction — classic
                'attendance_rate': maybe_null(
                    random.choice([
                        round(random.uniform(0.4, 1.0), 2),
                        f"{random.randint(40, 100)}%",
                        None
                    ]),
                    null_rate=0.15
                ),
                'note': maybe_null(
                    random.choice(['excused', 'unexcused', 'sick', 'family emergency', '', None]),
                    null_rate=0.7
                ),
            })

    df = pd.DataFrame(rows)
    path = os.path.join(OUTPUT_DIR, 'attendance_log.csv')
    df.to_csv(path, index=False)
    print(f"✓ attendance_log.csv — {len(df)} rows")


# ─── 4. ASSESSMENT SCORES ─────────────────────────────────────────────────────
def generate_assessments(student_ids):
    rows = []
    assessments = [
        ('Math', 'Pre', 'Sep 2023'),
        ('Math', 'Post', 'Jan 2024'),
        ('Reading', 'Pre', 'Sep 2023'),
        ('Reading', 'Post', 'Jan 2024'),
        ('SEL', 'Mid', 'Nov 2023'),   # Social Emotional Learning
    ]

    for sid in student_ids:
        for subject, period, month in assessments:
            if random.random() < 0.18:  # 18% missing assessments
                continue

            pre_score = random.randint(40, 75)
            # post scores show growth (but not always)
            if period == 'Post':
                score = pre_score + random.randint(-5, 25)
            else:
                score = pre_score

            rows.append({
                'student_id': sid,
                'subject': subject,
                'assessment_period': period,
                'month': month,
                # Score stored inconsistently — sometimes /100, sometimes raw
                'score': maybe_null(score),
                'score_out_of': maybe_null(random.choice([100, 100, 100, None])),
                'percentile': maybe_null(round(random.uniform(10, 90), 1), null_rate=0.3),
                'grade_equivalent': maybe_null(
                    random.choice(['5.2', '6.1', '7.3', '8.0', 'N/A', None]),
                    null_rate=0.4
                ),
                'assessor': maybe_null(fake.name(), null_rate=0.5),
            })

    df = pd.DataFrame(rows)
    path = os.path.join(OUTPUT_DIR, 'assessment_scores.csv')
    df.to_csv(path, index=False)
    print(f"✓ assessment_scores.csv — {len(df)} rows")


# ─── 5. GRANTS / OUTCOMES (the one that doesn't join cleanly) ─────────────────
def generate_grants():
    """
    Grant funder expects specific metrics.
    Column names don't match the other CSVs — this is intentional.
    FDE problem: reconcile 'participant_id' with 'student_id'.
    """
    rows = []
    grant_programs = {
        'Literacy First': ('Chicago Community Trust', 50000),
        'STEM Bootcamp': ('Gates Foundation', 75000),
        'College Prep 101': ('State DOE', 40000),
    }

    for prog, (funder, amount) in grant_programs.items():
        rows.append({
            'grant_id': f"GR{random.randint(1000,9999)}",
            'funder_name': funder,
            'program': prog,
            'award_amount': amount,
            'grant_year': '2023-24',
            # Metrics reported per grant — columns differ from assessments CSV
            'target_participants': random.randint(60, 120),
            'reported_participants': random.randint(55, 115),
            'target_attendance_rate': '80%',
            'reported_attendance_rate': f"{random.randint(72, 91)}%",
            'target_math_growth': '10 points',
            'reported_math_growth': maybe_null(f"{random.randint(5, 18)} points"),
            'target_reading_growth': '1 grade level',
            'reported_reading_growth': maybe_null(
                random.choice(['0.8 grade levels', '1.1 grade levels', '1 grade level', None])
            ),
            'report_due_date': messy_date(datetime(2024, random.randint(3, 6), 30)),
            'submitted': maybe_null(random.choice(['Yes', 'No', None])),
            'notes': maybe_null(fake.sentence(), null_rate=0.5),
        })

    df = pd.DataFrame(rows)
    path = os.path.join(OUTPUT_DIR, 'grants_outcomes.csv')
    df.to_csv(path, index=False)
    print(f"✓ grants_outcomes.csv — {len(df)} rows")


# ─── 6. STAFF / PROGRAM LEADS (sparse, messy) ─────────────────────────────────
def generate_staff():
    rows = []
    for _ in range(20):
        rows.append({
            'staff_id': f"STF{random.randint(100,999)}",
            'name': fake.name(),
            'role': maybe_null(random.choice([
                'Program Coordinator', 'Tutor', 'tutor', 'Site Lead',
                'Program Manager', 'Volunteer', 'AmeriCorps', None
            ])),
            'site': maybe_null(random.choice(SITES)),
            'program': maybe_null(random.choice(PROGRAMS)),
            'hire_date': maybe_null(messy_date(fake.date_between(start_date='-3y', end_date='-6m'))),
            'fte': maybe_null(random.choice([1.0, 0.5, 0.25, 'full-time', 'part-time', None])),
            'email': maybe_null(fake.email()),
        })

    df = pd.DataFrame(rows)
    path = os.path.join(OUTPUT_DIR, 'staff_roster.csv')
    df.to_csv(path, index=False)
    print(f"✓ staff_roster.csv — {len(df)} rows")


# ─── MAIN ─────────────────────────────────────────────────────────────────────
if __name__ == '__main__':
    print("\n🎲 Generating synthetic messy education data for EduPulse...\n")
    student_ids = generate_students_2024()
    generate_enrollments(student_ids)
    generate_attendance(student_ids)
    generate_assessments(student_ids)
    generate_grants()
    generate_staff()
    print(f"\n✅ All files written to: {os.path.abspath(OUTPUT_DIR)}")
    print("\nData issues baked in:")
    print("  • Inconsistent name formats (Last, First / UPPER / initials)")
    print("  • Mixed date formats in same column")
    print("  • ~15 duplicate student records")
    print("  • attendance_rate stored as float AND percentage string")
    print("  • grade_level stored 3 different ways")
    print("  • grants CSV uses 'participant_id' — won't join cleanly")
    print("  • ~12-25% null rates across key fields")
    print("  • status values inconsistent (Active/active/ACTIVE/dropout)")