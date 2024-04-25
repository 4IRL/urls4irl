"""
Creates the app's database if not already created.
https://stackoverflow.com/questions/43713124/creating-a-database-in-flask-sqlalchemy
"""

from run import app
from src import db

with app.app_context():
    db.init_app(app)
    db.create_all()
