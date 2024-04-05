/* Add User */

// Shows new User input fields
function addUserShowInput() {
    showInput("addUser");
    highlightInput($("#addUser"));
  }
  
  // Hides new User input fields
  function addUserHideInput() {
    hideInput("addUser");
  }
  
  function addUser() {
    // Extract data to submit in POST request
    [postURL, data] = addUserSetup();
  
    AJAXCall("post", postURL, data);
  
    // Handle response
    request.done(function (response, textStatus, xhr) {  
      if (xhr.status == 200) {
        addUserSuccess(response);
      }
    });
  
    request.fail(function (response, textStatus, xhr) {
      if (xhr.status == 404) {
        // Reroute to custom U4I 404 error page
      } else {
        addUserFail(response);
      }
    });
  }
  
  // This function will extract the current selection data needed for POST request (user ID)
  function addUserSetup() {
    let postURL = routes.addUser(getActiveUTubID());
  
    let newUsername = $("#addUser").val();
    data = {
      username: newUsername,
    };
  
    return [postURL, data];
  }
  
  // Perhaps update a scrollable/searchable list of users?
  function addUserSuccess(response) {
    resetNewUserForm();
  
    let UTubUsers = response.UTub_users;
    let newUser = UTubUsers[UTubUsers.length - 1];
  
    // Temporarily remove createDiv to reattach after addition of new User
    let createUser = $("#addUser").closest(".createDiv").detach();

    const parent = $("#listUsers");
  
    // Create and append newly created User badge
    parent.append(createUserBadge(response.User_ID_added, newUser));
    // Reorder createDiv after latest created UTub selector
    parent.append(createUser);
  
    displayState1UserDeck();
  }
  
  function addUserFail(response) {
    console.log("Basic implementation. Needs revision");
    console.log(response.responseJSON.Error_code);
    console.log(response.responseJSON.Message);
    // DP 09/17 could we maybe have a more descriptive reason for failure sent from backend to display to user?
    // Currently STD_JSON.MESSAGE: URL_FAILURE.UNABLE_TO_ADD_URL is too generic. the # * comments are ideal
  }
  
  /* Remove User */
  
  // Hide confirmation modal for removal of the selected user
  function removeUserHideModal() {
    $("#confirmModal").modal("hide");
    unbindEnter();
  }
  
  // Show confirmation modal for removal of the selected user from current UTub
  function removeUserShowModal(userID) {
    let modalTitle = "Are you sure you want to remove this user from the UTub?";
    let modalBody =
      "This user will no longer have access to the URLs in this UTub";
    let buttonTextDismiss = "Keep user";
    let buttonTextSubmit = "Remove user";
  
    $("#confirmModalTitle").text(modalTitle);
  
    $("#confirmModalBody").text(modalBody);
  
    $("#modalDismiss")
      .addClass("btn btn-default")
      .off("click")
      .on("click", function (e) {
        e.preventDefault();
        removeUserHideModal();
      })
      .text(buttonTextDismiss);
    bindKeyToFunction(removeUserHideModal, 27);
  
    $("#modalSubmit")
      .removeClass()
      .addClass("btn btn-danger")
      .text(buttonTextSubmit)
      .on("click", function (e) {
        e.preventDefault();
        removeUser(userID);
      })
      .text(buttonTextSubmit);
    bindKeyToFunction(removeUser, userID, 13);
  
    $("#confirmModal").modal("show");
  
    hideIfShown($("#modalRedirect"));
  }
  
  // Handles post request and response for removing a user from current UTub, after confirmation
  function removeUser(userID) {
    // Extract data to submit in POST request
    postURL = removeUserSetup(userID);
  
    let request = AJAXCall("post", postURL, []);
  
    // Handle response
    request.done(function (response, textStatus, xhr) {
      if (xhr.status == 200) {
        removeUserSuccess(userID);
      }
    });
  
    request.fail(function (response, textStatus, xhr) {  
      if (xhr.status == 404) {
        // Reroute to custom U4I 404 error page
      } else {
        removeUserFail(response);
      }
    });
  }
  
  // This function will extract the current selection data needed for POST request (user ID)
  function removeUserSetup(userID) {
    let postURL = routes.removeUser(getActiveUTubID(), userID);
  
    return postURL;
  }
  
  function removeUserSuccess(userID) {
    // Close modal
    $("#confirmModal").modal("hide");
  
    let userListItem = $("span[userid=" + userID + "]").parent();
    userListItem.fadeOut();
    userListItem.remove();
  
    displayState1UserDeck();
  }
  
  function removeUserFail(xhr, textStatus, error) {
    console.log("Error: Could not remove User");
  
    if (xhr.status == 409) {
      console.log(
        "Failure. Status code: " + xhr.status + ". Status: " + textStatus,
      );
      // const flashMessage = xhr.responseJSON.error;
      // const flashCategory = xhr.responseJSON.category;
  
      // let flashElem = flashMessageBanner(flashMessage, flashCategory);
      // flashElem.insertBefore('#modal-body').show();
    } else if (xhr.status == 404) {
      $(".invalid-feedback").remove();
      $(".alert").remove();
      $(".form-control").removeClass("is-invalid");
      const error = JSON.parse(xhr.responseJSON);
      for (var key in error) {
        $('<div class="invalid-feedback"><span>' + error[key] + "</span></div>")
          .insertAfter("#" + key)
          .show();
        $("#" + key).addClass("is-invalid");
      }
    }
    console.log(
      "Failure. Status code: " + xhr.status + ". Status: " + textStatus,
    );
    console.log("Error: " + error.Error_code);
  }
  