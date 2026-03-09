import sys
import os

# Make sure the root of the project is in the path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app

app = create_app("production")

# Vercel needs the WSGI app exposed as `app`
