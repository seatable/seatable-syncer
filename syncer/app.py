from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_webpack_loader import WebpackLoader


db = SQLAlchemy()


app = Flask(__name__, static_folder='../static')
app.config.from_object("config.Config")

webpack_loader = WebpackLoader(app)

db.init_app(app)

with app.app_context():
    from routes import sync_routes
    from models.sync_models import SyncJobs

    db.create_all()

