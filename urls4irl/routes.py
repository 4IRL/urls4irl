from werkzeug.security import check_password_hash, generate_password_hash
from flask import render_template, url_for, redirect, flash, session
from urls4irl import app, db
from urls4irl.forms import UserRegistrationForm, LoginForm, UTubForm
# from urls4irl.helpers import login_required
from urls4irl.models import User, UTub
from flask_login import login_user, login_required, current_user, logout_user


#TODO Import User Model and add in account creation


@app.route('/')
def splash():
    """Splash page for either an unlogged in user.

    """
    return render_template('splash.html')

@app.route('/home')
@login_required
def home():
    """Splash page for logged in user"""    
    return render_template('home.html')


@app.route('/login', methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('home'))

    login_form = LoginForm()

    if login_form.validate_on_submit():
        username = login_form.username.data
        user = User.query.filter_by(username=username).first()

        if user and check_password_hash(user.password, login_form.password.data):
            login_user(user)    # Can add Remember Me functionality here
            print(session)
            flash(f"Successful login, {username}", category="success")
            return redirect(url_for("home"))
        else:
            flash(f"Login Unsuccessful. Please check username and password.", category="danger")

    return render_template('login.html', login_form=login_form)

@app.route('/logout')
def logout():
    """Logs user out by clearing session details. Returns to login page."""
    logout_user()
    return redirect(url_for('login'))

@app.route('/create_utub', methods=["GET", "POST"])
@login_required
def create_utub():
    """User wants to create a new utub."""

    utub_form = UTubForm()

    if utub_form.validate_on_submit():
        name = utub_form.name.data
        new_utub = UTub(name=name, user_id=current_user.get_id())
        db.session.add(new_utub)
        db.session.commit()
        flash(f"Successfully made the {name} UTub!", category="success")
        return redirect(url_for('home'))

    flash("Okay let's get you a new UTub!", category="primary")
    return render_template('create_utub.html', utub_form=utub_form)

@app.route('/register', methods=["GET", "POST"])
def register_user():
    if current_user.is_authenticated:
        return redirect(url_for('home'))

    register_form = UserRegistrationForm()

    if register_form.validate_on_submit():
        username = register_form.username.data
        email = register_form.email.data
        password = generate_password_hash(register_form.password.data, method='pbkdf2:sha512', salt_length=16)
        new_user = User(username=username, email=email, email_confirm=False, password=password)
        db.session.add(new_user)
        db.session.commit()
        user = User.query.filter_by(username=username).first()
        login_user(user)
        flash(f"Account created for {register_form.username.data}!", "success")
        return redirect(url_for("home"))

    return render_template('register_user.html', register_form=register_form)


