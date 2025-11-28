"""
Flask extensions initialization
"""
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from authlib.integrations.flask_client import OAuth

# Initialize extensions
db = SQLAlchemy()
login_manager = LoginManager()
oauth = OAuth()
