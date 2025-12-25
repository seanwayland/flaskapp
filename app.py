from flask import (
    Flask,
    render_template,
    send_from_directory,
    send_file,
    redirect,
    request,
    session,
    url_for
)
import boto3
from config import access_key_id, secret_access_key, S3_BUCKET
import csv
from io import TextIOWrapper
from pathlib import Path
import os
import platform
import psycopg2

# -----------------------------
# Determine if we should use the database
# -----------------------------
USE_DB = platform.system() != "Darwin"  # Skip DB on macOS

def get_db():
    if not USE_DB:
        return None
    return psycopg2.connect(
        dbname="waylo_db",
        user="waylo_user",
        password=os.environ["WAYLO_DB_PASSWORD"],
        host="localhost"
    )

def db_insert(query, params):
    if not USE_DB:
        print("Skipping DB insert:", query, params)
        return
    conn = get_db()
    cur = conn.cursor()
    cur.execute(query, params)
    conn.commit()
    cur.close()
    conn.close()

# -----------------------------
# AWS setup
# -----------------------------
s3 = boto3.client(
    "s3",
    aws_access_key_id=access_key_id,
    aws_secret_access_key=secret_access_key,
    region_name="us-east-1"
)

AWS_S3_SIGNATURE_VERSION = "s3v4"

app = Flask(__name__)

# -----------------------------
# Load secrets
# -----------------------------
secrets_file = "/home/ubuntu/flaskapp/secrets.env"
if platform.system() == "Darwin":  # macOS
    secrets_file = "/Users/seanwayland/Desktop/waylo_flask_again/secrets.env"

with open(secrets_file) as f:
    for line in f:
        if "=" in line:
            key, value = line.strip().split("=", 1)
            os.environ[key] = value

app.secret_key = os.environ["FLASK_SECRET_KEY"]
UPLOAD_PASSWORD = os.environ["UPLOAD_PASSWORD"]
UPLOAD_DIR = "/home/ubuntu/flaskapp/static/files"

# =====================================================
#  LOGIN ROUTE
# =====================================================
@app.route('/upload', methods=['GET', 'POST'])
def upload_login():
    next_page = request.args.get("next")
    if next_page:
        session["next"] = next_page

    if request.method == 'POST':
        if request.form.get("password") == UPLOAD_PASSWORD:
            session["upload_auth"] = True
            redirect_target = session.pop("next", None)
            return redirect(redirect_target or url_for("hello"))
        else:
            return render_template("upload_login.html", error="Incorrect password")
    return render_template("upload_login.html")

# -----------------------------
# Upload protection decorator
# -----------------------------
def require_upload_auth(f):
    def wrapper(*args, **kwargs):
        if not session.get("upload_auth"):
            return redirect(url_for("upload_login", next=request.path))
        return f(*args, **kwargs)
    wrapper.__name__ = f.__name__
    return wrapper

# =====================================================
#  S3 UPLOAD
# =====================================================
@app.route("/s3/upload", methods=["GET", "POST"])
@require_upload_auth
def s3_upload():
    if request.method == "POST":
        if "file" not in request.files:
            return render_template("upload_form_s3.html", error="No file uploaded")
        file = request.files["file"]
        if file.filename == "":
            return render_template("upload_form_s3.html", error="No filename")
        try:
            s3.upload_fileobj(
                file,
                S3_BUCKET,
                file.filename,
                ExtraArgs={"ACL": "private"}
            )
            return render_template("upload_form_s3.html", success="Uploaded to S3!")
        except Exception as e:
            return render_template("upload_form_s3.html", error=str(e))
    return render_template("upload_form_s3.html")

# =====================================================
#  S3 LIST FILES
# =====================================================
@app.route("/s3/files")
def list_s3_files():
    try:
        response = s3.list_objects_v2(Bucket=S3_BUCKET)
        files = [obj["Key"] for obj in response.get("Contents", [])]
        return render_template("s3_files.html", files=files)
    except Exception as e:
        return str(e)

# =====================================================
#  S3 DOWNLOAD
# =====================================================
@app.route("/s3/download/<path:key>")
def s3_download(key):
    try:
        url = s3.generate_presigned_url(
            "get_object",
            Params={"Bucket": S3_BUCKET, "Key": key},
            ExpiresIn=300
        )
        return redirect(url)
    except Exception as e:
        return str(e)

# =====================================================
#  EC2 FILE UPLOAD (LOCAL)
# =====================================================
@app.route('/upload/form', methods=['GET', 'POST'])
@require_upload_auth
def upload_form():
    if request.method == 'POST':
        if "file" not in request.files:
            return render_template("upload_form.html", error="No file part")
        file = request.files["file"]
        if file.filename == "":
            return render_template("upload_form.html", error="No file selected")
        os.makedirs(UPLOAD_DIR, exist_ok=True)
        save_path = os.path.join(UPLOAD_DIR, file.filename)
        file.save(save_path)
        return render_template("upload_form.html", success="File uploaded!")
    return render_template("upload_form.html")

# =====================================================
#  MISC ROUTES
# =====================================================
@app.route('/')
def hello():
    return render_template('index.html')

@app.route('/yeah')
def yeah():
    return "yeah"

@app.route('/filedrop/')
def indexoo():
    p = Path(app.static_folder, 'files')
    filenames = [x.relative_to(app.static_folder) for x in p.iterdir() if x.is_file()]
    return render_template('files.html', **locals())

@app.route('/rail_mary/')
def hello_mary():
    return render_template('rail_mary.html')

