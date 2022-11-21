from werkzeug.security import check_password_hash, generate_password_hash
from flask import render_template, url_for, redirect, flash, request, jsonify, abort
from urls4irl import app, db
from urls4irl.forms import (UserRegistrationForm, LoginForm, UTubForm,
                            UTubNewUserForm, UTubNewURLForm, UTubNewUrlTagForm, UTubDescriptionForm)
from urls4irl.models import User, Utub, URLS, Utub_Urls, Tags, Url_Tags, Utub_Users
from flask_login import login_user, login_required, current_user, logout_user
from urls4irl.url_validation import InvalidURLError, check_request_head
from flask_cors import cross_origin

"""#####################        MAIN ROUTES        ###################"""

@app.route('/')
def splash():
    """Splash page for either an unlogged in user.

    """

    return redirect(url_for('login'))

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

@app.route('/utub/new', methods=["POST"])
@login_required
def create_utub():
    """
    User wants to create a new utub.
    Assocation Object:
    https://docs.sqlalchemy.org/en/14/orm/basic_relationships.html#many-to-many
    
    """

    utub_form = UTubForm()

    if utub_form.validate_on_submit():
        print(utub_form)
        name = utub_form.name.data
        description = utub_form.description.data
        new_utub = Utub(name=name, utub_creator=current_user.get_id(), utub_description=description)
        creator_to_utub = Utub_Users()
        creator_to_utub.to_user = current_user
        new_utub.members.append(creator_to_utub)
        db.session.commit()
        
        # Add time made?
        return jsonify({
            "Status": "Success",
            "UTub_ID" : f"{new_utub.id}", 
            "UTub_name" : f"{new_utub.name}",
            "UTub_description" : f"{description}",
            "UTub_creator_id": f"{current_user.get_id()}"
        }), 200

    return jsonify({
        "Status": "Failure",
        "Message" : "Unable to generate a new UTub with that information."
    }), 404  

@app.route('/utub/delete/<int:utub_id>', methods=["POST"])
@login_required
def delete_utub(utub_id: int):
    """
    Creator wants to delete their UTub. It deletes all associations between this UTub and its contained
    URLS and users.

    https://docs.sqlalchemy.org/en/13/orm/cascades.html#delete

    Args:
        utub_id (int): The ID of the UTub to be deleted
    """
    try:
        # Is this necessary?
        utub_id_to_delete = int(utub_id)

    except ValueError: 
        return jsonify({
            "Status" : "Failure",
            "Message" : "You don't have permission to delete this UTub!"
        }), 404

    utub = Utub.query.get_or_404(utub_id_to_delete)

    if int(current_user.get_id()) != int(utub.created_by.id):  
        return jsonify({
            "Status" : "Failure",
            "Message": "You don't have permission to delete this UTub!"
        }), 403
    
    else:
        utub = Utub.query.get(int(utub_id))
        db.session.delete(utub)
        db.session.commit()

        return jsonify({
            "Status" : "Success",
            "Message" : "UTub deleted",
            "Utub_ID" : f"{utub.id}", 
            "Utub_name" : f"{utub.name}",
            "UTub_description" : f"{utub.utub_description}",
        }), 200

@app.route('/utub/edit_description/<int:utub_id>', methods=["POST"])
@login_required
def update_utub_desc(utub_id: int):
    """
    Creator wants to update their UTub description.
    Description limit is 500 characters.
    Form data required to be sent from the frontend with a parameter "url_description".
    
    On POST:
        The new description is saved to the database for that UTub.

    Args:
        utub_id (int): The ID of the UTub that will have its description updated
    """
    current_utub = Utub.query.get(int(utub_id))
    
    if int(current_user.get_id()) not in [int(member.user_id) for member in current_utub.members]:
        return jsonify({
            "Status" : "Failure",
            "Message": "You do not have permission to edit this UTub's description",
            "UTub_description": f"{current_utub.utub_description}"
        }), 403

    current_utub_description = "" if current_utub.utub_description is None else current_utub.utub_description

    utub_desc_form = UTubDescriptionForm()

    if utub_desc_form.validate_on_submit():
        new_utub_description = utub_desc_form.utub_description.data

        if new_utub_description != current_utub_description:
            current_utub.utub_description = new_utub_description
            db.session.commit()

        return jsonify({
            "Status": "Success",
            "UTub_ID": f"{current_utub.id}",
            "UTub_description": f"{current_utub.utub_description}"
        }), 200

    return jsonify({
        "Status" : "Failure",
        "Message" : "Unable to modify this UTub's description"
    }), 404

