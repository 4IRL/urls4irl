"""
Creates the app's database if not already created. 
https://stackoverflow.com/questions/43713124/creating-a-database-in-flask-sqlalchemy    
"""

from urls4irl import db
from flask import current_app as app

# from flask_session import SqlAlchemySessionInterface


with app.test_request_context():
    db.init_app(app)
    # sess.app.session_interface.db.create_all()
    db.create_all()
