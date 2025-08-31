import os
import logging
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_socketio import SocketIO
from sqlalchemy.orm import DeclarativeBase
from werkzeug.middleware.proxy_fix import ProxyFix

# Configure logging
logging.basicConfig(level=logging.DEBUG)

class Base(DeclarativeBase):
    pass

db = SQLAlchemy(model_class=Base)

# Create the app
app = Flask(__name__)
app.secret_key = os.environ.get("SESSION_SECRET", "dev-secret-key-change-in-production")
app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)

# Configure the database
database_url = os.environ.get("DATABASE_URL", "sqlite:///hydrogen_platform.db")
app.config["SQLALCHEMY_DATABASE_URI"] = database_url
app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {
    "pool_recycle": 300,
    "pool_pre_ping": True,
}
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

# Initialize extensions
db.init_app(app)

# Initialize Flask-Login
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'
login_manager.login_message = 'Please log in to access this page.'
login_manager.login_message_category = 'info'

# Initialize SocketIO (simplified configuration)
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading', 
                   logger=False, engineio_logger=False, 
                   ping_timeout=60, ping_interval=25)

@login_manager.user_loader
def load_user(user_id):
    from models import User
    return User.query.get(int(user_id))

# Create tables and initialize data
with app.app_context():
    # Import models to ensure they're registered
    import models
    
    # Create all tables
    db.create_all()
    
    # Initialize system contracts
    try:
        from smart_contracts import SmartContractManager
        SmartContractManager.auto_deploy_system_contracts()
    except Exception as e:
        print(f"Warning: Could not auto-deploy system contracts: {e}")

# Import routes after app initialization
import routes
import websocket_events
