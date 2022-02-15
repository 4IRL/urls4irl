from flask import Flask, render_template, url_for, redirect
from forms import UserRegistrationForm, LoginForm


app = Flask(__name__)
app.config.from_object('config.Config')

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/login')
def login():
    return "Login"

@app.route('/register')
def register_user():
    return "Register"


if __name__ == "__main__":
    app.run()