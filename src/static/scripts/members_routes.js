/* Add Member */

// Shows new Member input fields
function addMemberShowInput() {
  showIfHidden($("#addMemberWrap").show());
  hideIfShown($("#displayMemberWrap"));
  hideIfShown($("#addMemberBtn"));
  highlightInput($("#usernameCreate"));
  setupAddMemberEventListeners();
}

// Hides new Member input fields
function addMemberHideInput() {
  hideIfShown($("#addMemberWrap"));
  showIfHidden($("#displayMemberWrap"));
  showIfHidden($("#addMemberBtn"));
  removeAddMemberEventListeners();
  resetAddMemberFailErrors();
  resetNewMemberForm();
}

function addMember() {
  // Extract data to submit in POST request
  [postURL, data] = addMemberSetup();

  AJAXCall("post", postURL, data);

  // Handle response
  request.done(function (response, textStatus, xhr) {
    if (xhr.status === 200) {
      addMemberSuccess(response);
    }
  });

  request.fail(function (xhr, _, textStatus) {
    addMemberFail(xhr);
  });
}

function setupAddMemberEventListeners() {
  // Prevent clicking in input box from closing the form
  $("#usernameCreate")
    .off("click.addMember")
    .on("click.addMember", function (e) {
      e.stopPropagation();
    });

  // Allow submission button to not close form in case of error
  $("#submitAddMember")
    .off("click.addMember")
    .on("click.addMember", function (e) {
      e.stopPropagation();
      addMember();
    });

  // Allow closing add member form by clicking anywhere else
  $(window)
    .off("click.addMember")
    .on("click.addMember", function (e) {
      const target = $(e.target);
      // Allow the cancel button to close the form
      if (
        target.parents("#cancelAddMember").length ||
        target.is("#cancelAddMember")
      ) {
        addMemberHideInput();
        return;
      }

      // Prevent initial opening form click or add member form area click from closing form
      const isInitialAddMemberBtn = target.parents("#addMemberBtn").length;
      const isInAddMemberFormArea = target.parents("#addMemberWrap").length;
      if (isInitialAddMemberBtn || isInAddMemberFormArea) return;
      addMemberHideInput();
    });

  // Allow closing by pressing escape key
  $(document).bind("keyup.addMember", function (e) {
    switch (e.which) {
      case 13:
        // Handle enter key pressed
        addMember();
        break;
      case 27:
        // Handle escape  key pressed
        addMemberHideInput();
        break;
      default:
      /* no-op */
    }
  });
}

function removeAddMemberEventListeners() {
  $(document).off(".addMember");
  $(window).off(".addMember");
}

// This function will extract the current selection data needed for POST request (member ID)
function addMemberSetup() {
  const postURL = routes.createMember(getActiveUTubID());

  const newMemberUsername = $("#usernameCreate").val();
  data = {
    username: newMemberUsername,
  };

  return [postURL, data];
}

// Perhaps update a scrollable/searchable list of members?
function addMemberSuccess(response) {
  resetNewMemberForm();

  // Create and append newly created Member badge - only creators can add members
  $("#listMembers").append(
    createMemberBadge(response.member.id, response.member.username, true),
  );

  addMemberHideInput();
  displayState1MemberDeck();
}

function addMemberFail(xhr) {
  switch (xhr.status) {
    case 400:
      const responseJSON = xhr.responseJSON;
      const hasErrors = responseJSON.hasOwnProperty("errors");
      const hasMessage = responseJSON.hasOwnProperty("message");
      if (hasErrors) {
        // Show form errors
        addMemberFailShowErrors(responseJSON.errors);
        break;
      } else if (hasMessage) {
        // Show message
        displayAddMemberFailErrors("username", responseJSON.message);
        break;
      }
    case 403:
    case 404:
    default:
      window.location.assign(routes.errorPage);
  }
  // DP 09/17 could we maybe have a more descriptive reason for failure sent from backend to display to member?
  // Currently STD_JSON.MESSAGE: URL_FAILURE.UNABLE_TO_ADD_URL is too generic. the # * comments are ideal
}

function addMemberFailShowErrors(errors) {
  for (let key in errors) {
    switch (key) {
      case "username":
        let errorMessage = errors[key][0];
        displayAddMemberFailErrors(key, errorMessage);
        return;
    }
  }
}

function displayAddMemberFailErrors(key, errorMessage) {
  $("#" + key + "Create-error")
    .addClass("visible")
    .text(errorMessage);
  $("#" + key + "Create").addClass("invalid-field");
}

function resetAddMemberFailErrors() {
  const addMemberFields = ["username"];
  addMemberFields.forEach((fieldName) => {
    $("#" + fieldName + "Create-error").removeClass("visible");
    $("#" + fieldName + "Create").removeClass("invalid-field");
  });
}

/* Remove Member */

// Hide confirmation modal for removal of the selected member
function removeMemberHideModal() {
  $("#confirmModal").modal("hide");
}

// Show confirmation modal for removal of the selected member from current UTub
function removeMemberShowModal(memberID, isCreator) {
  const modalTitle = isCreator
    ? "Are you sure you want to remove this member from the UTub?"
    : "Are you sure you want to leave this UTub?";
  const modalBody = isCreator
    ? "This member will no longer have access to the URLs in this UTub."
    : "You will no longer have access to the URLs in this UTub.";
  const buttonTextDismiss = isCreator ? "Keep member" : "Stay in UTub";
  const buttonTextSubmit = isCreator ? "Remove member" : "Leave UTub";

  $("#confirmModalTitle").text(modalTitle);

  $("#confirmModalBody").text(modalBody);

  $("#modalDismiss")
    .addClass("btn btn-secondary")
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
    .off("click")
    .on("click", function (e) {
      e.preventDefault();
      removeMember(memberID, isCreator);
    })
    .text(buttonTextSubmit);

  $("#confirmModal").modal("show");
  $("#modalRedirect").hide();
}

// Handles post request and response for removing a member from current UTub, after confirmation
function removeMember(memberID, isCreator) {
  // Extract data to submit in POST request
  postURL = removeMemberSetup(memberID);

  let request = AJAXCall("delete", postURL, []);

  // Handle response
  request.done(function (_, textStatus, xhr) {
    if (xhr.status === 200) {
      if (isCreator) {
        removeMemberSuccess(memberID);
        return;
      }
      $("#leaveUTubBtn").hide();
      $("#confirmModal").modal("hide");
      displayState0();
      displayState1UTubDeck(null, null);

      if ($("#listUTubs").find(".UTubSelector").length === 0)
        displayState0UTubDeck();
    }
  });

  request.fail(function (xhr, _, textStatus) {
    removeMemberFail(xhr);
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

  const memberListItem = $("span[memberid=" + memberID + "]");
  memberListItem.fadeOut("slow", function () {
    memberListItem.remove();
  });

  displayState1MemberDeck();
}

function removeMemberFail(xhr) {
  switch (xhr.status) {
    case 400:
    case 403:
    case 404:
    default:
      window.location.assign(routes.errorPage);
  }
}
