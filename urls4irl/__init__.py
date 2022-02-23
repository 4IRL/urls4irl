from flask import Flask
from flask_session import Session
from flask_sqlalchemy import SQLAlchemy
from urls4irl.config import Config
from flask_login import LoginManager


app = Flask(__name__)
app.config.from_object(Config)
app.config['SQLALCHEMY_DATABASE_URI'] = "sqlite:///urls4irl_db.db"
Session(app)
db = SQLAlchemy(app)
login_manager = LoginManager(app)



from urls4irl import routes
