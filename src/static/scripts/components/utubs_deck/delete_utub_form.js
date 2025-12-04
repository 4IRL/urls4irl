"use strict";

function setDeleteEventListeners(utubID) {
  const utubBtnDelete = $("#utubBtnDelete");

  // Delete UTub
  utubBtnDelete.offAndOn("click.deleteUTub", function () {
    deleteUTubShowModal(utubID);
  });

  // Allows user to press enter to bring up form while focusing on the delete UTub icon, esp after tabbing
  utubBtnDelete.offAndOn("focus.deleteUTub", function () {
    $(document).offAndOn("keyup.deleteUTub", function (e) {
      if (e.key === KEYS.ENTER) {
        e.stopPropagation();
        deleteUTubShowModal(utubID);
      }
    });
  });

  // Removes the keyup listener from the document once the button is blurred
  utubBtnDelete.offAndOn("blur.deleteUTub", function () {
    $(document).off("keyup.deleteUTub");
  });
}

// Hide confirmation modal for deletion of the current UTub
function deleteUTubHideModal() {
  $("#confirmModal").modal("hide");
}

// Show confirmation modal for deletion of the current UTub
function deleteUTubShowModal(utubID) {
  const modalTitle = "Are you sure you want to delete this UTub?";
  const modalBody = `${STRINGS.UTUB_DELETE_WARNING}`;
  const buttonTextDismiss = "Nevermind...";
  const buttonTextSubmit = "Delete this sucka!";

  $("#confirmModalTitle").text(modalTitle);

  $("#confirmModalBody").text(modalBody);

  $("#modalDismiss")
    .removeClass()
    .addClass("btn btn-secondary")
    .offAndOn("click", function (e) {
      e.preventDefault();
      deleteUTubHideModal();
    })
    .text(buttonTextDismiss);

  $("#modalSubmit")
    .removeClass()
    .addClass("btn btn-danger")
    .text(buttonTextSubmit)
    .offAndOn("click", function (e) {
      e.preventDefault();
      deleteUTub(utubID);
      closeUTubSearchAndEraseInput();
    });

  $("#confirmModal").modal("show");
  $("#modalRedirect").hide();
}

// Handles deletion of a current UTub
function deleteUTub(utubID) {
  // Extract data to submit in POST request
  let postURL = deleteUTubSetup(utubID);

  const request = ajaxCall("delete", postURL, []);

  // Handle response
  request.done(function (response, textStatus, xhr) {
    if (xhr.status === 200) {
      deleteUTubSuccess(utubID);
    }
  });

  request.fail(function (xhr, textStatus, errorThrown) {
    deleteUTubFail(xhr);
  });
}

// Prepares post request inputs to delete the current UTub
function deleteUTubSetup(utubID) {
  let postURL = routes.deleteUTub(utubID);

  return postURL;
}

function deleteUTubSuccess(utubID) {
  hideInputs();

  // Close modal
  $("#confirmModal").modal("hide");
  $("#utubBtnDelete").hide();

  // Update UTub Deck
  const utubSelector = $(".UTubSelector[utubid=" + utubID + "]");

  setTimeout(function () {
    window.history.pushState(null, null, "/home");
    window.history.replaceState(null, null, "/home");
  }, 0);

  utubSelector.fadeOut("slow", () => {
    utubSelector.remove();

    // Reset all panels
    setUIWhenNoUTubSelected();

    hideInputsAndSetUTubDeckSubheader();
    resetURLDeckOnDeleteUTub();

    if (getNumOfUTubs() === 0) {
      resetUTubDeckIfNoUTubs();
      $("#utubTagBtnCreate").hideClass();
    }

    isMobile() ? setMobileUIWhenUTubNotSelectedOrUTubDeleted() : null;
  });
}

function deleteUTubFail(xhr) {
  if (
    xhr.status === 403 &&
    xhr.getResponseHeader("Content-Type") === "text/html; charset=utf-8"
  ) {
    // Handle invalid CSRF token error response
    $("body").html(xhr.responseText);
    return;
  }
  window.location.assign(routes.errorPage);
  return;
}
