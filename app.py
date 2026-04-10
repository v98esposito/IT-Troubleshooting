import os
import logging
from flask import Flask
import json
from extensions import db, login_manager, mail, csrf
from werkzeug.middleware.proxy_fix import ProxyFix

# Configure logging
logging.basicConfig(level=logging.DEBUG)

# Create the app
app = Flask(__name__)
app.secret_key = os.environ.get("SESSION_SECRET", "dev-secret-key-for-csrf-protection-2025")
app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)

# Configure the database
app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get("DATABASE_URL", "sqlite:///ticketing.db")
app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {
    "pool_recycle": 300,
    "pool_pre_ping": True,
}
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

# Configure email settings
app.config["MAIL_SERVER"] = os.environ.get("MAIL_SERVER", "smtp.gmail.com")
app.config["MAIL_PORT"] = int(os.environ.get("MAIL_PORT", 587))
app.config["MAIL_USE_TLS"] = True
app.config["MAIL_USERNAME"] = os.environ.get("MAIL_USERNAME", "")
app.config["MAIL_PASSWORD"] = os.environ.get("MAIL_PASSWORD", "")
app.config["MAIL_DEFAULT_SENDER"] = os.environ.get("MAIL_DEFAULT_SENDER", "noreply@ittickets.com")

# Set upload folder for attachments
app.config["UPLOAD_FOLDER"] = "uploads"
app.config["MAX_CONTENT_LENGTH"] = 16 * 1024 * 1024  # 16MB max upload

# Initialize extensions with app
db.init_app(app)
login_manager.init_app(app)
login_manager.login_view = "login"
login_manager.login_message_category = "info"
mail.init_app(app)
csrf.init_app(app)

# Create upload folder if it doesn't exist
# Using app.root_path to ensure the path is relative to the app's root
upload_folder_path = os.path.join(app.root_path, app.config["UPLOAD_FOLDER"])
if not os.path.exists(upload_folder_path):
    os.makedirs(upload_folder_path)

# Import models and create tables
with app.app_context():
    from models import User, Ticket, TicketStatus, Comment, Attachment, Category, Department, PasswordReset
    db.create_all()

# Run the app
if __name__ == '__main__':
    # Import and register routes
    from routes import register_routes
    register_routes(app)
    
    # Run the app
    app.run(debug=True, host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))

# Custom Jinja2 filter for escaping JavaScript
@app.template_filter('escapejs')
def escapejs_filter(value):
    if value is None:
        return ''
    # Using json.dumps to safely escape strings for JavaScript context
    # The slicing [1:-1] removes the surrounding double quotes added by json.dumps
    return json.dumps(str(value))[1:-1]


# If you intend to run this file directly for development (though main.py is preferred):
# if __name__ == '__main__':
#     app.run(debug=True, host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))
