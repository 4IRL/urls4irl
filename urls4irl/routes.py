from atexit import register
from flask import render_template, url_for, redirect, flash, session
from urls4irl import app
from urls4irl.forms import UserRegistrationForm, LoginForm
from urls4irl.helpers import login_required
from urls4irl.models import User

#TODO Import User Model and add in account creation


@app.route('/')
def splash():
    """Splash page for either an unlogged in or logged in user.

    Args:
        user (_type_, optional): _description_. Defaults to None.

    Returns:
        _type_: _description_
    """
    return render_template('index.html')

@app.route('/home/<user>')
@login_required
def home(user):
    """Splash page for logged in user"""
    flash(f"Successful login, {user}", category="success")
    return render_template('index.html', user=user)


@app.route('/login', methods=["GET", "POST"])
def login():
    login_form = LoginForm()

    if login_form.validate_on_submit():
        username = login_form.username.data
        print(login_form.username.data)
        print(login_form.password.data)
        session["user_id"] = 0
        print("Session id is: ", session["user_id"])
        return redirect(url_for("home", user=username))

    return render_template('login.html', login_form=login_form)

@app.route('/logout')
def logout():
    """Logs user out by clearing session details. Returns to login page."""
    session.clear()
    return redirect(url_for('login'))

@app.route('/register', methods=["GET", "POST"])
def register_user():
    register_form = UserRegistrationForm()

    if register_form.validate_on_submit():
        print(register_form.username.data)
        print(register_form.email.data)
        print(register_form.password.data)
        flash(f"Account created for {register_form.username.data}!", "success")
        return redirect(url_for("home", user=register_form.username.data))

    return render_template('register_user.html', register_form=register_form)


