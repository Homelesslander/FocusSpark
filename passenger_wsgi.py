import sys
import os

# Add the current directory to Python path
project_home = u'/home/focusspark/www'
if project_home not in sys.path:
    sys.path.insert(0, project_home)

# Set environment variables for Flask
os.environ['FLASK_APP'] = 'app.py'
os.environ['FLASK_ENV'] = 'production'

# Import your Flask app
from app import app as application

# Set production mode
application.config['DEBUG'] = False
application.config['ENV'] = 'production'
