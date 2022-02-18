from flask import Flask
from flask_session import Session
from flask_sqlalchemy import SQLAlchemy
from urls4irl.config import Config

app = Flask(__name__)
app.config.from_object(Config)
app.config['SQLALCHEMY_DATABASE_URI'] = "sqlite:///urls4irl_db.db"
Session(app)
db = SQLAlchemy(app)


from urls4irl import routes
