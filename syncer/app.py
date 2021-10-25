from flask import Flask
from flask_sqlalchemy import SQLAlchemy


db = SQLAlchemy()


app = Flask(__name__)
app.config.from_object("config.Config")

db.init_app(app)

with app.app_context():
    from routes import sync_routes
    from models.sync_models import SyncJobs

    db.create_all()

