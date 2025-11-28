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
from pathlib import Path
import os

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

with open(secrets_file) as f:
    for line in f:
        if "=" in line:
            key, value = line.strip().split("=", 1)
            os.environ[key] = value

app.secret_key = os.environ["FLASK_SECRET_KEY"]
UPLOAD_PASSWORD = os.environ["UPLOAD_PASSWORD"]

UPLOAD_DIR = "/home/ubuntu/flaskapp/static/files"


# =====================================================
#  LOGIN (FIXED WITH REDIRECT TO ORIGINAL DESTINATION)
# =====================================================
@app.route('/upload', methods=['GET', 'POST'])
def upload_login():
    """Password prompt with redirect support."""

    # If user was sent here from another protected page, store return URL
    next_page = request.args.get("next")
    if next_page:
        session["next"] = next_page

    if request.method == 'POST':
        if request.form.get("password") == UPLOAD_PASSWORD:
            session["upload_auth"] = True

            # Return user to original destination if available
            redirect_target = session.pop("next", None)
            if redirect_target:
                return redirect(redirect_target)

            # Fallback if no destination
            return redirect(url_for("upload_form"))

        else:
            return render_template("upload_login.html", error="Incorrect password")

    return render_template("upload_login.html")


# =====================================================
#  S3 UPLOAD
# =====================================================
@app.route("/s3/upload", methods=["GET", "POST"])
def s3_upload():
    if not session.get("upload_auth"):
        return redirect(url_for("upload_login", next=request.path))

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
def upload_form():
    if not session.get("upload_auth"):
        return redirect(url_for("upload_login", next=request.path))

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
