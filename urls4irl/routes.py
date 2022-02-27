from werkzeug.security import check_password_hash, generate_password_hash
from flask import render_template, url_for, redirect, flash, request
from urls4irl import app, db
from urls4irl.forms import UserRegistrationForm, LoginForm, UTubForm, UTubNewUserForm, UTubNewURLForm
from urls4irl.models import User, Utub, URLS, UtubUrls
from flask_login import login_user, login_required, current_user, logout_user

"""#####################        MAIN ROUTES        ###################"""

@app.route('/')
def splash():
    """Splash page for either an unlogged in user.

    """
    return redirect(url_for('home'))
    #return render_template('splash.html')

@app.route('/home')
@login_required
def home():
    """Splash page for logged in user. Loads and displays all UTubs, and contained URLs."""
    utubs = Utub.query.filter(Utub.users.any(id=int(current_user.get_id()))).all()
    return render_template('home.html', utubs=utubs)

"""#####################        END MAIN ROUTES        ###################"""

"""#####################        USER LOGIN/LOGOUT/REGISTRATION ROUTES        ###################"""

@app.route('/login', methods=["GET", "POST"])
def login():
    """Login page. Allows user to register or login."""
    if current_user.is_authenticated:
        return redirect(url_for('home'))

    if not User.query.filter().all():
        """!!! Added users for testing !!!"""
        password = generate_password_hash('abcdefg', method='pbkdf2:sha512', salt_length=16)
        password2 = generate_password_hash('rehreh', method='pbkdf2:sha512', salt_length=16)
        new_user = User(username="Giovanni", email='gio@g.com', email_confirm=False, password=password)
        new_user2 = User(username="Rehan", email='Reh@reh.com', email_confirm=False, password=password2)
        db.session.add(new_user)
        db.session.add(new_user2)
        db.session.commit()
        flash("Added test user.", category='info')

    login_form = LoginForm()

    if login_form.validate_on_submit():
        username = login_form.username.data
        user = User.query.filter_by(username=username).first()

        if user and check_password_hash(user.password, login_form.password.data):
            login_user(user)    # Can add Remember Me functionality here
            next_page = request.args.get('next')    # Takes user to the page they wanted to originally before being logged in

            flash(f"Successful login, {username}", category="success")
            return redirect(next_page) if next_page else redirect(url_for('home'))
        else:
            flash(f"Login Unsuccessful. Please check username and password.", category="danger")

    return render_template('login.html', login_form=login_form)

@app.route('/logout')
def logout():
    """Logs user out by clearing session details. Returns to login page."""
    logout_user()
    return redirect(url_for('login'))

@app.route('/register', methods=["GET", "POST"])
def register_user():
    """Register a user page."""
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

"""#####################        END USER LOGIN/LOGOUT/REGISTRATION ROUTES        ###################"""

"""#####################        UTUB INVOLVED ROUTES        ###################"""

@app.route('/create_utub', methods=["GET", "POST"])
@login_required
def create_utub():
    """User wants to create a new utub."""

    utub_form = UTubForm()

    if utub_form.validate_on_submit():
        name = utub_form.name.data
        new_utub = Utub(name=name, user_id=current_user.get_id())

        new_utub.users.append(current_user)
        db.session.add(new_utub)
        db.session.commit()
        flash(f"Successfully made your UTub named {name}", category="success")
        return redirect(url_for('home'))

    flash("Okay let's get you a new UTub!", category="primary")
    return render_template('create_utub.html', utub_form=utub_form)

@app.route('/add_user/<int:utub_id>', methods=["GET", "POST"])
@login_required
def add_user(utub_id):
    """Creater of utub wants to add a user to the utub."""
    utub = Utub.query.get(int(utub_id))

    if int(utub.created_by.id) != int(current_user.get_id()):
        flash("Not authorized to add a user to this UTub", category="danger")
        return redirect(url_for('home'))

    utub_new_user_form = UTubNewUserForm()

    if utub_new_user_form.validate_on_submit():
        username = utub_new_user_form.username.data
        
        new_user = User.query.filter_by(username=username).first()
        already_in_utub = [user for user in utub.users if int(user.id) == int(new_user.id)]

        if already_in_utub:
            flash("This user already exists in the UTub.", category="danger")
        
        else:
            utub.users.append(new_user)
            db.session.add(utub)
            db.session.commit()
            flash(f"Successfully added {username} to {utub.name}", category="success")
            return redirect(url_for('home'))

    return render_template('add_user_to_utub.html', utub_new_user_form=utub_new_user_form)

@app.route('/add_url/<int:utub_id>', methods=["GET", "POST"])
@login_required
def add_url(utub_id: int):
    """User wants to add URL to UTub."""
    utub = Utub.query.get(int(utub_id))

    if int(current_user.get_id()) not in [int(user.id) for user in utub.users]:
        flash("Not authorized to add a URL to this UTub", category="danger")
        return redirect(url_for('home'))

    utub_new_url_form = UTubNewURLForm()

    if utub_new_url_form.validate_on_submit():
        url_string = utub_new_url_form.url_string.data
    
        # Get URL if already created
        already_created_url = URLS.query.filter_by(url_string=url_string).first()

        if already_created_url:
            url_utub_user_add = UtubUrls(utub_id=utub_id, url_id=already_created_url.id, user_id=int(current_user.get_id()))
        
        else:
            # Else create new URL and appends to the UTUB
            new_url = URLS(url_string=url_string, created_by=int(current_user.get_id()))
            db.session.add(new_url)
            db.session.commit()
            url_utub_user_add = UtubUrls(utub_id=utub_id, url_id=new_url.id, user_id=int(current_user.get_id()))
            
        db.session.add(url_utub_user_add)
        db.session.commit()

        flash(f"Added {url_string} to {utub.name}", category="info")
        return redirect(url_for('home'))
        

    return render_template('add_url_to_utub.html', utub_new_url_form=utub_new_url_form)

@app.route('/delete_utub/<int:utub_id>/<int:owner_id>', methods=["POST"])
@login_required
def delete_utub(utub_id: int, owner_id: int):
    """Creator wants to delete their UTub."""
    
    if int(current_user.get_id()) != owner_id:
        flash("You do not have permission to delete this UTub", category="danger")
    
    else:
        flash("You are the owner and want to delete this UTub.", category="danger")
        # Delete UTub functionality here.

    return redirect(url_for('home'))

"""#####################        END UTUB INVOLVED ROUTES        ###################"""
