from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from ddtrace import patch_all


db = SQLAlchemy()
patch_all()

def create_app():
    app = Flask(__name__)
    app.config.from_object("config.Config")

    db.init_app(app)

    with app.app_context():
        from routes import email_sync_routes
        return app
