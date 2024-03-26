/* Add UTub */

// Shows new UTub input fields
function addUTubShowInput() {
    showInput("createUTub");
    highlightInput($("#createUTub"));
  }
  
  // Hides new UTub input fields
  function addUTubHideInput() {
    hideInput("createUTub");
    unbindEnter(); // unbinding doesn't seem to work...
  }
  
  // Handles post request and response for adding a new UTub
  function addUTub() {
    // Extract data to submit in POST request
    [postURL, data] = addUTubSetup();
  
    console.log("About to make post AJAX call");
    console.log("About to make post AJAX call");
    let request = AJAXCall("post", postURL, data);
  
    // Handle response
    request.done(function (response, textStatus, xhr) {
      console.log("success");
  
      if (xhr.status == 200) {
        addUTubSuccess(response);
      }
    });
  
    request.fail(function (response, textStatus, xhr) {
      console.log("failed");
  
      addUTubFail(response, textStatus, xhr);
    });
  
    unbindEnter();
  }
  
  // Handles preparation for post request to create a new UTub
  function addUTubSetup() {
    let postURL = routes.addUTub;
    let newUTubName = $("#createUTub").val();
    data = { name: newUTubName };
  
    return [postURL, data];
  }
  
  // Handle creation of new UTub
  function addUTubSuccess(response) {
    // DP 12/28/23 One problem is that confirmed DB changes aren't yet reflected on the page. Ex. 1. User makes UTub name change UTub1 -> UTub2. 2. User attempts to create new UTub UTub1. 3. Warning modal is thrown because no AJAX call made to update the passed UTubs json.
    resetNewUTubForm();
  
    let UTubID = response.UTub_ID;
  
    $("#confirmModal").modal("hide");
  
    // Remove createDiv; Reattach after addition of new UTub
    $("#createUTub").closest(".createDiv").remove();
  
  
    // Create and append newly created UTub selector
    let index = Number($(".UTub").last().attr("position"));
    let nextIndex = index + 1;
    let listUTubs = $("#listUTubs");
    listUTubs.append(createUTubSelector(response.UTub_name, UTubID, nextIndex));
  
    // Create new createDiv after latest created UTub selector
    listUTubs.append(createNewUTubInputField());
  
    selectUTub(UTubID);
  }
  
  function addUTubFail(response, textStatus, xhr) {
    if (xhr.status == 409) {
      console.log(
        "Failure. Status code: " + xhr.status + ". Status: " + textStatus,
      );
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
      "Failure. Error code: " +
      response.error.Error_code +
      ". Status: " +
      response.error.Message,
    );
  }
  
  /* Edit UTub */
  
  // Shows input fields for editing an exiting UTub's name
  function editUTubNameShowInput() {
    // Show edit fields
    showInput("editUTubName");
  
    // Hide current name and edit button
    hideIfShown($("#URLDeckHeader"));
    hideIfShown($("#editUTubNameBtn"));
    hideIfShown($("#editUTubNameBtn"));
    hideIfShown($("#addURLBtn"));
  }
  
  // Hides input fields for editing an exiting UTub's name
  function editUTubNameHideInput() {
    // Hide edit fields
    hideInput("editUTubName");
  
    // Show values and edit button
    showIfHidden($("#URLDeckHeader"));
    showIfHidden($("#editUTubNameBtn"));
    showIfHidden($("#editUTubNameBtn"));
    showIfHidden($("#addURLBtn"));
  }
  
  // Shows input fields for editing an exiting UTub's description
  function editUTubDescriptionShowInput() {
    // Show edit fields
    showInput("editUTubDescription");
    showIfHidden($("#submitEditUTubDescriptionBtn"));
  
    // Hide current description and edit button
    hideIfShown($("#UTubDescription"));
    hideIfShown($("#editUTubDescriptionBtn"));
  }
  
  // Hides input fields for editing an exiting UTub's description
  function editUTubDescriptionHideInput() {
    // Hide edit fields
    hideInput("editUTubDescription");
    hideIfShown($("#submitEditUTubDescriptionBtn"));
    hideIfShown($("#submitEditUTubDescriptionBtn"));
  
    // Show values and edit button
    showIfHidden($("#UTubDescription"));
    showIfHidden($("#editUTubDescriptionBtn"));
    // Show values and edit button
    showIfHidden($("#UTubDescription"));
    showIfHidden($("#editUTubDescriptionBtn"));
  }
  
  // Handles post request and response for adding a new UTub
  function editUTubName() {
    // Extract data to submit in POST request
    [postURL, data] = editUTubNameSetup();
  
    let request = AJAXCall("post", postURL, data);
  
    // Handle response
    request.done(function (response, textStatus, xhr) {
      console.log("success");
  
      if (xhr.status == 200) {
        editUTubNameSuccess(response);
      }
    });
  
    request.fail(function (response, textStatus, xhr) {
      console.log("failed");
  
      editUTubFail(response, textStatus, xhr);
    });
  }
  
  //
  function editUTubDescription() {
    // Extract data to submit in POST request
    [postURL, data] = editUTubDescriptionSetup();
  
    let request = AJAXCall("post", postURL, data);
  
    // Handle response
    request.done(function (response, textStatus, xhr) {
      console.log("success");
  
      if (xhr.status == 200) {
        editUTubDescriptionSuccess(response);
      }
    });
  
    request.fail(function (response, textStatus, xhr) {
      console.log("failed");
  
      editUTubFail(response, textStatus, xhr);
    });
  }
  
  // Handles preparation for post request to edit an existing UTub
  function editUTubNameSetup() {
    let postURL = routes.editUTub(getActiveUTubID());
  
    let editedUTubName = $("#editUTubName").val();
    data = { name: editedUTubName };
  
    return [postURL, data];
  }
  
  // Handles preparation for post request to edit an existing UTub
  function editUTubDescriptionSetup() {
    let postURL = routes.editUTubDescription(getActiveUTubID());
  
    let editedUTubDescription = $("#editUTubDescription").val();
    data = { utub_description: editedUTubDescription };
  
    return [postURL, data];
  }
  
  //
  function editUTubNameSuccess(response) {
    let UTubName = response.UTub_name;
  
    if (!isHidden($("#confirmModal")[0])) $("#confirmModal").modal("hide");
  
    // UTubDeck display updates
    let editedUTubLabel = $("#listUTubs").find(".active");
    editedUTubLabel.find("b").text(UTubName);
  
    // Display updates
    displayState1UTubDeck(getActiveUTubID(), getCurrentUTubCreatorID());
    displayState1URLDeck();
    // Display updates
    displayState1UTubDeck(getActiveUTubID(), getCurrentUTubCreatorID());
    displayState1URLDeck();
  }
  
  //
  function editUTubDescriptionSuccess(response) {
    let UTubDescription = response.UTub_description;
  
    if (!isHidden($("#confirmModal")[0])) $("#confirmModal").modal("hide");
  
    displayState2UTubDescriptionDeck(UTubDescription);
    displayState2UTubDescriptionDeck(UTubDescription);
  }
  
  //
  function editUTubFail(response, textStatus, xhr) {
    console.log("Error: Could not create UTub");
    console.log(response);
  
    if (xhr.status == 409) {
      console.log(
        "Failure. Status code: " + xhr.status + ". Status: " + textStatus,
      );
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
      "Failure. Error code: " +
      response.responseJSON.Error_code +
      ". Status: " +
      response.responseJSON.Message,
    );
  }
  
  /* Delete UTub */
  
  // Hide confirmation modal for deletion of the current UTub
  function deleteUTubHideModal() {
    $("#confirmModal").modal("hide");
    unbindEnter();
  }
  
  // Show confirmation modal for deletion of the current UTub
  function deleteUTubShowModal() {
    let modalTitle = "Are you sure you want to delete this UTub?";
    let modalBody =
      "This action will remove all URLs in UTub and is irreverisible!";
    let buttonTextDismiss = "Nevermind...";
    let buttonTextSubmit = "Delete this sucka!";
  
    $("#confirmModalTitle").text(modalTitle);
  
    $("#confirmModalBody").text(modalBody);
  
    $("#modalDismiss")
      .addClass("btn btn-default")
      .off("click")
      .on("click", function (e) {
        e.preventDefault();
        deleteUTubHideModal();
      })
      .text(buttonTextDismiss);
    bindKeyToFunction(deleteUTubHideModal, 27);
  
    $("#modalSubmit")
      .removeClass()
      .addClass("btn btn-danger")
      .text(buttonTextSubmit)
      .off("click")
      .off("click")
      .on("click", function (e) {
        e.preventDefault();
        deleteUTub();
      });
    bindKeyToFunction(deleteUTub, 13);
  
    $("#confirmModal").modal("show");
  
    hideIfShown($("#modalRedirect"));
  }
  
  // Handles deletion of a current UTub
  function deleteUTub() {
    // Extract data to submit in POST request
    postURL = deleteUTubSetup();
  
    let request = AJAXCall("post", postURL, []);
  
    // Handle response
    request.done(function (response, textStatus, xhr) {
      console.log("success");
  
      if (xhr.status == 200) {
        deleteUTubSuccess();
      }
    });
  
    request.fail(function (response, textStatus, xhr) {
      console.log("failed");
  
      deleteUTubFailure(response, textStatus, xhr);
    });
  
    unbindEnter();
  }
  
  // Prepares post request inputs to delete the current UTub
  function deleteUTubSetup() {
  
    let postURL = routes.deleteUTub(getActiveUTubID());
  
    return postURL;
  }
  
  function deleteUTubSuccess() {
    hideInputs();
  
    // Close modal
    $("#confirmModal").modal("hide");
  
    // Update UTub Deck
    let currentUTubID = getActiveUTubID();
    let UTubSelector = $("div[utubid=" + currentUTubID + "]");
    UTubSelector.fadeOut();
    UTubSelector.remove();
  
    // Reset all panels
    displayState0();
  
    displayState1UTubDeck(null, null);
  
    if ($("#listUTubs").find("div.UTub").length == 0) displayState0UTubDeck();
  }
  
  function deleteUTubFailure(response, textStatus, xhr) {
    console.log("Error: Could not delete UTub");
  
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
      "Failure. Error code: " +
      response.error.Error_code +
      ". Status: " +
      response.error.Message,
    );
  }
  