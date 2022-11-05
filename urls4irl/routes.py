from audioop import cross
from werkzeug.security import check_password_hash, generate_password_hash
from flask import render_template, url_for, redirect, flash, request, jsonify, abort
from urls4irl import app, db
from urls4irl.forms import (UserRegistrationForm, LoginForm, UTubForm, UTubDeleteForm, 

                            UTubNewUserForm, UTubNewURLForm, UTubNewUrlTagForm, UTubDescriptionForm)
from urls4irl.models import User, Utub, URLS, Utub_Urls, Tags, Url_Tags, Utub_Users
from flask_login import login_user, login_required, current_user, logout_user
from urls4irl.url_validation import InvalidURLError, check_request_head
from flask_cors import cross_origin

import sys

"""#####################        MAIN ROUTES        ###################"""

@app.route('/')
def splash():
    """Splash page for either an unlogged in user.

    """

    # Test code until splash page built in

    # Test code until splash page built in
    username = 'Giovanni'
    user = User.query.filter_by(username=username).first()
    login_user(user) 
    return redirect(url_for('home'))

@app.route('/home', methods=["GET"])
@login_required
def home():
    """
    Splash page for logged in user. Loads and displays all UTubs, and contained URLs.
    
    Args:
        /home : With no args, this returns all UTubIDs for the given user
        /home?UTubID=[int] = Where the integer value is the associated UTubID
                                that the user clicked on

    Returns:
        - All UTubIDs if no args
        - Requested UTubID if a valid arg

    """
    if not request.args:
        # User got here without any arguments in the URL
        # Therefore, only provide UTub name and UTub ID
        utub_details = current_user.serialized_on_initial_load
        return render_template('home.html', utubs_for_this_user=utub_details)

    elif len(request.args) > 1:
        # Too many args in URL
        return abort(404)

    else:
        if 'UTubID' not in request.args:
            # Wrong argument
            return abort(404)
            
        requested_id = request.args.get('UTubID')

        utub = Utub.query.get_or_404(requested_id)
        
        if int(current_user.get_id()) not in [int(member.user_id) for member in utub.members]:
            # User is not member of the UTub they are requesting
            return abort(403)

        utub_data_serialized = utub.serialized

        return jsonify(utub_data_serialized)


"""#####################        END MAIN ROUTES        ###################"""

"""#####################        USER LOGIN/LOGOUT/REGISTRATION ROUTES        ###################"""

@app.route('/login', methods=["GET", "POST"])
def login():
    """Login page. Allows user to register or login."""
    if current_user.is_authenticated:
        return redirect(url_for('home'))

    response_code = 200

    if not User.query.filter().all():
        """!!! Added users for testing !!!"""
        password = generate_password_hash('abcdefg', method='pbkdf2:sha512', salt_length=16)
        password2 = generate_password_hash('rehreh', method='pbkdf2:sha512', salt_length=16)
        password3 = generate_password_hash('bobob', method='pbkdf2:sha512', salt_length=16)
        new_user = User(username="Giovanni", email='gio@g.com', email_confirm=False, password=password)
        new_user2 = User(username="Rehan", email='Reh@reh.com', email_confirm=False, password=password2)
        new_user3 = User(username="Bobo", email='Bob@bob.com', email_confirm=False, password=password3)
        db.session.add(new_user)
        db.session.add(new_user2)
        db.session.add(new_user3)
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
            response_code = 400

    return render_template('login.html', login_form=login_form), response_code

@app.route('/logout')
def logout():
    """Logs user out by clearing session details. Returns to login page."""
    logout_user()
    return redirect(url_for('login'))

@app.route('/register', methods=["GET", "POST"])
def register_user():
    """Allows a user to register an account."""
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
        return redirect(url_for('home'))

    return render_template('register_user.html', register_form=register_form)

"""#####################        END USER LOGIN/LOGOUT/REGISTRATION ROUTES        ###################"""

"""#####################        UTUB INVOLVED ROUTES        ###################"""

@app.route('/create_utub', methods=["GET", "POST"])
@login_required
def create_utub():
    """
    User wants to create a new utub.
    Assocation Object:
    https://docs.sqlalchemy.org/en/14/orm/basic_relationships.html#many-to-many
    
    """

    utub_form = UTubForm()

    if utub_form.validate_on_submit():
        name = utub_form.name.data
        new_utub = Utub(name=name, utub_creator=current_user.get_id())
        creator_to_utub = Utub_Users()
        creator_to_utub.to_user = current_user
        new_utub.members.append(creator_to_utub)
        db.session.commit()
        # flash(f"Successfully made your UTub named {name}", category="success")
        return jsonify({"UtubID" : f"{new_utub.id}", "UtubName" : f"{new_utub.name}"})

    # flash("Okay let's get you a new UTub!", category="primary")
    return render_template('_create_utub_form.html', utub_form=utub_form)   

