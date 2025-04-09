"use strict";

// Hide confirmation modal for removal of the selected URL
function deleteURLHideModal() {
  $("#confirmModal").modal("hide").removeClass("deleteUrlModal");
}

// Show confirmation modal for removal of the selected existing URL from current UTub
function deleteURLShowModal(utubUrlID, urlCard) {
  let modalTitle = "Are you sure you want to delete this URL from the UTub?";
  let modalText = "You can always add it back again!";
  let buttonTextDismiss = "Just kidding";
  let buttonTextSubmit = "Delete URL";

  $("#confirmModalTitle").text(modalTitle);
  $("#confirmModalBody").text(modalText);

  $("#modalDismiss")
    .offAndOn("click", function (e) {
      e.preventDefault();
      deleteURLHideModal();
    })
    .text(buttonTextDismiss);

  $("#modalSubmit")
    .offAndOn("click", function (e) {
      e.preventDefault();
      deleteURL(utubUrlID, urlCard);
    })
    .text(buttonTextSubmit);

  $("#confirmModal")
    .addClass("deleteUrlModal")
    .modal("show")
    .on("hidden.bs.modal", () => {
      $("#confirmModal").removeClass("deleteUrlModal");
    });
  $("#modalRedirect").hide();
  hideIfShown($("#modalRedirect"));
}

// Prepares post request inputs for removal of a URL
function deleteURLSetup(utubID, utubUrlID) {
  const deleteURL = routes.deleteURL(utubID, utubUrlID);
  return deleteURL;
}

// Handles post request and response for removing an existing URL from current UTub, after confirmation
async function deleteURL(utubUrlID, urlCard) {
  const utubID = getActiveUTubID();
  try {
    // Check for stale data
    await getUpdatedURL(utubID, utubUrlID, urlCard);
    // Extract data to submit in POST request
    const deleteURL = deleteURLSetup(utubID, utubUrlID);

    const request = ajaxCall("delete", deleteURL, []);

    // Handle response
    request.done(function (response, textStatus, xhr) {
      if (xhr.status === 200) {
        deleteURLSuccessOnDelete(response, urlCard);
      }
    });

    request.fail(function (xhr, _, textStatus) {
      // Reroute to custom U4I 404 error page
      deleteURLFail(xhr);
    });
  } catch (error) {
    handleRejectFromGetURL(error, urlCard, { showError: false });
  }
}

// Displays changes related to a successful removal of a URL
function deleteURLSuccessOnDelete(response, urlCard) {
  // Close modal
  $("#confirmModal").modal("hide");
  urlCard.fadeOut("slow", function () {
    urlCard.remove();
    if ($("#listURLs .urlRow").length === 0) {
      $("#accessAllURLsBtn").hide();
      $("#NoURLsSubheader").show();
      $("#urlBtnDeckCreateWrap").show();
    } else {
      updateTagFilteringOnURLOrURLTagDeletion();
    }
  });
}

// Displays appropriate prompts and options to user following a failed removal of a URL
function deleteURLFail(xhr) {
  if (
    xhr.status === 403 &&
    xhr.getResponseHeader("Content-Type") === "text/html; charset=utf-8"
  ) {
    // Handle invalid CSRF token error response
    $("body").html(xhr.responseText);
    return;
  }

  switch (xhr.status) {
    case 403:
    case 404:
    default:
      window.location.assign(routes.errorPage);
  }
}
