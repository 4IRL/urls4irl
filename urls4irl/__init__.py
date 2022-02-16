from flask import Flask

app = Flask(__name__)
app.config.from_pyfile('config.py')


from urls4irl import routes