"""#####################        END UTUB INVOLVED ROUTES        ###################"""

"""#####################        USER INVOLVED ROUTES        ###################"""

@app.route('/utub/user/remove/<int:utub_id>/<int:user_id>',  methods=["POST"])
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
        # Creator tried to delete themselves, not allowed
        return jsonify({
            "Status" : "Failure",
            "Message" : "UTub creator cannot remove themselves"
        }), 400

    current_user_ids_in_utub = [int(member.user_id) for member in current_utub.members]

    if int(user_id) not in current_user_ids_in_utub:
        # User not in this Utub
        return jsonify({
            "Status" : "Failure",
            "Message" : "User not found in this UTub"
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
            "Message" : "Not allowed to remove a user from this UTub"
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

@app.route('/utub/user/add/<int:utub_id>', methods=["POST"])
@login_required
def add_user(utub_id: int):
    """
    Creater of utub wants to add a user to the utub.
    
    Args:
        utub_id (int): The utub that this user is being added to
    """
    utub = Utub.query.get(utub_id)

    if int(utub.created_by.id) != int(current_user.get_id()):
        # User not authorized to add a user to this UTub
        return jsonify({
            "Status" : "Failure",
            "Message" : "Not authorized"
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
                "Message" : "User already in UTub"
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

    return jsonify({
        "Status" : "Failure",
        "Message" : "Unable to add that user to this UTub"
    }), 404

"""#####################        END USER INVOLVED ROUTES        ###################"""

"""#####################        URL INVOLVED ROUTES        ###################"""


@app.route('/utub/url/remove/<int:utub_id>/<int:url_id>', methods=["POST"])
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
        return jsonify({
            "Status" : "Failure",
            "Message" : "Unable to remove this URL",
            "Error_code": 1
        }), 404

    # Otherwise, only one user should've added this url - retrieve them
    url_added_by = url_added_by[0]

    if int(current_user.get_id()) == owner_id or int(current_user.get_id()) == url_added_by:
        # User is creator of this UTub, or added the URL
        utub_url_user_row = Utub_Urls.query.filter_by(utub_id=utub_id, url_id=url_id).all()

        if len(utub_url_user_row) > 1:
            # How did this happen? URLs are unique to each UTub, so should only return one
            return jsonify({
                "Status" : "Failure",
                "Message" : "Unable to remove this URL",
                "Error_code": 2
            }), 404

        db.session.delete(utub_url_user_row[0])
        db.session.commit()
        
        return jsonify({
            "Status" : "Success",
            "Message": "URL removed from this UTub",
            "URL" : jsonify(URLS.query.get_or_404(url_id).serialized),
            "UTub_ID" : f"{utub.id}",
            "UTub_name" : f"{utub.name}"
        }), 200

    else:
        # Can only delete URLs you added, or if you are the creator of this UTub
        return jsonify({
                "Status" : "Failure",
                "Message" : "Unable to remove this URL",
                "Error_code": 3
            }), 403


@app.route('/utub/url/add/<int:utub_id>', methods=["POST"])
@login_required
def add_url(utub_id: int):
    """
    User wants to add URL to UTub. On success, adds the URL to the UTub.
    
    Args:
        utub_id (int): The Utub to add this URL to
    """
    utub = Utub.query.get(int(utub_id))

    if int(current_user.get_id()) not in [int(member.user_id) for member in utub.members]:
        # Not authorized to add URL to this UTub
        return jsonify({
            "Status" : "Failure",
            "Message" : "Unable to add this URL",
            "Error_code": 1
        }), 403

    utub_new_url_form = UTubNewURLForm()

    if utub_new_url_form.validate_on_submit():
        url_string = utub_new_url_form.url_string.data

        try:
            validated_url = check_request_head(url_string)
        
        except InvalidURLError:
            return jsonify({
                "Status" : "Failure",
                "Message" : "Unable to add this URL",
                "Error_code": 2
            }), 400

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
                    return jsonify({
                        "Status" : "Failure",
                        "Message" : "Unable to add this URL",
                        "Error_code": 3
                    }), 400


                url_utub_user_add = Utub_Urls(utub_id=utub_id, url_id=already_created_url.id, user_id=int(current_user.get_id()))
                url_id = already_created_url.id

            else:
                # Else create new URL and append to the UTUB
                new_url = URLS(url_string=validated_url, created_by=int(current_user.get_id()))
                db.session.add(new_url)
                db.session.commit()
                url_utub_user_add = Utub_Urls(utub_id=utub_id, url_id=new_url.id, user_id=int(current_user.get_id()))
                url_id = new_url.id
                
            db.session.add(url_utub_user_add)
            db.session.commit()

            # Successfully added URL to UTub
            return jsonify({
                "Status" : "Success",
                "Message" : "URL added to UTub",
                "URL" : {
                    "url_string": f"{validated_url}",
                    "url_ID" : f"{url_id}"
                },
                "UTub_ID" : f"{utub_id}",
                "UTub_name" : f"{utub.name}",
                "Added_by" : f"{current_user.get_id()}"
            }), 200
        
    return jsonify({
        "Status" : "Failure",
        "Message" : "Unable to add this URL",
        "Error_code": 4
    }), 404


@app.route('/utub/url/edit/<int:utub_id>/<int:url_id>', methods=["POST"])
@login_required
def edit_url(utub_id: int, url_id: int):
    """
    Edits the URL contained in the UTub.
    If user makes no edits or produces the same URL, then no edits occur.

    If the user provides a different URL, then remove the old URL from URL-UTUB association table, and 
    add in the new one. 
        If the new URL does not exist in the URLS table, first add it there.
    """
    print(request.data)
    return jsonify({"Status" : "Success"}), 200

"""#####################        END URL INVOLVED ROUTES        ###################"""

"""#####################        TAG INVOLVED ROUTES        ###################"""

@app.route('/utub/url/tag/add/<int:utub_id>/<int:url_id>', methods=["POST"])
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
        return jsonify({
            "Status" : "Failure",
            "Message" : "Unable to add tag to this URL",
            "Error_code" : 1
        }), 404
       
    url_tag_form = UTubNewUrlTagForm()

    if url_tag_form.validate_on_submit():

        tag_to_add = url_tag_form.tag_string.data

        # If too many tags, disallow adding tag
        tags_already_on_this_url = [tags for tags in utub.utub_url_tags if int(tags.url_id) == int(url_id)]

        if len(tags_already_on_this_url) > 4:
                # Cannot have more than 5 tags on a URL
                return jsonify({
                    "Status" : "Failure",
                    "Message" : "URLs can only have 5 tags max"
                }), 400

        # If not a tag already, create it
        tag_already_created = Tags.query.filter_by(tag_string=tag_to_add).first()

        if tag_already_created:
            # Check if tag already on url
            this_tag_is_already_on_this_url = [tags for tags in tags_already_on_this_url if int(tags.tag_id) == int(tag_already_created.id)]

            if this_tag_is_already_on_this_url:
                # Tag is already on this URL
                return jsonify({
                    "Status" : "Failure",
                    "Message" : "URL already has this tag"
                }), 400

            # Associate with the UTub and URL
            utub_url_tag = Url_Tags(utub_id=utub_id, url_id=url_id, tag_id=tag_already_created.id)
            tag_id = tag_already_created.id

        else:
            # Create tag, then associate with this UTub and URL
            new_tag = Tags(tag_string=tag_to_add, created_by=int(current_user.get_id()))
            db.session.add(new_tag)
            db.session.commit()
            utub_url_tag = Url_Tags(utub_id=utub_id, url_id=url_id, tag_id=new_tag.id)
            tag_id = new_tag.id

        db.session.add(utub_url_tag)
        db.session.commit()

        # Successfully added tag to URL on UTub

        return jsonify({
            "Status" : "Success",
            "Message" : "Tag added to this URL",
            "Tag" : {
                "tag_ID" : f"{tag_id}",
                "tag_string" : f"{tag_to_add}"
            },
            "URL_ID" : f"{url_id}",
            "UTub_ID" : f"{utub_id}"
        }), 200

    return jsonify({
        "Status" : "Failure",
        "Message" : "Unable to add tag to this URL",
        "Error_code" : 2
    }), 404

@app.route('/utub/url/tag/remove/<int:utub_id>/<int:url_id>/<int:tag_id>', methods=["POST"])
@login_required
def remove_tag(utub_id: int, url_id: int, tag_id: int):
    """
    User wants to delete a tag from a URL contained in a UTub. Only available to owner of that utub.

    TODO -> Owner + URL owner can remove tag?

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
        return jsonify({
            "Status" : "Success",
            "Message" : "Tag removed from URL",
            "tag_ID": f"{tag_id}",
            "URL_ID": f"{url_id}",
            "UTub_ID": f"{utub_id}" 
        }), 200

    return jsonify({
        "Status" : "Failure",
        "Message" : "Only UTub owners can remove tags"
    }), 403

"""#####################        END TAG INVOLVED ROUTES        ###################"""