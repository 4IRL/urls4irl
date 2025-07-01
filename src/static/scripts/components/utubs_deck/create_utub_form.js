"use strict";

function setCreateUTubEventListeners() {
  // Create new UTub
  const utubBtnCreate = $("#utubBtnCreate");
  utubBtnCreate.offAndOn("click.createDeleteUTub", function () {
    createUTubShowInput();
    closeUTubSearchAndEraseInput();
  });

  // Allows user to press enter to bring up form while focusing on the add UTub icon, esp after tabbing
  utubBtnCreate.offAndOn("focus.createDeleteUTub", function () {
    $(document).offAndOn("keyup.createDeleteUTub", function (e) {
      if (e.which === 13) {
        e.stopPropagation();
        createUTubShowInput();
      }
    });
  });

  // Removes the keyup listener from the document once the button is blurred
  utubBtnCreate.offAndOn("blur.createDeleteUTub", function () {
    $(document).off("keyup.createDeleteUTub");
  });
}

// Attaches appropriate event listeners to the add UTub and cancel add UTub buttons
function createNewUTubEventListeners() {
  const utubSubmitBtnCreate = $("#utubSubmitBtnCreate");
  const utubCancelBtnCreate = $("#utubCancelBtnCreate");
  utubSubmitBtnCreate.offAndOn("click.createUTub", function (e) {
    if ($(e.target).closest("#utubSubmitBtnCreate").length > 0)
      checkSameNameUTub(true, $("#utubNameCreate").val());
  });

  utubCancelBtnCreate.offAndOn("click.createUTub", function (e) {
    if ($(e.target).closest("#utubCancelBtnCreate").length > 0)
      createUTubHideInput();
  });

  utubSubmitBtnCreate.offAndOn("focus.createUTub", function () {
    $(document).offAndOn("keyup.createUTubSubmit", function (e) {
      if (e.which === 13) checkSameNameUTub(true, $("#utubNameCreate").val());
    });
  });

  utubSubmitBtnCreate.offAndOn("blur.createUTub", function () {
    $(document).off("keyup.createUTubSubmit");
  });

  utubCancelBtnCreate.offAndOn("focus.createUTub", function () {
    $(document).offAndOn("keyup.createUTubCancel", function (e) {
      if (e.which === 13) createUTubHideInput();
    });
  });

  utubCancelBtnCreate.on("blur.createUTub", function () {
    $(document).off("keyup.createUTubCancel");
  });

  const utubNameInput = $("#utubNameCreate");
  const utubDescriptionInput = $("#utubDescriptionCreate");

  utubNameInput.on("focus.createUTub", function () {
    $(document).on("keyup.createUTubName", function (e) {
      handleOnFocusEventListenersForCreateUTub(e);
    });
  });

  utubNameInput.on("blur.createUTub", function () {
    $(document).off(".createUTubName");
  });

  utubDescriptionInput.on("focus.createUTub", function () {
    $(document).on("keyup.createUTubDescription", function (e) {
      handleOnFocusEventListenersForCreateUTub(e);
    });
  });

  utubDescriptionInput.on("blur.createUTub", function () {
    $(document).off(".createUTubDescription");
  });
}

function removeNewUTubEventListeners() {
  $(document).off("keyup.createUTubName");
  $(document).off("keyup.createUTubDescription");
  $(document).off("keyup.createUTubCancel");
  $(document).off("keyup.createUTubSubmit");
  $("#utubNameCreate").off(".createUTub");
  $("#utubDescriptionCreate").off(".createUTub");
  $("#utubSubmitBtnCreate").off(".createUTub");
  $("#utubCancelBtnCreate").off(".createUTub");
}

function handleOnFocusEventListenersForCreateUTub(e) {
  switch (e.which) {
    case 13:
      // Handle enter key pressed
      checkSameNameUTub(true, $("#utubNameCreate").val());
      break;
    case 27:
      // Handle escape key pressed
      $("#utubNameCreate").trigger("blur");
      $("#utubDescriptionCreate").trigger("blur");
      createUTubHideInput();
      break;
    default:
    /* no-op */
  }
}

