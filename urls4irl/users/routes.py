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

            return redirect(next_page) if next_page else url_for('main.home')
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
        return url_for('main.home')

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
    current_utub = Utub.query.get_or_404(utub_id)

    if user_id == current_utub.created_by.id:
        # Creator tried to delete themselves, not allowed
        return jsonify({
            "Status" : "Failure",
            "Message" : "UTub creator cannot remove themselves",
            "Error_code": 1
        }), 400

    current_user_ids_in_utub = [member.user_id for member in current_utub.members]
    current_user_id = current_user.id

    # User can't remove if current user is not in this current UTub's members
    # User can't remove if current user is not creator of UTub and requested user is not same as current user
    current_user_not_in_utub = current_user_id not in current_user_ids_in_utub
    member_trying_to_remove_another_member = current_user_id != current_utub.created_by.id and user_id != current_user_id
    
    if current_user_not_in_utub or member_trying_to_remove_another_member:
        return jsonify({
            "Status" : "Failure",
            "Message" : "Not allowed to remove a user from this UTub",
            "Error_code": 2
            }), 403

    if user_id not in current_user_ids_in_utub:
        return jsonify({
            "Status" : "Failure",
            "Message" : "User does not exist or not found in this UTub",
            "Error_code": 3
        }), 404

    user_to_delete_in_utub = Utub_Users.query.filter(Utub_Users.utub_id == utub_id, Utub_Users.user_id == user_id).first_or_404()

    deleted_user = User.query.get(user_id)
    deleted_user_username = deleted_user.username

    db.session.delete(user_to_delete_in_utub)
    db.session.commit()

    return jsonify({
        "Status" : "Success",
        "Message" : "User removed",
        "User_ID_removed" : f"{user_id}",
        "Username": f"{deleted_user_username}",
        "UTub_ID" : f"{utub_id}",
        "UTub_name" : f"{current_utub.name}",
        "UTub_users": [user.to_user.username for user in current_utub.members]
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

        new_user = User.query.filter_by(username=username).first_or_404()
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
                "User_ID_added" : int(new_user.id),
                "UTub_ID" : int(utub_id),
                "UTub_name" : f"{utub.name}",
                "UTub_users": [user.to_user.username for user in utub.members]
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
