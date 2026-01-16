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
from config import access_key_id, secret_access_key, S3_BUCKET, SES_ACCESS_KEY, SES_SECRET_KEY, SES_REGION
import csv
from io import TextIOWrapper
from pathlib import Path
import os
import platform
import psycopg2
from PIL import Image, ImageDraw, ImageFont

import logging
logging.basicConfig(level=logging.INFO)


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


ses_client = boto3.client(
    "ses",
    aws_access_key_id=SES_ACCESS_KEY,
    aws_secret_access_key=SES_SECRET_KEY,
    region_name=SES_REGION
)

import time


def send_email(to_address, subject, html_body, text_body):
    response = ses_client.send_email(
        ReplyToAddresses=["seanwayland@gmail.com"],
        Source="Sean Wayland <sean@waylomusic.com>", # or another real inbox
        Destination={"ToAddresses": [to_address]},
        Message={
            "Subject": {"Data": subject, "Charset": "UTF-8"},
            "Body": {
                "Html": {"Data": html_body, "Charset": "UTF-8"},
                "Text": {"Data": text_body, "Charset": "UTF-8"}
            }
        }
    )
    time.sleep(0.2)
    return response


def upload_image_to_s3(local_path, s3_key):
    s3.upload_file(
        local_path,
        S3_BUCKET,
        s3_key,
        ExtraArgs={
            "ContentType": "image/png",
            "ACL": "private"
        }
    )
    return s3_key


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

        poster_text = f"{data['info']}"
        image_key = text_on_image(poster_text)

        db_insert(
            """
            INSERT INTO performances (date, location, info, image_url)
            VALUES (%s, %s, %s, %s)
            """,
            (data["date"], data["location"], data["info"], image_key)
        )

        data["image_url"] = image_key

        return render_template(
            "thanks.html",
            source="/performances/new",
            rows=[data]
        )

    return render_template("performance_form.html")