function sameUTubNameOnNewUTubWarningShowModal() {
  const modalTitle = "Create a new UTub with this name?";
  const modalBody = `${STRINGS.UTUB_CREATE_SAME_NAME}`;
  const buttonTextDismiss = "Go Back to Editing";
  const buttonTextSubmit = "Create";

  $("#confirmModalTitle").text(modalTitle);

  $("#confirmModalBody").text(modalBody);

  $("#modalDismiss")
    .addClass("btn btn-secondary")
    .text(buttonTextDismiss)
    .offAndOn("click", function (e) {
      e.preventDefault();
      e.stopPropagation();
      sameNameWarningHideModal();
      highlightInput($("#utubNameCreate"));
    });

  $("#modalRedirect").hideClass();
  $("#modalRedirect").hide();

  $("#modalSubmit")
    .removeClass()
    .addClass("btn btn-success")
    .text(buttonTextSubmit)
    .offAndOn("click", function (e) {
      e.preventDefault();
      createUTub();
      $("#utubNameCreate").val(null);
      $("#utubDescriptionCreate").val(null);
    });

  $("#confirmModal").modal("show");
  $("#confirmModal").on("hidden.bs.modal", function (e) {
    // Refocus on the name's input box
    highlightInput($("#utubNameCreate"));
  });
}

// Shows new UTub input fields
function createUTubShowInput() {
  $("#createUTubWrap").showClassFlex();
  createNewUTubEventListeners();
  $("#utubNameCreate").trigger("focus");
  $("#listUTubs").hideClass();
  $("#UTubDeck").find(".button-container").hideClass();
  removeCreateDeleteUTubEventListeners();
}

// Hides new UTub input fields
function createUTubHideInput() {
  $("#createUTubWrap").hideClass();
  $("#listUTubs").showClassNormal();
  $("#utubNameCreate").val(null);
  $("#utubDescriptionCreate").val(null);
  removeNewUTubEventListeners();
  resetUTubFailErrors();
  $("#UTubDeck").find(".button-container").showClassNormal();
  setCreateDeleteUTubEventListeners();
}

// Handles preparation for post request to create a new UTub
function createUTubSetup() {
  const postURL = routes.createUTub;
  const newUTubName = $("#utubNameCreate").val();
  const newUTubDescription = $("#utubDescriptionCreate").val();
  let data = { utubName: newUTubName, utubDescription: newUTubDescription };

  return [postURL, data];
}

// Handles post request and response for adding a new UTub
function createUTub() {
  // Extract data to submit in POST request
  let postURL, data;
  [postURL, data] = createUTubSetup();
  resetUTubFailErrors();

  let request = ajaxCall("post", postURL, data);

  // Handle response
  request.done(function (response, textStatus, xhr) {
    if (xhr.status === 200) {
      createUTubSuccess(response);
      $("#listUTubs").showClassNormal();
    }
  });

  request.fail(function (xhr, _, textStatus) {
    createUTubFail(xhr);
  });
}

// Handle creation of new UTub
function createUTubSuccess(response) {
  // DP 12/28/23 One problem is that confirmed DB changes aren't yet reflected on the page. Ex. 1. User makes UTub name change UTub1 -> UTub2. 2. User attempts to create new UTub UTub1. 3. Warning modal is thrown because no AJAX call made to update the passed UTubs json.
  const UTubID = response.utubID;

  $("#confirmModal").modal("hide");

  // Remove createDiv; Reattach after addition of new UTub
  createUTubHideInput();

  // Create and append newly created UTub selector
  const index = parseInt($(".UTubSelector").first().attr("position"));
  const newUTubSelector = createUTubSelector(
    response.utubName,
    UTubID,
    CONSTANTS.MEMBER_ROLES.CREATOR,
    index - 1,
  );
  $("#listUTubs").prepend(newUTubSelector);

  selectUTub(UTubID, newUTubSelector);
}

// Handle error response display to user
function createUTubFail(xhr) {
  if (!xhr.hasOwnProperty("responseJSON")) {
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
  switch (xhr.status) {
    case 400:
      const responseJSON = xhr.responseJSON;
      if (responseJSON.hasOwnProperty("message")) {
        if (responseJSON.hasOwnProperty("errors"))
          createUTubFailErrors(responseJSON.errors);
        break;
      }
    case 404:
    default:
      window.location.assign(routes.errorPage);
  }
}

// Cycle through the valid errors for adding a UTub
function createUTubFailErrors(errors) {
  for (let key in errors) {
    switch (key) {
      case "utubName":
      case "utubDescription":
        let errorMessage = errors[key][0];
        displayUTubFailErrors(key, errorMessage);
    }
  }
}

// Show the error message and highlight the input box border red on error of field
function displayUTubFailErrors(key, errorMessage) {
  $("#" + key + "Create-error")
    .addClass("visible")
    .text(errorMessage);
  $("#" + key + "Create").addClass("invalid-field");
}

function resetUTubFailErrors() {
  const newUTubFields = ["utubName", "utubDescription"];
  newUTubFields.forEach((fieldName) => {
    $("#" + fieldName + "Create").removeClass("invalid-field");
    $("#" + fieldName + "Create-error").removeClass("visible");
  });
}
