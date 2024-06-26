/* Add Member */

// Shows new Member input fields
function addMemberShowInput() {
  showInput("addMember");
  highlightInput($("#addMember"));
}

// Hides new Member input fields
function addMemberHideInput() {
  hideInput("addMember");
}

function addMember() {
  // Extract data to submit in POST request
  [postURL, data] = addMemberSetup();

  AJAXCall("post", postURL, data);

  // Handle response
  request.done(function (response, textStatus, xhr) {
    if (xhr.status == 200) {
      addMemberSuccess(response, data.memberUsername);
    }
  });

  request.fail(function (response, textStatus, xhr) {
    if (xhr.status == 404) {
      // Reroute to custom U4I 404 error page
    } else {
      addMemberFail(response);
    }
  });
}

// This function will extract the current selection data needed for POST request (member ID)
function addMemberSetup() {
  let postURL = routes.addMember(getActiveUTubID());

  let newMemberUsername = $("#addMember").val();
  data = {
    username: newMemberUsername,
  };

  return [postURL, data];
}

// Perhaps update a scrollable/searchable list of members?
function addMemberSuccess(response, memberUsername) {
  resetNewMemberForm();

  // Remove createDiv. Create and append a new instance after addition of new Member
  $("#addMember").closest(".createDiv").detach();

  const parent = $("#listMembers");

  // Create and append newly created Member badge
  parent.append(
    createMemberBadge(response.member.id, response.member.username),
  );
  // Create and append new member input field
  parent.append(createNewMemberInputField());

  displayState1MemberDeck();
}

function addMemberFail(response) {
  console.log("Basic implementation. Needs revision");
  console.log(response.responseJSON.errorCode);
  console.log(response.responseJSON.message);
  // DP 09/17 could we maybe have a more descriptive reason for failure sent from backend to display to member?
  // Currently STD_JSON.MESSAGE: URL_FAILURE.UNABLE_TO_ADD_URL is too generic. the # * comments are ideal
}

/* Remove Member */

// Hide confirmation modal for removal of the selected member
function removeMemberHideModal() {
  $("#confirmModal").modal("hide");
  unbindEnter();
}

// Show confirmation modal for removal of the selected member from current UTub
function removeMemberShowModal(memberID) {
  let modalTitle = "Are you sure you want to remove this member from the UTub?";
  let modalBody =
    "This member will no longer have access to the URLs in this UTub";
  let buttonTextDismiss = "Keep member";
  let buttonTextSubmit = "Remove member";

  $("#confirmModalTitle").text(modalTitle);

  $("#confirmModalBody").text(modalBody);

  $("#modalDismiss")
    .addClass("btn btn-default")
    .off("click")
    .on("click", function (e) {
      e.preventDefault();
      removeMemberHideModal();
    })
    .text(buttonTextDismiss);

  $("#modalSubmit")
    .removeClass()
    .addClass("btn btn-danger")
    .text(buttonTextSubmit)
    .on("click", function (e) {
      e.preventDefault();
      removeMember(memberID);
    })
    .text(buttonTextSubmit);

  $("#confirmModal").modal("show");

  hideIfShown($("#modalRedirect"));
}

// Handles post request and response for removing a member from current UTub, after confirmation
function removeMember(memberID) {
  // Extract data to submit in POST request
  postURL = removeMemberSetup(memberID);

  let request = AJAXCall("delete", postURL, []);

  // Handle response
  request.done(function (response, textStatus, xhr) {
    if (xhr.status == 200) {
      removeMemberSuccess(memberID);
    }
  });

  request.fail(function (response, textStatus, xhr) {
    if (xhr.status == 404) {
      // Reroute to custom U4I 404 error page
    } else {
      removeMemberFail(response);
    }
  });
}

// This function will extract the current selection data needed for POST request (member ID)
function removeMemberSetup(memberID) {
  let postURL = routes.removeMember(getActiveUTubID(), memberID);

  return postURL;
}

function removeMemberSuccess(memberID) {
  // Close modal
  $("#confirmModal").modal("hide");

  let memberListItem = $("span[memberid=" + memberID + "]");
  memberListItem.fadeOut();
  memberListItem.remove();

  displayState1MemberDeck();
}

function removeMemberFail(xhr, textStatus, error) {
  console.log("Error: Could not remove Member");

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