# =====================================================
# Mailing List (with CSV support)
# =====================================================
# =====================================================
# Mailing List (with CSV support + unsubscribed)
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
                return render_template(
                    "mailing_list_form.html",
                    error="Please upload a CSV file"
                )

            reader = csv.DictReader(TextIOWrapper(csv_file, encoding="utf-8"))

            # normalize fieldnames to lowercase
            fieldnames = {f.lower() for f in reader.fieldnames}

            required_fields = {"name", "email"}
            if not required_fields.issubset(fieldnames):
                return render_template(
                    "mailing_list_form.html",
                    error="CSV must contain at least: Name, Email"
                )

            for row in reader:
                name = row.get("Name") or row.get("name") or ""
                email = row.get("Email") or row.get("email")
                location = row.get("Location") or row.get("location") or ""
                info = row.get("Info") or row.get("info") or ""

                # Unsubscribed: 1 = TRUE, anything else = FALSE
                unsubscribed_raw = (
                    row.get("Unsubscribed")
                    or row.get("unsubscribed")
                    or ""
                ).strip()

                unsubscribed = unsubscribed_raw in ("1", "true", "TRUE", "yes", "YES")

                if not email:
                    continue  # skip invalid rows

                db_insert("""
                    INSERT INTO mailing_list (email, name, location, info, unsubscribed)
                    VALUES (%s, %s, %s, %s, %s)
                    ON CONFLICT (email)
                    DO UPDATE SET
                        name = EXCLUDED.name,
                        location = EXCLUDED.location,
                        info = EXCLUDED.info,
                        unsubscribed = EXCLUDED.unsubscribed;
                """, (
                    email,
                    name,
                    location,
                    info,
                    unsubscribed
                ))

                rows_to_show.append({
                    "name": name,
                    "email": email,
                    "location": location,
                    "info": info,
                    "unsubscribed": unsubscribed
                })

            return render_template(
                "thanks.html",
                source="/mailing-list/new",
                rows=rows_to_show[:10]
            )

        # ---- SINGLE FORM ENTRY PATH ----
        data = {
            "name": request.form["name"],
            "email": request.form["email"],
            "location": request.form.get("location", ""),
            "info": request.form.get("info", ""),
        }

        db_insert("""
            INSERT INTO mailing_list (email, name, location, info, unsubscribed)
            VALUES (%s, %s, %s, %s, FALSE)
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
        return render_template(
            "thanks.html",
            source="/mailing-list/new",
            rows=rows_to_show
        )

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
    cur.execute("SELECT email, name, location, info, unsubscribed FROM mailing_list ORDER BY email")
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
    cur.execute("SELECT email, name, location, info, unsubscribed FROM mailing_list ORDER BY email")
    rows = cur.fetchall()
    cur.close()
    conn.close()

    si = StringIO()
    writer = csv.writer(si)
    writer.writerow(["email", "name", "location", "info", "unsubscribed"])
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
def view_performances():
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT date, location, info, image_url FROM performances WHERE date >= NOW() ORDER BY date ASC")
    rows = cur.fetchall()
    cur.close()
    conn.close()

    # Convert to list of dicts and generate presigned URLs
    performances = []
    for row in rows:
        date, location, info, image_key = row
        if image_key:
            try:
                image_url = s3.generate_presigned_url(
                    "get_object",
                    Params={"Bucket": S3_BUCKET, "Key": image_key},
                    ExpiresIn=3600  # URL valid for 1 hour
                )
            except Exception:
                image_url = None
        else:
            image_url = None
        performances.append({
            "date": date,
            "location": location,
            "info": info,
            "image_url": image_url,
            "image_key": image_key  # raw key text
        })

    return render_template("performances_view.html", performances=performances)



@app.route("/performances/download")
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

def get_default_font_path():
    system = platform.system()
    if system == "Darwin":  # macOS
        return "/System/Library/Fonts/Supplemental/Arial Bold.ttf"
    elif system == "Linux":  # Ubuntu
        return "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
    else:
        raise RuntimeError(f"Unsupported OS: {system}")


from textwrap import wrap
from PIL import Image, ImageDraw, ImageFont

def text_on_image(text, background_path="/home/ubuntu/flaskapp/bg.jpg"):
    img = Image.open(background_path)
    draw = ImageDraw.Draw(img)
    font_path = get_default_font_path()
    font_size = 15
    font = ImageFont.truetype(font_path, font_size)

    # Wrap text to fit image width
    max_width = img.width - 100  # padding
    lines = []
    for paragraph in text.splitlines():
        lines.extend(wrap(paragraph, width=40))  # adjust width

    y_text = 50
    for line in lines:
        draw.text(
            (50, y_text),
            line,
            font=font,
            fill="white",
            stroke_width=3,
            stroke_fill="black"
        )
        # Use textbbox to get height
        bbox = draw.textbbox((0,0), line, font=font, stroke_width=3)
        line_height = bbox[3] - bbox[1]
        y_text += line_height + 5  # spacing

    # ---- temp local file ----
    filename = f"performance_{int(__import__('time').time())}.png"
    local_path = f"/tmp/{filename}"

    img.save(local_path)

    # ---- upload to S3 ----
    s3_key = f"performance_images/{filename}"
    upload_image_to_s3(local_path, s3_key)

    # cleanup
    try:
        os.remove(local_path)
    except OSError:
        pass

    return s3_key


from urllib.parse import unquote


@app.route("/mailing-list/unsubscribe")
def unsubscribe():
    email = request.args.get("email")
    token = request.args.get("secret")  # optional
    
    if not email:
        return "Missing email", 400
    
    # If token exists, verify it (bounce/Lambda case)
    if token and token != "Banana":
        return "Unauthorized", 403
    
    email = unquote(email)
    
    db_insert(
        "UPDATE mailing_list SET unsubscribed = TRUE WHERE email = %s",
        (email,)
    )
    
    return render_template("unsubscribed.html", email=email)



# -------------------------
# SEND NEWSLETTER FUNCTION
# -------------------------
def send_newsletter(subject="Upcoming Sean Wayland Performances",
                    body_text="Check out the upcoming performances!",
                    extra_message=""):
    """
    Sends newsletter to users.
    Opens its own DB connection.
    """
    conn = get_db()
    try:
        cur = conn.cursor()
        cur.execute("""
            SELECT email, name
            FROM mailing_list
            WHERE unsubscribed = FALSE
            AND email IN ('seanwayland@gmail.com', 'echoqshen@gmail.com',
                          'bounce@simulator.amazonses.com',
                          'complaint@simulator.amazonses.com')
        """)
        rows = cur.fetchall()
        cur.close()
    finally:
        conn.close()

    for email, name in rows:

        # HTML version with proper line breaks
        extra_html = f"<p>{extra_message.replace('\n', '<br>')}</p>" if extra_message else ""
        extra_text = f"\n\n{extra_message}" if extra_message else ""


        html_body = f"""
        <p>Hi {name or 'there'},</p>
        {extra_html}
        <p>“You are receiving this email because you signed up for updates at waylomusic.com.”</p>
        <p><strong>Upcoming Sean Wayland Performances</strong></p>
        <p>
            <a href="https://waylomusic.com/performances/view">View Performances</a>
        </p>
        <p>
            <a href="https://waylomusic.com/mailing-list/unsubscribe?email={email}">Unsubscribe</a>
        </p>
        """

        text_body = f"""
Dear {name or 'friend'},
{extra_text}

Upcoming Sean Wayland Performances:
https://waylomusic.com/performances/view

Unsubscribe:
https://waylomusic.com/mailing-list/unsubscribe?email={email}
"""

        send_email(
    email,
    subject,
    html_body,
    text_body,
    source="Sean Wayland <sean@waylomusic.com>"  # must match verified domain
)

        logging.info(f"Sent newsletter to {email}")
        


# -------------------------
# BACKGROUND THREAD FUNCTION
# -------------------------
def send_newsletter_thread(extra_message):
    """
    Runs newsletter sending in a separate thread.
    """
    try:
        send_newsletter(extra_message=extra_message)
        logging.info("Newsletter thread finished successfully")
    except Exception:
        logging.exception("Newsletter thread failed")


# -------------------------
# SEND NEWSLETTER ENDPOINT
# -------------------------
@app.route("/send-newsletter", methods=["GET", "POST"])
@require_upload_auth
def send_newsletter_endpoint():
    message = None
    extra_message = ""

    if request.method == "POST":
        extra_message = request.form.get("extra_message", "").strip()

        # --- EARLY RETURN FOR TESTING ---
        #return f"POST received! Extra message: {extra_message}"

        # Fire-and-forget background thread
        # threading.Thread(
        #     target=send_newsletter_thread,
        #     args=(extra_message,),
        #     daemon=True
        # ).start()

        try:
            send_newsletter(extra_message=extra_message)
            logging.info("Newsletter thread finished successfully")
        except Exception:
            logging.exception("Newsletter thread failed")
        message = "Newsletter is being sent..."

    return render_template(
        "newsletter_compose.html",
        message=message,
        extra_message=extra_message
    )

@app.route('/admin')
@require_upload_auth
def admin():
    return render_template('admin.html')

# =====================================================
# Public Mailing List Signup
# =====================================================
@app.route("/mailing_list/signup", methods=["GET", "POST"])
def mailing_list_signup():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip().lower()
        location = request.form.get("location", "").strip()

        if not name or not email:
            return render_template(
                "mailing_list_signup.html",
                error="Name and email are required."
            )

        # Insert as unsubscribed = FALSE
        db_insert("""
            INSERT INTO mailing_list (email, name, location, unsubscribed)
            VALUES (%s, %s, %s, FALSE)
            ON CONFLICT (email)
            DO UPDATE SET
                name = EXCLUDED.name,
                location = EXCLUDED.location;
        """, (email, name, location))

        # Optional: send confirmation email later (double opt-in)
        # send_confirm_email(email)

        return render_template("mailing_list_signup_success.html", email=email)

    return render_template("mailing_list_signup.html")