@app.route('/delete_utub/<int:utub_id>', methods=["GET", "POST"])
@login_required
def delete_utub(utub_id: int):
    """
    Creator wants to delete their UTub. It deletes all associations between this UTub and its contained
    URLS and users.

    https://docs.sqlalchemy.org/en/13/orm/cascades.html#delete

    Args:
        utub_id (int): The ID of the UTub to be deleted
    """
    utub_delete_form = UTubDeleteForm()

    if request.method == "GET":
        return render_template('_delete_utub_form.html', utub_delete_form=utub_delete_form)

    else:
        try:
            utub_id_to_delete = int(utub_id)
        except ValueError: 
            return jsonify({"Error": "You don't have permission to delete this UTub!"}), 404

        utub = Utub.query.get_or_404(utub_id_to_delete)

        if int(current_user.get_id()) != int(utub.created_by.id):  
            return jsonify({"Error": "You don't have permission to delete this UTub!"}), 403
        
        else:
            utub = Utub.query.get(int(utub_id))
            db.session.delete(utub)
            db.session.commit()
            return jsonify({"UtubID" : f"{utub.id}", "UtubName" : f"{utub.name}"})

@app.route('/update_utub_desc/<int:utub_id>', methods=["GET", "POST"])
@login_required
def update_utub_desc(utub_id: int):
    """
    Creator wants to update their UTub description.
    Description limit is 500 characters.
    Form data required to be sent from the frontend with a parameter "url_description".
    
    On GET:
            The previous UTub's description is sent as JSON to be included in the form for editing.

    On POST:
            The new description is saved to the database for that UTub.
        Requires a JSON in the POST request body.
    Example:
    {
        "utub_description": "New UTub description."
    }

    Args:
        utub_id (int): The ID of the UTub that will have its description updated
    """
    current_utub = Utub.query.get(int(utub_id))
    
    if int(current_user.get_id()) not in [int(member.user_id) for member in current_utub.members]:
        flash("Not authorized to add a description to this UTub.", category="danger")
        return home(), 403

    current_utub_description = current_utub.utub_description

    if current_utub_description is None:
        current_utub_description = ""

    utub_desc_form = UTubDescriptionForm()

    if utub_desc_form.validate_on_submit():
        new_utub_description = utub_desc_form.utub_description.data

        if new_utub_description != current_utub_description:
            current_utub.utub_description = new_utub_description
            db.session.commit()

        return redirect(url_for('home', UTubID=utub_id))

    utub_description_for_get = {
        "utub_description": current_utub_description
    }
    return render_template('add_desc_to_utub.html', desc_form=utub_desc_form, current_utub_desc=utub_description_for_get)

"""#####################        END UTUB INVOLVED ROUTES        ###################"""

"""#####################        USER INVOLVED ROUTES        ###################"""

@app.route('/delete_user/<int:utub_id>/<int:user_id>',  methods=["POST"])
@login_required
def delete_user(utub_id: int, user_id: int):
    """
    Delete a user from a Utub. The creator of the Utub can delete anyone but themselves.
    Any user can remove themselves from a UTub they did not create.

    Args:
        utub_id (int): ID of the UTub to remove the user from
        user_id (int): ID of the User to remove from the UTub
    """
    current_utub = Utub.query.get(int(utub_id))

    if int(user_id) == int(current_utub.created_by.id):
        # Creator tried to delete themselves
        flash("Creator of a UTub cannot be removed.", category="danger")
        return home(), 400

    current_user_ids_in_utub = [int(member.user_id) for member in current_utub.members]

    if int(user_id) not in current_user_ids_in_utub:
        # User not in this Utub
        flash("Can't remove a user that isn't in this UTub.", category="danger")
        return home(), 400

    if int(current_user.get_id()) == int(current_utub.created_by.id):
        # Creator of utub wants to delete someone
        user_to_delete_in_utub = [member_to_delete for member_to_delete in current_utub.members if int(user_id) == (member_to_delete.user_id)][0]

    elif int(current_user.get_id()) in current_user_ids_in_utub and int(user_id) == int(current_user.get_id()):
        # User in this UTub and user wants to remove themself
        user_to_delete_in_utub = [member_to_delete for member_to_delete in current_utub.members if int(user_id) == (member_to_delete.user_id)][0]

    else:
        flash("Error: Only the creator of a UTub can delete other users. Only you can remove yourself.", category="danger")
        return home, 403
    
    current_utub.members.remove(user_to_delete_in_utub)
    db.session.commit()

    return redirect(url_for('home', UTubID=utub_id))

