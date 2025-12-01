"use strict";

function setUnselectUpdateUTubTagEventListeners() {
  const utubTagBtnUnselectAll = $("#utubTagBtnUpdateAllOpen");
  utubTagBtnUnselectAll
    .offAndOn("click.openUTubTagUpdate", function () {
      setTagDeckBtnsOnUpdateAllUTubTagsOpened();
      openUTubTagBtnMenuOnUTubTags();
    })
    .offAndOn("focus.openUTubTagUpdate", function () {
      $(document).offAndOn("keyup.openUTubTagUpdate", function (e) {
        if (e.key === KEYS.ENTER) {
          setTagDeckBtnsOnUpdateAllUTubTagsOpened();
          openUTubTagBtnMenuOnUTubTags();
        }
      });
    })
    .offAndOn("blur.openUTubTagUpdate", function () {
      $(document).off("keyup.openUTubTagUpdate");
    });

  const utubTagBtnUpdateAllClose = $("#utubTagBtnUpdateAllClose");
  utubTagBtnUpdateAllClose
    .offAndOn("click.closeUTubTagUpdate", function () {
      setTagDeckBtnsOnUpdateAllUTubTagsClosed();
      closeUTubTagBtnMenuOnUTubTags();
    })
    .offAndOn("focus.closeUTubTagUpdate", function () {
      $(document).offAndOn("keyup.closeUTubTagUpdate", function (e) {
        if (e.key === KEYS.ENTER) {
          setTagDeckBtnsOnUpdateAllUTubTagsClosed();
          closeUTubTagBtnMenuOnUTubTags();
        }
      });
    })
    .offAndOn("blur.closeUTubTagUpdate", function () {
      $(document).off("keyup.closeUTubTagUpdate");
    });
}

function deleteUTubTagHideModal() {
  $("#confirmModal").modal("hide");
}

function deleteUTubTagShowModal(utubID, utubTagID) {
  const modalTitle = "Are you sure you want to delete this Tag?";
  const modalBody = `${STRINGS.UTUB_TAG_DELETE_WARNING}`;
  const buttonTextDismiss = "Nevermind...";
  const buttonTextSubmit = "Delete this sucka!";

  $("#confirmModalTitle").text(modalTitle);

  $("#confirmModalBody").text(modalBody);

  $("#modalDismiss")
    .removeClass()
    .addClass("btn btn-secondary")
    .offAndOn("click", function (e) {
      e.preventDefault();
      deleteUTubTagHideModal();
    })
    .text(buttonTextDismiss);

  $("#modalSubmit")
    .removeClass()
    .addClass("btn btn-danger")
    .text(buttonTextSubmit)
    .offAndOn("click", function (e) {
      e.preventDefault();
      deleteUTubTag(utubID, utubTagID);
    });

  $("#confirmModal").modal("show");
  $("#modalRedirect").hide();
}

function deleteUTubTagSetup(utubID, utubTagID) {
  debugger;
  let deleteURL = routes.deleteUTubTag(utubID, utubTagID);

  return deleteURL;
}

function deleteUTubTag(utubID, utubTagID) {
  let deleteUTubTagURL = deleteUTubTagSetup(utubID, utubTagID);

  const request = ajaxCall("delete", deleteUTubTagURL, []);

  // Handle response
  request.done(function (response, textStatus, xhr) {
    if (xhr.status === 200) {
      deleteUTubTagSuccess(response);
    }
  });

  request.fail(function (xhr, textStatus, errorThrown) {
    deleteUTubTagFail(xhr);
  });
}

function deleteUTubTagSuccess(response) {
  // Close the modal
  $("#confirmModal").modal("hide");

  // Remove the UTub Tag
  const utubTagID = response.utubTag.utubTagID;

  const utubTagSelector = $(".tagFilter[data-utub-tag-id=" + utubTagID + "]");
  utubTagSelector.fadeOut("slow", () => {
    utubTagSelector.remove();
  });

  // Remove the tag from associated URLs
  const urlTagBadges = $(".tagBadge[data-utub-tag-id=" + utubTagID + "]");
  urlTagBadges.remove();
}

function deleteUTubTagFail() {
  // Idempotent operation - on failure let nothing happen
  $("#confirmModal").modal("hide");
  return;
}
