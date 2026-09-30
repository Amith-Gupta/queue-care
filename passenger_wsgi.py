import sys
import os

# Add current project directory to system path
project_dir = os.path.dirname(os.path.abspath(__file__))
if project_dir not in sys.path:
    sys.path.insert(0, project_dir)

# Import Flask application object
from app import app as application
