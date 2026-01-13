import csv
import os
import psycopg2
from config import DB_PASSWORD

CSV_FILE = "mailing_list_edited_fix.csv"

DB_CONFIG = {
    "host": "3.141.191.84",
    "dbname": "waylo_db",
    "user": "waylo_user",
    "password": DB_PASSWORD,
    "port": 5432,
}


def load_emails_to_unsubscribe(csv_path):
    emails = set()

    if not os.path.exists(csv_path):
        print(f"CSV file not found: {csv_path}")
        return []

    with open(csv_path, newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            # Accept common truthy values in the unsubscribed column
            val = (row.get("unsubscribed") or "").strip().lower()
            if val in ("true", "1", "t", "yes", "y"):
                email = (row.get("email") or "").strip().lower()
                if email:
                    emails.add(email)

    return sorted(emails)


def mark_unsubscribed(conn, emails):
    if not emails:
        print("No emails to unsubscribe.")
        return

    with conn.cursor() as cur:
        cur.execute(
            """
            UPDATE mailing_list
            SET unsubscribed = TRUE
            WHERE email = ANY(%s)
            """,
            (emails,),
        )
        updated = cur.rowcount
    conn.commit()
    print(f"Updated {updated} rows.")


def main():
    csv_path = os.path.join(os.path.dirname(__file__), CSV_FILE)
    emails = load_emails_to_unsubscribe(csv_path)

    print(f"Found {len(emails)} unsubscribed emails in CSV.")
    if not emails:
        return

    conn = psycopg2.connect(**DB_CONFIG)
    try:
        mark_unsubscribed(conn, emails)
    finally:
        conn.close()


if __name__ == "__main__":
    main()
