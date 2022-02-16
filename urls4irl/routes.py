from flask import render_template, url_for, redirect
from urls4irl import app
from urls4irl.forms import UserRegistrationForm, LoginForm


@app.route('/')
def home():
    return render_template('index.html')

@app.route('/login')
def login():
    return "Login"

@app.route('/register')
def register_user():
    return "Register"