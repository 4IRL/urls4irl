/* Add Member */

// Shows new Member input fields
function createMemberShowInput() {
  showIfHidden($("#createMemberWrap").show());
  hideIfShown($("#displayMemberWrap"));
  hideIfShown($("#memberBtnCreate"));
  highlightInput($("#memberCreate"));
  setupCreateMemberEventListeners();
}

// Hides new Member input fields
function createMemberHideInput() {
  hideIfShown($("#createMemberWrap"));
  showIfHidden($("#displayMemberWrap"));
  showIfHidden($("#memberBtnCreate"));
  removeCreateMemberEventListeners();
  resetCreateMemberFailErrors();
  resetNewMemberForm();
}

function createMember() {
  // Extract data to submit in POST request
  [postURL, data] = createMemberSetup();

  AJAXCall("post", postURL, data);

  // Handle response
  request.done(function (response, textStatus, xhr) {
    if (xhr.status === 200) {
      createMemberSuccess(response);
    }
  });

  request.fail(function (xhr, _, textStatus) {
    createMemberFail(xhr);
  });
}

function setupCreateMemberEventListeners() {
  // Prevent clicking in input box from closing the form
  $("#memberCreate")
    .off("click.createMember")
    .on("click.createMember", function (e) {
      e.stopPropagation();
    });

  // Allow submission button to not close form in case of error
  $("#memberSubmitBtnCreate")
    .off("click.createMember")
    .on("click.createMember", function (e) {
      e.stopPropagation();
      createMember();
    });

  // Allow closing add member form by clicking anywhere else
  $(window)
    .off("click.createMember")
    .on("click.createMember", function (e) {
      const target = $(e.target);
      // Allow the cancel button to close the form
      if (
        target.parents("#memberCancelBtnCreate").length ||
        target.is("#memberCancelBtnCreate")
      ) {
        createMemberHideInput();
        return;
      }

      // Prevent initial opening form click or add member form area click from closing form
      const isInitialCreateMemberBtn =
        target.parents("#memberBtnCreate").length;
      const isInCreateMemberFormArea =
        target.parents("#createMemberWrap").length;
      if (isInitialCreateMemberBtn || isInCreateMemberFormArea) return;
      createMemberHideInput();
    });

  // Allow closing by pressing escape key
  $(document).bind("keyup.createMember", function (e) {
    switch (e.which) {
      case 13:
        // Handle enter key pressed
        createMember();
        break;
      case 27:
        // Handle escape  key pressed
        createMemberHideInput();
        break;
      default:
      /* no-op */
    }
  });
}

function removeCreateMemberEventListeners() {
  $(document).off(".createMember");
  $(window).off(".createMember");
}

// This function will extract the current selection data needed for POST request (member ID)
function createMemberSetup() {
  const postURL = routes.createMember(getActiveUTubID());

  const newMemberUsername = $("#memberCreate").val();
  data = {
    username: newMemberUsername,
  };

  return [postURL, data];
}

// Perhaps update a scrollable/searchable list of members?
function createMemberSuccess(response) {
  resetNewMemberForm();

  // Create and append newly created Member badge - only creators can add members
  $("#listMembers").append(
    createMemberBadge(response.member.id, response.member.username, true),
  );

  createMemberHideInput();
  displayState1MemberDeck(null, true);
}

function createMemberFail(xhr) {
  switch (xhr.status) {
    case 400:
      const responseJSON = xhr.responseJSON;
      const hasErrors = responseJSON.hasOwnProperty("errors");
      const hasMessage = responseJSON.hasOwnProperty("message");
      if (hasErrors) {
        // Show form errors
        createMemberFailErrors(responseJSON.errors);
        break;
      } else if (hasMessage) {
        // Show message
        displayCreateMemberFailErrors("username", responseJSON.message);
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

function createMemberFailErrors(errors) {
  for (let key in errors) {
    switch (key) {
      case "username":
        let errorMessage = errors[key][0];
        displayCreateMemberFailErrors(key, errorMessage);
        return;
    }
  }
}

function displayCreateMemberFailErrors(_, errorMessage) {
  $("#memberCreate-error").addClass("visible").text(errorMessage);
  $("#memberCreate").addClass("invalid-field");
}

function resetCreateMemberFailErrors() {
  const createMemberFields = ["member"];
  createMemberFields.forEach((fieldName) => {
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
      } else {
        leaveUTubSuccess();
      }
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

  displayState1MemberDeck(null, true);
}

function leaveUTubSuccess() {
  // Close modal
  $("#confirmModal").modal("hide");

  // Members Deck display updates
  $("#memberSelfBtnDelete").hide();
  $("#confirmModal").modal("hide");
  displayState0();

  // UTub Deck display updates
  const UTubSelector = $(".UTubSelector[utubid=" + getActiveUTubID() + "]");
  UTubSelector.fadeOut("slow", function () {
    UTubSelector.remove();
    displayState1UTubDeck(null, null);
  });
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
