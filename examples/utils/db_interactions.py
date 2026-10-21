import sqlite3
import csv
from pathlib import Path


def coordinate_funding_db(candidates, db_file_path):
    existing_orgs = set()
    # --- Set up db ---
    conn = sqlite3.connect(str(db_file_path))
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS funding_candidates (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            org_name TEXT UNIQUE,
            funding_amount REAL,
            application_deadline TEXT,
            application_url TEXT,
            justification TEXT
        )
    """)
    print('checkpoint 2')
    cur.execute("SELECT org_name FROM funding_candidates")
    existing_orgs.update(
        row[0].strip().lower() for row in cur.fetchall() if row[0]
    )
    inserted = 0
    skipped = 0

    for c in candidates:

        org_name = (c.get("org_name") or "").strip().lower()

        if not org_name or org_name in existing_orgs:
            skipped += 1
            continue

        cur.execute(
            "INSERT INTO funding_candidates (org_name, funding_amount, application_deadline, application_url, justification) VALUES (?, ?, ?, ?, ?)",
            (org_name, c.get('funding_amount'), c.get('application_deadline'), c.get('application_url'),
             c.get('justification'))
        )
        existing_orgs.add(org_name)
        inserted += 1
    conn.commit()
    conn.close()
    confirmation_message = f"Inserted: {inserted} into 'funding_candidates' table,\nSkipped (duplicate/missing email): {skipped}"
    return confirmation_message


def coordinate_outreach_db(candidates, sp_file_path, db_file_path):
    existing_emails = set()

    csv_path = Path(sp_file_path)
    if csv_path.exists():
        with open(csv_path, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                email = row.get("EMAIL")
                if email:
                    existing_emails.add(email.strip().lower())

    conn = sqlite3.connect(str(db_file_path))
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS candidates (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            first_name TEXT,
            last_name TEXT,
            org_name TEXT,
            contact_email TEXT UNIQUE,
            justification TEXT
        )
    """)

    cur.execute("SELECT contact_email FROM candidates")
    existing_emails.update(
        row[0].strip().lower() for row in cur.fetchall() if row[0]
    )

    inserted = 0
    skipped = 0
    for c in candidates:
        email = (c.get("contact_email") or "").strip().lower()

        if not email or email in existing_emails:
            skipped += 1
            continue

        cur.execute(
            "INSERT INTO candidates (first_name, last_name, org_name, contact_email, justification) VALUES (?, ?, ?, ?, ?)",
            (c.get('first_name'), c.get('last_name'), c.get("org_name"), email, c.get("justification"))
        )
        existing_emails.add(email)
        inserted += 1

    conn.commit()
    conn.close()
    confirmation_message = f"Inserted: {inserted} into 'candidates' table,\nSkipped (duplicate/missing email): {skipped}"
    return confirmation_message
