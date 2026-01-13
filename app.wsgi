import sys
import os
import logging

# Activate virtualenv
activate_this = '/home/ubuntu/flaskapp/venv/bin/activate_this.py'
with open(activate_this) as f:
    exec(f.read(), dict(__file__=activate_this))

# Add app directory to sys.path
sys.path.insert(0, "/var/www/html/flaskapp/")

# Logging to stderr (safe under mod_wsgi)
logging.basicConfig(
    stream=sys.stderr,
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)
logging.info("WSGI app starting...")

# Import the Flask app
from app import app as application
