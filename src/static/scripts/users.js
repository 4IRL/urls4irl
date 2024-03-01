/** User-related constants **/

// Routes
const ADD_USER_ROUTE = "/user/add/"; // +<int:utub_id>
const REMOVE_USER_ROUTE = "/user/remove/"; // +<int:utub_id>/<int:user_id>

/** User UI Interactions **/

$(document).ready(function () {
  /* Bind click functions */

  // Add user to UTub
  $("#addUserBtn").on("click", function (e) {
    // e.stopPropagation();
    // e.preventDefault();
    hideInputs();
    deselectAllURLs();
    addUserShowInput();
    // Bind enter key (keycode 13) to submit user input
    // DP 12/29 It'd be nice to have a single utils.js function with inputs of function and keyTarget (see semi-successful attempt under bindKeyToFunction() in utils.js)
    unbindEnter();
    $(document).bind("keypress", function (e) {
      if (e.which == 13) {
        addUser();
      }
    });
  });
});

/** User Utility Functions **/

// Simple function to streamline the jQuery selector extraction of selected user ID. And makes it easier in case the ID is encoded in a new location in the future
function getCurrentUserID() {
  return $("li.nav-item.user").attr("id");
}

// Clear user selection
function resetNewUserForm() {
  $("#UTubUsernameInput").val("");
}

// Clear the User Deck
function resetUserDeck() {
  $("#UTubOwner").empty();
  $("#listUsers").empty();
}

/** User Functions **/

// Build center panel URL list for selectedUTub
function buildUserDeck(dictUsers, UTubOwnerID) {
  resetUserDeck();
  const parent = $("#listUsers");
  let numOfUsers = dictUsers.length ? dictUsers.length : 0;
  let ownerBool = getCurrentUserID() == UTubOwnerID;

  // Instantiate deck with list of users with access to current UTub
  for (let i = 0; i < numOfUsers; i++) {
    let UTubUser = dictUsers[i];

    if (UTubUser.id !== UTubOwnerID) {
      parent.append(createUserSelector(UTubUser));
    } else {
      $("#UTubOwner").append(createOwnerBadge(UTubUser));
    }
  }

  // Subheader prompt
  let UserDeckSubheader = $("#UserDeckSubheader");
  if (numOfUsers === 1) UserDeckSubheader.text("Add a user");
  else UserDeckSubheader.text(numOfUsers + " active users");

  // Ability to add users is restricted to UTub owner
  if (ownerBool) {
    showIfHidden($("#addUserBtn"));
    parent.append(createNewUserInputField());
  } else hideIfShown($("#addUserBtn"));

}

// Creates user list item
function createOwnerBadge(UTubUser) {
  let userSpan = document.createElement("span");

  $(userSpan)
    .attr({ userid: UTubUser.id })
    .addClass("user")
    .html("<b>" + UTubUser.username + "</b>");

  return userSpan;
}

// Creates user list item
function createUserSelector(UTubUser) {
  let userListItem = document.createElement("li");
  let userSpan = document.createElement("span");
  let removeButton = document.createElement("a");

  let userID = UTubUser.id;

  $(userSpan)
    .attr({ userid: userID })
    .addClass("user")
    .html("<b>" + UTubUser.username + "</b>");

  $(removeButton)
    .attr({ class: "btn btn-sm btn-outline-link border-0 user-remove" })
    .on("click", function (e) {
      e.stopPropagation();
      e.preventDefault();
      removeUserShowModal(userID);
    });
  removeButton.innerHTML = "&times;";

  $(userSpan).append(removeButton);
  $(userListItem).append(userSpan);

  return userListItem;
}

