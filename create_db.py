"""
Creates the app's database if not already created. 
https://stackoverflow.com/questions/43713124/creating-a-database-in-flask-sqlalchemy    
"""

from urls4irl import db
from urls4irl import app

with app.test_request_context():
    db.init_app(app)
    db.create_all()