@app.route('/delete_utub/<int:utub_id>', methods=["POST"])
@login_required
def delete_utub(utub_id: int):
    """
    Creator wants to delete their UTub. It deletes all associations between this UTub and its contained
    URLS and users.

    https://docs.sqlalchemy.org/en/13/orm/cascades.html#delete

    Args:
        utub_id (int): The ID of the UTub to be deleted
    """
    utub = Utub.query.get(int(utub_id))

    if int(current_user.get_id()) != int(utub.created_by.id):
        flash("You do not have permission to delete this UTub.", category="danger")
        return home(), 403
    
    else:
        utub = Utub.query.get(int(utub_id))
        db.session.delete(utub)
        db.session.commit()
        flash("You successfully deleted this UTub.", category="danger")

        return redirect(url_for('home'))

@app.route('/update_utub_desc/<int:utub_id>', methods=["GET", "POST"])
@login_required
def update_utub_desc(utub_id: int):
    """
    Creator wants to update their UTub description.
    Description limit is 500 characters.
    Form data required to be sent from the frontend with a parameter "url_description".
    
    On GET:
            The previous UTub's description is sent as JSON to be included in the form for editing.

    On POST:
            The new description is saved to the database for that UTub.
        Requires a JSON in the POST request body.
    Example:
    {
        "utub_description": "New UTub description."
    }

    Args:
        utub_id (int): The ID of the UTub that will have its description updated
    """
    current_utub = Utub.query.get(int(utub_id))
    
    if int(current_user.get_id()) not in [int(member.user_id) for member in current_utub.members]:
        flash("Not authorized to add a description to this UTub.", category="danger")
        return home(), 403

    current_utub_description = current_utub.utub_description

    if current_utub_description is None:
        current_utub_description = ""

    utub_desc_form = UTubDescriptionForm()

    if utub_desc_form.validate_on_submit():
        new_utub_description = utub_desc_form.utub_description.data

        if new_utub_description != current_utub_description:
            current_utub.utub_description = new_utub_description
            db.session.commit()

        return redirect(url_for('home', UTubID=utub_id))

    utub_description_for_get = {
        "utub_description": current_utub_description
    }
    return render_template('add_desc_to_utub.html', desc_form=utub_desc_form, current_utub_desc=utub_description_for_get)

"""#####################        END UTUB INVOLVED ROUTES        ###################"""

"""#####################        USER INVOLVED ROUTES        ###################"""

@app.route('/delete_user/<int:utub_id>/<int:user_id>',  methods=["POST"])
@login_required
def delete_user(utub_id: int, user_id: int):
    """
    Delete a user from a Utub. The creator of the Utub can delete anyone but themselves.
    Any user can remove themselves from a UTub they did not create.

    Args:
        utub_id (int): ID of the UTub to remove the user from
        user_id (int): ID of the User to remove from the UTub
    """
    current_utub = Utub.query.get(int(utub_id))

    if int(user_id) == int(current_utub.created_by.id):
        # Creator tried to delete themselves
        flash("Creator of a UTub cannot be removed.", category="danger")
        return home(), 400

    current_user_ids_in_utub = [int(member.user_id) for member in current_utub.members]

    if int(user_id) not in current_user_ids_in_utub:
        # User not in this Utub
        flash("Can't remove a user that isn't in this UTub.", category="danger")
        return home(), 400

    if int(current_user.get_id()) == int(current_utub.created_by.id):
        # Creator of utub wants to delete someone
        user_to_delete_in_utub = [member_to_delete for member_to_delete in current_utub.members if int(user_id) == (member_to_delete.user_id)][0]

    elif int(current_user.get_id()) in current_user_ids_in_utub and int(user_id) == int(current_user.get_id()):
        # User in this UTub and user wants to remove themself
        user_to_delete_in_utub = [member_to_delete for member_to_delete in current_utub.members if int(user_id) == (member_to_delete.user_id)][0]

    else:
        flash("Error: Only the creator of a UTub can delete other users. Only you can remove yourself.", category="danger")
        return home, 403
    
    current_utub.members.remove(user_to_delete_in_utub)
    db.session.commit()

    return redirect(url_for('home', UTubID=utub_id))