@app.route('/return-all_charts/')
def return_all_charts():
    try:
        return send_file('sean_wayland_pdfs_jan26_2022.zip')
    except Exception as e:
        return str(e)

@app.route('/return-plugins/')
def return_plugins():
    try:
        return send_file('plugins_2023.zip')
    except Exception as e:
        return str(e)

@app.route('/return_rail_mary_album/')
def return_rail_mary():
    resource = "rail_mary_album_complete.zip"
    try:
        url = s3.generate_presigned_url(
            'get_object',
            Params={'Bucket': S3_BUCKET, 'Key': resource},
            ExpiresIn=1000
        )
        return redirect(url)
    except Exception as e:
        return str(e)

@app.route('/return_expanded_album/')
def return_expanded_ablum():
    try:
        return send_file('expanded_album.zip')
    except Exception as e:
        return str(e)

@app.route('/files')
def indexo():
    p = Path("/var/www/html/flaskapp/static/files")
    filenames = [x.relative_to(app.static_folder) for x in p.iterdir() if x.is_file()]
    return render_template('files.html', **locals())

# =====================================================
# Performances
# =====================================================
@app.route("/performances/new", methods=["GET", "POST"])
@require_upload_auth
def new_performance():
    if request.method == "POST":
        data = {
            "date": request.form["date"],
            "location": request.form["location"],
            "info": request.form["info"],
        }
        db_insert(
            "INSERT INTO performances (date, location, info) VALUES (%s, %s, %s)",
            (data["date"], data["location"], data["info"])
        )
        return render_template(
            "thanks.html",
            source="/performances/new",
            rows=[data]
        )
    return render_template("performance_form.html")

# =====================================================
# Mailing List (with CSV support)
# =====================================================
@app.route("/mailing-list/new", methods=["GET", "POST"])
@require_upload_auth
def new_mailing_list_entry():
    if request.method == "POST":

        rows_to_show = []

        # ---- CSV UPLOAD PATH ----
        if "csv_file" in request.files and request.files["csv_file"].filename:
            csv_file = request.files["csv_file"]
            if not csv_file.filename.lower().endswith(".csv"):
                return render_template("mailing_list_form.html", error="Please upload a CSV file")
            reader = csv.DictReader(TextIOWrapper(csv_file, encoding="utf-8"))
            required_fields = {"name", "email", "location", "info"}
            if not required_fields.issubset(reader.fieldnames):
                return render_template("mailing_list_form.html", error="CSV must contain: name, email, location, info")
            for row in reader:
                db_insert("""
                    INSERT INTO mailing_list (email, name, location, info)
                    VALUES (%s, %s, %s, %s)
                    ON CONFLICT (email)
                    DO UPDATE SET
                        name = EXCLUDED.name,
                        location = EXCLUDED.location,
                        info = EXCLUDED.info;
                """, (
                    row["email"],
                    row["name"],
                    row["location"],
                    row["info"]
                ))
                rows_to_show.append(row)
            return render_template("thanks.html", source="/mailing-list/new", rows=rows_to_show[:10])

        # ---- SINGLE FORM ENTRY PATH ----
        data = {
            "name": request.form["name"],
            "email": request.form["email"],
            "location": request.form["location"],
            "info": request.form["info"],
        }
        db_insert("""
            INSERT INTO mailing_list (email, name, location, info)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (email)
            DO UPDATE SET
                name = EXCLUDED.name,
                location = EXCLUDED.location,
                info = EXCLUDED.info;
        """, (
            data["email"],
            data["name"],
            data["location"],
            data["info"]
        ))
        rows_to_show.append(data)
        return render_template("thanks.html", source="/mailing-list/new", rows=rows_to_show)

    return render_template("mailing_list_form.html")

# =====================================================
# THANKS PAGE
# =====================================================
@app.route("/thanks")
def thanks():
    page = request.args.get("page")
    rows = session.pop("submitted_rows", [])
    total = session.pop("submitted_total", len(rows))
    return render_template("thanks.html", page=page, rows=rows[:10], total=total)


# =====================================================
# View all mailing list entries
# =====================================================
@app.route("/mailing-list/view")
@require_upload_auth
def view_mailing_list():
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT email, name, location, info FROM mailing_list ORDER BY email")
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return render_template("mailing_list_view.html", rows=rows[:50])  # show only first 50 rows


@app.route("/mailing-list/download")
@require_upload_auth
def download_mailing_list():
    import csv
    from io import StringIO
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT email, name, location, info FROM mailing_list ORDER BY email")
    rows = cur.fetchall()
    cur.close()
    conn.close()

    si = StringIO()
    writer = csv.writer(si)
    writer.writerow(["email", "name", "location", "info"])
    writer.writerows(rows)
    output = si.getvalue()
    return (output, 200, {
        "Content-Type": "text/csv",
        "Content-Disposition": 'attachment; filename="mailing_list.csv"'
    })


# =====================================================
# View all performances
# =====================================================
@app.route("/performances/view")
@require_upload_auth
def view_performances():
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT date, location, info FROM performances ORDER BY date DESC")
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return render_template("performances_view.html", rows=rows[:50])  # show first 50 rows


@app.route("/performances/download")
@require_upload_auth
def download_performances():
    import csv
    from io import StringIO
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT date, location, info FROM performances ORDER BY date DESC")
    rows = cur.fetchall()
    cur.close()
    conn.close()

    si = StringIO()
    writer = csv.writer(si)
    writer.writerow(["date", "location", "info"])
    writer.writerows(rows)
    output = si.getvalue()
    return (output, 200, {
        "Content-Type": "text/csv",
        "Content-Disposition": 'attachment; filename="performances.csv"'
    })


