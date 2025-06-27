"use strict";

// Dynamically generates the remove member icon when needed
function createMemberRemoveIcon() {
  const WIDTH_HEIGHT_PX = "24px";
  const SVG_NS = "http://www.w3.org/2000/svg";
  const removeMemberOuterIconSvg = $(document.createElementNS(SVG_NS, "svg"));
  const removeMemberInnerIconPath = $(document.createElementNS(SVG_NS, "path"));
  const path =
    "M1 14s-1 0-1-1 1-4 6-4 6 3 6 4-1 1-1 1zm5-6a3 3 0 1 0 0-6 3 3 0 0 0 0 6m6.146-2.854a.5.5 0 0 1 .708 0L14 6.293l1.146-1.147a.5.5 0 0 1 .708.708L14.707 7l1.147 1.146a.5.5 0 0 1-.708.708L14 7.707l-1.146 1.147a.5.5 0 0 1-.708-.708L13.293 7l-1.147-1.146a.5.5 0 0 1 0-.708";

  removeMemberInnerIconPath.attr({
    "fill-rule": "evenodd",
    d: path,
  });

  removeMemberOuterIconSvg
    .attr({
      xmlns: SVG_NS,
      width: WIDTH_HEIGHT_PX,
      height: WIDTH_HEIGHT_PX,
      fill: "currentColor",
      class: "bi bi-person-x-fill memberOtherBtnDelete pointerable",
      viewBox: "0 0 16 16",
      tabindex: "0",
    })
    .append(removeMemberInnerIconPath);

  return removeMemberOuterIconSvg;
}

function createLeaveUTubAsMemberIcon(isCurrentUserOwner, currentUserID) {
  $("#memberSelfBtnDelete")
    .offAndOn("click.removeMember", function (e) {
      e.stopPropagation();
      hideInputs();
      deselectAllURLs();
      removeMemberShowModal(currentUserID, isCurrentUserOwner);
    })
    .offAndOn("focus.removeSelf", function () {
      $(document).on("keyup.removeSelf", function (e) {
        if (e.which === 13) {
          hideInputs();
          deselectAllURLs();
          removeMemberShowModal(currentUserID, isCurrentUserOwner);
        }
      });
    })
    .offAndOn("blur.removeSelf", function () {
      $(document).off("keyup.removeSelf");
    });
}

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
    .offAndOn("click", function (e) {
      e.preventDefault();
      removeMemberHideModal();
    })
    .text(buttonTextDismiss);

  $("#modalSubmit")
    .removeClass()
    .addClass("btn btn-danger")
    .text(buttonTextSubmit)
    .offAndOn("click", function (e) {
      e.preventDefault();
      removeMember(memberID, isCreator);
    })
    .text(buttonTextSubmit);

  $("#confirmModal").modal("show");
  $("#modalRedirect").hide();
}

// This function will extract the current selection data needed for POST request (member ID)
function removeMemberSetup(memberID) {
  let postURL = routes.removeMember(getActiveUTubID(), memberID);

  return postURL;
}

// Handles post request and response for removing a member from current UTub, after confirmation
function removeMember(memberID, isCreator) {
  // Extract data to submit in POST request
  let postURL = removeMemberSetup(memberID);

  let request = ajaxCall("delete", postURL, []);

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

function removeMemberSuccess(memberID) {
  // Close modal
  $("#confirmModal").modal("hide");

  const memberListItem = $("span[memberid=" + memberID + "]");
  memberListItem.fadeOut("slow", function () {
    memberListItem.remove();
  });

  setMemberDeckForUTub(true);

  if (getNumOfUTubs() === 0) {
    resetUTubDeckIfNoUTubs();
  }
}

function leaveUTubSuccess() {
  // Close modal
  $("#confirmModal").modal("hide");

  // Members Deck display updates
  $("#memberSelfBtnDelete").hideClass();
  $("#confirmModal").modal("hide");
  setUIWhenNoUTubSelected();

  // UTub Deck display updates
  const utubSelector = $(".UTubSelector[utubid=" + getActiveUTubID() + "]");
  utubSelector.fadeOut("slow", function () {
    utubSelector.remove();
    hideInputsAndSetUTubDeckSubheader();
  });

  setTimeout(function () {
    window.history.pushState(null, null, "/home");
    window.history.replaceState(null, null, "/home");
  }, 0);
}

function removeMemberFail(xhr) {
  if (
    xhr.status === 403 &&
    xhr.getResponseHeader("Content-Type") === "text/html; charset=utf-8"
  ) {
    // Handle invalid CSRF token error response
    $("body").html(xhr.responseText);
    return;
  }

  switch (xhr.status) {
    case 400:
    case 403:
    case 404:
    default:
      window.location.assign(routes.errorPage);
  }
}
