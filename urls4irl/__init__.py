from flask import Flask
from flask_session import Session
from urls4irl.config import Config

app = Flask(__name__)
app.config.from_object(Config)
Session(app)


from urls4irl import routes