// Creates a typically hidden input text field. When creation of a new UTub is requested, it is shown to the user. Input field recreated here to ensure at the end of list after creation of new UTubs
function createNewUserInputField() {
  const wrapper = $(document.createElement("div"));
  const wrapperInput = $(document.createElement("fieldset")); // This element wraps the new user input
  const wrapperBtns = $(document.createElement("div"));

  const label = document.createElement("label"); // This element labels the new user field
  const input = $(document.createElement("input"));
  const submit = $(document.createElement("i"));
  const cancel = $(document.createElement("i"));

  $(wrapper)
    .attr({
      style: "display: none",
    })
    .addClass("createDiv row");

  $(wrapperInput).addClass("col-9 col-lg-9 mb-md-0");

  $(label)
    .attr({
      for: "UTubUsernameInput",
      style: "display:block",
    })
    .html("<b> Username </b>");

  $(input)
    .attr({
      id: "UTubUsernameInput",
      type: "text",
      placeholder: "Username",
    })
    .addClass("User userInput");

  wrapperInput.append(label).append(input);

  $(wrapperBtns).addClass("col-3 mb-md-0 py-4 d-flex flex-row");

  // Submit addUser checkbox
  let htmlString =
    '<svg xmlns="http://www.w3.org/2000/svg" fill="currentColor" class="b=i bi-check-square-fill" viewBox="0 0 16 16" width="' +
    ICON_WIDTH +
    '" height="' +
    ICON_HEIGHT +
    '">' +
    '<path d="M2 0a2 2 0 0 0-2 2v12a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V2a2 2 0 0 0-2-2zm10.03 4.97a.75.75 0 0 1 .011 1.05l-3.992 4.99a.75.75 0 0 1-1.08.02L4.324 8.384a.75.75 0 1 1 1.06-1.06l2.094 2.093 3.473-4.425a.75.75 0 0 1 1.08-.022z"/></svg>';

  $(submit)
    .addClass("mx-1 green-clickable")
    .on("click", function (e) {
      e.stopPropagation();
      e.preventDefault();
      addUser();
    })
    .html(htmlString);

  wrapperBtns.append(submit);

  // Cancel add User x-box
  htmlString =
    '<svg xmlns="http://www.w3.org/2000/svg" fill="currentColor" class="bi bi-x-square-fill text-danger" viewBox="0 0 16 16" width="' +
    ICON_WIDTH +
    '" height="' +
    ICON_HEIGHT +
    '">' +
    '<path d="M2 0a2 2 0 0 0-2 2v12a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V2a2 2 0 0 0-2-2zm3.354 4.646L8 7.293l2.646-2.647a.5.5 0 0 1 .708.708L8.707 8l2.647 2.646a.5.5 0 0 1-.708.708L8 8.707l-2.646 2.647a.5.5 0 0 1-.708-.708L7.293 8 4.646 5.354a.5.5 0 1 1 .708-.708"/></svg>';

  $(cancel)
    .addClass("mx-1")
    .on("click", function (e) {
      e.stopPropagation();
      e.preventDefault();
      hideIfShown(wrapper);
    })
    .html(htmlString);

  wrapperBtns.append(cancel);

  wrapper.append(wrapperInput);
  wrapper.append(wrapperBtns);

  return wrapper;
}

/** Post data handling **/

/* Add User */

// Shows new User input fields
function addUserShowInput() {
  showInput("UTubUsernameInput");
  highlightInput($("#UTubUsernameInput"));
}

// Hides new User input fields
function addUserHideInput() {
  hideInput("UTubUsernameInput");
}

function addUser() {
  // Extract data to submit in POST request
  [postURL, data] = addUserSetup();

  AJAXCall("post", postURL, data);

  // Handle response
  request.done(function (response, textStatus, xhr) {
    console.log("success");

    if (xhr.status == 200) {
      addUserSuccess(response);
    }
  });

  request.fail(function (response, textStatus, xhr) {
    console.log("failed");

    if (xhr.status == 404) {
      // Reroute to custom U4I 404 error page
    } else {
      addUserFail(response);
    }
  });
}

// This function will extract the current selection data needed for POST request (user ID)
function addUserSetup() {
  let postURL = ADD_USER_ROUTE + getActiveUTubID();

  let newUsername = $("#UTubUsernameInput").val();
  data = {
    username: newUsername,
  };

  return [postURL, data];
}

// Perhaps update a scrollable/searchable list of users?
function addUserSuccess(response) {
  console.log(response)
  let UTubUsers = response.UTub_users;
  console.log(UTubUsers[UTubUsers.length-1])
  $("#listUsers").append(createUserSelector(UTubUsers[UTubUsers.length-1]));
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
    console.log("success");

    if (xhr.status == 200) {
      removeUserSuccess(userID);
    }
  });

  request.fail(function (response, textStatus, xhr) {
    console.log("failed");

    if (xhr.status == 404) {
      // Reroute to custom U4I 404 error page
    } else {
      removeUserFail(response);
    }
  });
}

// This function will extract the current selection data needed for POST request (user ID)
function removeUserSetup(userID) {
  let postURL = REMOVE_USER_ROUTE + getActiveUTubID() + "/" + userID;

  return postURL;
}

function removeUserSuccess(userID) {
  // Close modal
  $("#confirmModal").modal("hide");

  let userListItem = $("span[userid=" + userID + "]").parent();
  userListItem.fadeOut();
  userListItem.remove();
}

function removeUserFail(xhr, textStatus, error) {
  console.log("Error: Could not delete URL");

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
