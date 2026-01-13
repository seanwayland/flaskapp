import psycopg2
import requests
import time
from config import DB_PASSWORD, NEVERBOUNCE_API_KEY


import csv
import os

from datetime import datetime

# -------------------------
# CONFIG
# -------------------------

DB_CONFIG = {
    "host": "3.141.191.84",
    "dbname": "waylo_db",
    "user": "waylo_user",
    "password": DB_PASSWORD,
    "port": 5432,
}


NEVERBOUNCE_URL = "https://api.neverbounce.com/v4/single/check"

# Treat these results as "bad"
BAD_RESULTS = {"invalid", "disposable", "spamtrap", "unknown"}





# -------------------------
# CONFIG
# -------------------------



CSV_FILE = "neverbounce_results.csv"



# -------------------------
# CSV HELPERS
# -------------------------

def load_checked_emails():
    checked = set()

    if not os.path.exists(CSV_FILE):
        return checked

    with open(CSV_FILE, newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            checked.add(row["email"].lower())

    return checked


def append_csv_row(row):
    file_exists = os.path.exists(CSV_FILE)

    with open(CSV_FILE, "a", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=["email", "result", "is_bad", "checked_at"]
        )

        if not file_exists:
            writer.writeheader()

        writer.writerow(row)
        f.flush()  # critical for crash safety


# -------------------------
# DB
# -------------------------

def get_all_emails(conn):
    with conn.cursor() as cur:
        cur.execute("""
            SELECT email
            FROM mailing_list
            WHERE unsubscribed IS NOT TRUE
        """)
        return [row[0].lower() for row in cur.fetchall()]


def mark_unsubscribed(conn, bad_emails):
    if not bad_emails:
        return

    with conn.cursor() as cur:
        cur.execute("""
            UPDATE mailing_list
            SET unsubscribed = TRUE
            WHERE email = ANY(%s)
        """, (bad_emails,))
    conn.commit()


# -------------------------
# NEVERBOUNCE
# -------------------------

def check_email(email):
    params = {
        "key": NEVERBOUNCE_API_KEY,
        "email": email,
    }
    resp = requests.get(NEVERBOUNCE_URL, params=params, timeout=10)
    resp.raise_for_status()
    return resp.json().get("result")


# -------------------------
# MAIN
# -------------------------

def main():
    conn = psycopg2.connect(**DB_CONFIG)

    all_emails = get_all_emails(conn)
    checked_emails = load_checked_emails()

    to_check = [e for e in all_emails if e not in checked_emails]

    print(f"Total emails: {len(all_emails)}")
    print(f"Already checked: {len(checked_emails)}")
    print(f"Remaining to check: {len(to_check)}")

    newly_bad = []

    for i, email in enumerate(to_check, start=1):
        try:
            result = check_email(email)
            is_bad = result in BAD_RESULTS

            row = {
                "email": email,
                "result": result,
                "is_bad": is_bad,
                "checked_at": datetime.utcnow().isoformat(),
            }

            append_csv_row(row)

            if is_bad:
                newly_bad.append(email)

            print(f"[{i}/{len(to_check)}] {email} → {result}")

            time.sleep(0.2)

        except Exception as e:
            print(f"ERROR {email}: {e}")

    print(f"Unsubscribing {len(newly_bad)} new emails...")
    mark_unsubscribed(conn, newly_bad)

    conn.close()
    print("Done.")


if __name__ == "__main__":
    main()