@app.route('/add_user/<int:utub_id>', methods=["GET", "POST"])
@login_required
def add_user(utub_id: int):
    """
    Creater of utub wants to add a user to the utub.
    
    Args:
        utub_id (int): The utub that this user is being added to
    """
    utub = Utub.query.get(utub_id)

    if int(utub.created_by.id) != int(current_user.get_id()):
        flash("Not authorized to add a user to this UTub", category="danger")
        return abort(403)

    utub_new_user_form = UTubNewUserForm()

    if utub_new_user_form.validate_on_submit():
        username = utub_new_user_form.username.data
        
        new_user = User.query.filter_by(username=username).first()
        already_in_utub = [member for member in utub.members if int(member.user_id) == int(new_user.id)]

        if already_in_utub:
            flash("This user already exists in the UTub.", category="danger")
            return home(), 400
        
        else:
            new_user_to_utub = Utub_Users()
            new_user_to_utub.to_user = new_user
            utub.members.append(new_user_to_utub)
            db.session.commit()
            flash(f"Successfully added {username} to {utub.name}", category="success")
            return redirect(url_for('home', UTubID=utub_id))

    return render_template('add_user_to_utub.html', utub_new_user_form=utub_new_user_form)

"""#####################        END USER INVOLVED ROUTES        ###################"""

"""#####################        URL INVOLVED ROUTES        ###################"""


@app.route('/delete_url/<int:utub_id>/<int:url_id>', methods=["POST"])
@login_required
def delete_url(utub_id: int, url_id: int):
    """
    User wants to delete a URL from a UTub. Only available to owner of that utub,
    or whoever added the URL into that Utub.

    Args:
        utub_id (int): The ID of the UTub that contains the URL to be deleted
        url_id (int): The ID of the URL to be deleted
    """
    utub = Utub.query.get(int(utub_id))
    owner_id = int(utub.created_by.id)
    
    # Search through all urls in the UTub for the one that matches the prescribed URL ID and get the user who added it - should be only one
    url_added_by = [url_in_utub.user_that_added_url.id for url_in_utub in utub.utub_urls if int(url_in_utub.url_id) == int(url_id)]

    if len(url_added_by) != 1 or not url_added_by:
        # No user added this URL, or multiple users did...
        flash("Something went wrong", category="danger")
        return abort(404)

    # Otherwise, only one user should've added this url - retrieve them
    url_added_by = url_added_by[0]

    if int(current_user.get_id()) == owner_id or int(current_user.get_id()) == url_added_by:
        # User is creator of this UTub, or added the URL
        utub_url_user_row = Utub_Urls.query.filter_by(utub_id=utub_id, url_id=url_id).all()

        if len(utub_url_user_row) > 1:
            # How did this happen? URLs are unique to each UTub, so should only return one
            flash("Error: Something went wrong", category="danger")
            return abort(404)

        db.session.delete(utub_url_user_row[0])
        db.session.commit()
        flash("You successfully deleted the URL from the UTub.", category="danger")
        return redirect(url_for('home', UTubID=utub_id))

    else:
        flash("Can only delete URLs you added, or if you are the creator of this UTub.", category="danger")
        return home(), 403


@app.route('/add_url/<int:utub_id>', methods=["GET", "POST"])
@login_required
def add_url(utub_id: int):
    """
    User wants to add URL to UTub. On success, adds the URL to the UTub.
    
    Args:
        utub_id (int): The Utub to add this URL to
    """
    utub = Utub.query.get(int(utub_id))

    if int(current_user.get_id()) not in [int(member.user_id) for member in utub.members]:
        flash("Not authorized to add a URL to this UTub", category="danger")

        return home(), 403

    utub_new_url_form = UTubNewURLForm()

    if utub_new_url_form.validate_on_submit():
        url_string = utub_new_url_form.url_string.data

        try:
            validated_url = check_request_head(url_string)
        
        except InvalidURLError:
            flash(f"Invalid URL.", category="danger")
            return render_template('_add_url_form.html', utub_new_url_form=utub_new_url_form), 400


        else: 
            # Get URL if already created
            print(f"Validated URL: {validated_url}")
            already_created_url = URLS.query.filter_by(url_string=validated_url).first()

            if already_created_url:

                # Get all urls currently in utub
                urls_in_utub = [utub_user_url_object.url_in_utub for utub_user_url_object in utub.utub_urls]
            
                #URL already generated, now confirm if within UTUB or not
                if already_created_url in urls_in_utub:
                    # URL already in UTUB
                    flash(f"URL already in UTub", category="info")

                    return render_template('_add_url_form.html', utub_new_url_form=utub_new_url_form), 400


                url_utub_user_add = Utub_Urls(utub_id=utub_id, url_id=already_created_url.id, user_id=int(current_user.get_id()))

            else:
                # Else create new URL and append to the UTUB
                new_url = URLS(url_string=validated_url, created_by=int(current_user.get_id()))
                db.session.add(new_url)
                db.session.commit()
                url_utub_user_add = Utub_Urls(utub_id=utub_id, url_id=new_url.id, user_id=int(current_user.get_id()))
                
            db.session.add(url_utub_user_add)
            db.session.commit()

            flash(f"Added {url_string} to {utub.name}", category="info")
            return redirect(url_for('home', UTubID=utub_id))
        
    return render_template('_add_url_form.html', utub_new_url_form=utub_new_url_form)

