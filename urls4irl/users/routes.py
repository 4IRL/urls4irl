from flask import Blueprint, jsonify, redirect, url_for, render_template, request
from werkzeug.security import check_password_hash
from flask_login import current_user, login_required, login_user, logout_user
from urls4irl import db
from urls4irl.models import Utub, Utub_Users, User
from urls4irl.users.forms import LoginForm, UserRegistrationForm, UTubNewUserForm

users = Blueprint('users', __name__)

@users.route('/login', methods=["GET", "POST"])
def login():
    """Login page. Allows user to register or login."""
    if current_user.is_authenticated:
        return redirect(url_for('main.home'))

    login_form = LoginForm()

    if login_form.validate_on_submit():
        username = login_form.username.data
        user = User.query.filter_by(username=username).first()

        if user and user.is_password_correct(login_form.password.data):
            login_user(user)    # Can add Remember Me functionality here
            next_page = request.args.get('next')    # Takes user to the page they wanted to originally before being logged in

            return redirect(next_page) if next_page else redirect(url_for('main.home'))
        else:
            return render_template('login.html', login_form=login_form), 400

    return render_template('login.html', login_form=login_form)

@users.route('/logout')
def logout():
    """Logs user out by clearing session details. Returns to login page."""
    logout_user()
    return redirect(url_for('users.login'))

@users.route('/register', methods=["GET", "POST"])
def register_user():
    """Allows a user to register an account."""
    if current_user.is_authenticated:
        return redirect(url_for('main.home'))

    register_form = UserRegistrationForm()

    if register_form.validate_on_submit():
        username = register_form.username.data
        email = register_form.email.data
        plain_password = register_form.password.data
        new_user = User(username=username, email=email, plaintext_password=plain_password, email_confirm=False)
        db.session.add(new_user)
        db.session.commit()
        user = User.query.filter_by(username=username).first()
        login_user(user)
        return redirect(url_for('main.home'))

    return render_template('register_user.html', register_form=register_form)

@users.route('/user/remove/<int:utub_id>/<int:user_id>',  methods=["POST"])
@login_required
def delete_user(utub_id: int, user_id: int):
    """
    Delete a user from a Utub. The creator of the Utub can delete anyone but themselves.
    Any user can remove themselves from a UTub they did not create.

    Args:
        utub_id (int): ID of the UTub to remove the user from
        user_id (int): ID of the User to remove from the UTub
    """
    current_utub = Utub.query.get_or_404(int(utub_id))

    if int(user_id) == int(current_utub.created_by.id):
        # Creator tried to delete themselves, not allowed
        return jsonify({
            "Status" : "Failure",
            "Message" : "UTub creator cannot remove themselves",
            "Error_code": 1
        }), 400

    current_user_ids_in_utub = [int(member.user_id) for member in current_utub.members]

    if int(user_id) not in current_user_ids_in_utub:
        # User not in this Utub
        return jsonify({
            "Status" : "Failure",
            "Message" : "User not found in this UTub",
            "Error_code": 2
        }), 400

    if int(current_user.get_id()) == int(current_utub.created_by.id):
        # Creator of utub wants to delete someone
        user_to_delete_in_utub = [member_to_delete for member_to_delete in current_utub.members if int(user_id) == (member_to_delete.user_id)][0]

    elif int(current_user.get_id()) in current_user_ids_in_utub and int(user_id) == int(current_user.get_id()):
        # User in this UTub and user wants to remove themself
        user_to_delete_in_utub = [member_to_delete for member_to_delete in current_utub.members if int(user_id) == (member_to_delete.user_id)][0]

    else:
        # Only creator of UTub can delete other users, only you can remove yourself
        return jsonify({
            "Status" : "Failure",
            "Message" : "Not allowed to remove a user from this UTub",
            "Error_code": 3
            }), 403
    
    current_utub.members.remove(user_to_delete_in_utub)
    db.session.commit()

    return jsonify({
        "Status" : "Success",
        "Message" : "User removed",
        "User_ID" : f"{user_id}",
        "UTub_ID" : f"{utub_id}",
        "UTub_name" : f"{current_user.name}",
    }), 200

@users.route('/user/add/<int:utub_id>', methods=["POST"])
@login_required
def add_user(utub_id: int):
    """
    Creater of utub wants to add a user to the utub.
    
    Args:
        utub_id (int): The utub that this user is being added to
    """
    utub = Utub.query.get_or_404(utub_id)

    if int(utub.created_by.id) != int(current_user.get_id()):
        # User not authorized to add a user to this UTub
        return jsonify({
            "Status" : "Failure",
            "Message" : "Not authorized",
            "Error_code": 1
        }), 403

    utub_new_user_form = UTubNewUserForm()

    if utub_new_user_form.validate_on_submit():
        username = utub_new_user_form.username.data
        
        new_user = User.query.filter_by(username=username).first()
        already_in_utub = [member for member in utub.members if int(member.user_id) == int(new_user.id)]

        if already_in_utub:
            # User already exists in UTub
            return jsonify({
                "Status" : "Failure",
                "Message" : "User already in UTub",
                "Error_code": 2
            }), 400
        
        else:
            new_user_to_utub = Utub_Users()
            new_user_to_utub.to_user = new_user
            utub.members.append(new_user_to_utub)
            db.session.commit()
            
            # Successfully added user to UTub
            return jsonify({
                "Status" : "Success",
                "Message" : "User added",
                "User_ID" : f"{new_user.id}",
                "UTub_ID" : f"{utub_id}",
                "UTub_name" : f"{current_user.name}",
            }), 200

    if utub_new_user_form.errors is not None:
        return jsonify({
            "Status" : "Failure",
            "Message" : "Unable to add that user to this UTub",
            "Error_code": 3,
            "Errors": utub_new_user_form.errors
        }), 404


    return jsonify({
        "Status" : "Failure",
        "Message" : "Unable to add that user to this UTub",
        "Error_code": 4
    }), 404
