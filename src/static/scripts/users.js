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
    addUser();
  });
  
  // Remove user from UTub
  $("#removeUserBtn").on("click", function (e) {
    // e.stopPropagation();
    // e.preventDefault();
    removeUserShowModal();
  });
  
});

/** User Utility Functions **/

// Simple function to streamline the jQuery selector extraction of selected user ID. And makes it easier in case the ID is encoded in a new location in the future
function selectedUserID() {}

// Clear user selection
function clearUserSelection() {
  $("#UTubUsernameInput").val("");
}

/* User Functions */

// Build center panel URL list for selectedUTub
function buildUserDeck(UTubUsers) {
  
  for(UTubUser in UTubUsers) {
    $("#UTubUsers").append(UTubUser.username);
  }
}

/** Post data handling **/

/* Add User */

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
  let postURL = ADD_USER_ROUTE + currentUTubID();

  let newUsername = $("#UTubUsernameInput").val();
  data = {
    username: newUsername
  };

  return [postURL, data];
}

// Perhaps update a scrollable/searchable list of users?
function addUserSuccess(response) {}

function addUserFail(response) {
  console.log("Basic implementation. Needs revision");
  console.log(response.responseJSON.Error_code);
  console.log(response.responseJSON.Message);
  // DP 09/17 could we maybe have a more descriptive reason for failure sent from backend to display to user?
  // Currently STD_JSON.MESSAGE: URL_FAILURE.UNABLE_TO_ADD_URL is too generic. the # * comments are ideal
}

/* Remove User */

// Show confirmation modal for removal of the selected user from current UTub
function removeUserShowModal() {
  let modalTitle = "Are you sure you want to remove this user from the UTub?";
  $(".modal-title").text(modalTitle);

  $("#modalDismiss").on("click", function (e) {
    e.preventDefault();
    $("#confirmModal").modal("hide");
  });

  $("#modalSubmit").on("click", function (e) {
    e.preventDefault();
    removeUser();
  });

  $("#confirmModal").modal("show");

  hideIfShown($("#modalRedirect"));
}

// Handles post request and response for removing a user from current UTub, after confirmation
function removeUser() {
  // Extract data to submit in POST request
  postURL = removeUserSetup();

  let request = AJAXCall("post", postURL, []);

  // Handle response
  request.done(function (response, textStatus, xhr) {
    console.log("success");

    if (xhr.status == 200) {
      removeUserSuccess();
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
function removeUserSetup() {
  let postURL = REMOVE_USER_ROUTE + currentUTubID();

  return postURL;
}

function removeUserSuccess() {
  // Close modal
  $("#confirmModal").modal("hide");

  let cardCol = $("div[urlid=" + selectedURLID() + "]").parent();
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