"""#####################        END URL INVOLVED ROUTES        ###################"""

"""#####################        TAG INVOLVED ROUTES        ###################"""

@app.route('/add_tag/<int:utub_id>/<int:url_id>', methods=["GET", "POST"])
@login_required
def add_tag(utub_id: int, url_id: int):
    """
    User wants to add a tag to a URL. 5 tags per URL.
    
    Args:
        utub_id (int): The utub that this user is being added to
        url_id (int): The URL this user wants to add a tag to
    """
    utub = Utub.query.get(utub_id)
    utub_url = [url_in_utub for url_in_utub in utub.utub_urls if url_in_utub.url_id == url_id]
    user_in_utub = [int(member.user_id) for member in utub.members if int(member.user_id) == int(current_user.get_id())]

    if not user_in_utub or not utub_url:
        # How did a user not in this utub get access to add a tag to this URL?
        # How did a user try to add a tag to a URL not contained within the UTub?
        flash("Error has occurred", category="danger")
        return home(), 404
       
    url_tag_form = UTubNewUrlTagForm()

    if url_tag_form.validate_on_submit():

        tag_to_add = url_tag_form.tag_string.data

        # If too many tags, disallow adding tag
        tags_already_on_this_url = [tags for tags in utub.utub_url_tags if int(tags.url_id) == int(url_id)]

        if len(tags_already_on_this_url) > 4:
                # Cannot have more than 5 tags on a URL
                flash("You cannot add more tags to this URL.", category="danger")
                return home(), 400

        # If not a tag already, create it
        tag_already_created = Tags.query.filter_by(tag_string=tag_to_add).first()

        if tag_already_created:
            # Check if tag already on url
            this_tag_is_already_on_this_url = [tags for tags in tags_already_on_this_url if int(tags.tag_id) == int(tag_already_created.id)]

            if this_tag_is_already_on_this_url:
                flash("This tag is already on this URL", category="danger")
                return render_template('add_tag_to_url.html', url_tag_form=url_tag_form), 400

            # Associate with the UTub and URL
            utub_url_tag = Url_Tags(utub_id=utub_id, url_id=url_id, tag_id=tag_already_created.id)

        else:
            # Create tag, then associate with this UTub and URL
            new_tag = Tags(tag_string=tag_to_add, created_by=int(current_user.get_id()))
            db.session.add(new_tag)
            db.session.commit()
            utub_url_tag = Url_Tags(utub_id=utub_id, url_id=url_id, tag_id=new_tag.id)

        db.session.add(utub_url_tag)
        db.session.commit()

        flash(f"Added {tag_to_add} to {utub_url[0].url_in_utub.url_string}", category="info")

        return redirect(url_for('home', UTubID=utub_id))

    return render_template('add_tag_to_url.html', url_tag_form=url_tag_form)

@app.route('/remove_tag/<int:utub_id>/<int:url_id>/<int:tag_id>', methods=["POST"])
@login_required
def remove_tag(utub_id: int, url_id: int, tag_id: int):
    """
    User wants to delete a tag from a URL contained in a UTub. Only available to owner of that utub.

    Args:
        utub_id (int): The ID of the UTub that contains the URL to be deleted
        url_id (int): The ID of the URL to be deleted
        tag_id (int): The ID of the tag
    """
    utub = Utub.query.get(int(utub_id))
    owner_id = utub.utub_creator

    if int(current_user.get_id()) == owner_id:
        # User is creator of this UTub
        tag_for_url_in_utub = Url_Tags.query.filter_by(utub_id=utub_id, url_id=url_id, tag_id=tag_id).first()

        db.session.delete(tag_for_url_in_utub)
        db.session.commit()
        flash("You successfully deleted the tag from the URL.", category="danger")
        return redirect(url_for('home', UTubID=utub_id))

    return home(), 403

"""#####################        END TAG INVOLVED ROUTES        ###################"""