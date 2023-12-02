/* General UI Interactions */

$(document).ready(function () {
  // Dev tracking of click-triggered objects
  $(document).click(function (e) {
    console.log($(e.target)[0]);
  });

  // CSRF token initialization for non-modal POST requests
  let csrftoken = $("meta[name=csrf-token]").attr("content");
  $.ajaxSetup({
    beforeSend: function (xhr, settings) {
      if (
        !/^(GET|HEAD|OPTIONS|TRACE)$/i.test(settings.type) &&
        !this.crossDomain
      ) {
        xhr.setRequestHeader("X-CSRFToken", csrftoken);
      }
    },
  });

  // Prevent form refresh of page on submittal
  $("form").on("submit", function () {
    return false;
  });

  // Keyboard navigation between selected UTubs or URLs
  $(document).on("keyup", function (e) {
    let keycode = e.keyCode ? e.keyCode : e.which;
    let prev = keycode == 37 || keycode == 38; // UP and LEFT keys
    let next = keycode == 39 || keycode == 40; // DOWN and RIGHT keys

    if ($("#URLFocusRow").length > 0) {
      // Some URL is selected, switch URLs

      let UPRcards = $("#UPRRow").children(".cardCol").length;
      let LWRcards = $("#LWRRow").children(".cardCol").length;

      if (prev && UPRcards > 0) {
        // User wants to highlight previous URL
        let cardCol = $($("#UPRRow").children(".cardCol")[UPRcards - 1]);
        toggleSelectedURL($(cardCol[0].children).attr("urlid"));
      } else if (next && LWRcards > 0) {
        // User wants to highlight next URL
        let cardCol = $($("#LWRRow").children(".cardCol")[0]);
        toggleSelectedURL($(cardCol[0].children).attr("urlid"));
      }
    } else {
      // No URL selected, switch UTubs
    }
  });

  // Navbar animation
  $(".first-button").on("click", function () {
    $(".animated-icon1").toggleClass("open");
  });
  $(".second-button").on("click", function () {
    $(".animated-icon2").toggleClass("open");
  });
  $(".third-button").on("click", function () {
    $(".animated-icon3").toggleClass("open");
  });
});

// General Functions

// Request user text input by showing the appropriate text input element and await valid input
function showInput(handle) {
  let inputEl = $("#" + handle);
  let inputDiv = inputEl.closest(".createDiv");
  showIfHidden(inputDiv);
}

// Highlight the input field. Typically if user requests action that is already displayed
function highlightInput(inputEl) {
  inputEl.focus();
  if (inputEl[0].value) {
    inputEl[0].setSelectionRange(0, inputEl[0].value.length);
  }
}

// Hide input fields if user successfully completes, or cancels an action
function hideInput(handle) {
  let inputEl = $("#" + handle);
  let inputDiv = inputEl.closest(".createDiv");
  hideIfShown(inputDiv);
}

// Once valid data is received from the user, this function processes it and attempts a POST request
function postData(e, handle) {
  // console.log($(e.target));
  // console.log("was clicked");
  // console.log(handle + " postData initiated");
  let postURL;
  let data;

  // Extract data to submit in POST request
  [data, postURL] = postRequestSetup(e, handle);

  // if (data.isEmpty()) postRequestCleanupNeutral()?;
  console.log(data);
  console.log(selectedURLID());

  // POST request
  let request = $.ajax({
    type: "post",
    url: postURL,
    data: data,
  });

  // Handle response
  request.done(function (response, textStatus, xhr) {
    console.log("success");

    if (xhr.status == 200) {
      postRequestCleanupSuccess(e, handle, response);
    }
  });

  request.fail(function (response, textStatus, xhr) {
    console.log("failed");

    if (xhr.status == 404) {
      // Reroute to custom U4I 404 error page
    } else {
      postRequestCleanupFail(e, handle, response, textStatus, xhr);
    }
  });
}

// Extract data to submit in POST request
function postRequestSetup(e, handle) {
  let data;

  switch (handle) {
    case "createUTub":
      postURL = "/utub/new";
      let newUTubName = e.target.value;
      data = { name: newUTubName };

      console.log(UTubs);
      let UTubNames = UTubs.map((x) => x.name);
      console.log(UTubNames);

      if (UTubNames.includes(data.name)) {
        confirmModal(handle);
      }

      break;

    case "createURL":
      postURL = "/url/add/" + currentUTubID();

      let newURLDescription = $("#newURLDescription")[0].value;
      let newURL = $("#newURL")[0].value;
      data = {
        url_string: newURL,
        url_description: newURLDescription,
      };

      break;

    case "createTag":
      // postURL unimplemented as of 05/17/23
      postURL = "/tag/new";
      let newTagName = e.target.value;
      data = { tag_string: newTagName };

      break;

    case "editUTub":
      postURL = "/utub/edit_name/" + currentUTubID();

      let editedUTubName = $("#editUTub")[0].value;
      data = { name: editedUTubName };

      break;

    case "editUTubDescription":
      postURL = "/utub/edit_description/" + currentUTubID();

      let editedUTubDescription = $("#editUTubDescription")[0].value;
      data = { utub_description: editedUTubDescription };

      break;

    case "editURL":
      postURL = "/url/edit/" + currentUTubID() + "/" + selectedURLID();

      let URLCardDiv = $(e.target).closest(".card");
      let editedURLfield = URLCardDiv.find(".editURLString")[0];
      let editedURL = editedURLfield.value;
      let editedURLDescriptionfield = URLCardDiv.find(".editURLDescription")[0];
      let editedURLDescription = editedURLDescriptionfield.value;
      data = {
        url_string: editedURL,
        url_description: editedURLDescription,
      };

      break;

    case "addTagToURL":
      postURL = "/tag/add/" + currentUTubID() + "/" + selectedURLID();

      let cardDiv = $(e.target).closest(".card");
      let addTagName = cardDiv.find(".addTag")[0].value;
      data = { tag_string: addTagName };

      break;

    case "editTags":
      // Send UTubID
      let tagID = e[0];
      let tagText = e[1];
      postURL = "/tag/edit/" + tagID;
      data = {
        id: tagID,
        tag_string: tagText,
      };

      break;

    case "deleteUTub":
      postURL = "/utub/delete/" + currentUTubID();

      break;

    case "deleteURL":
      postURL = "/url/remove/" + currentUTubID() + "/" + selectedURLID();

      break;

    case "deleteUser":
      // postURL = "/url/remove/" + currentUTubID() + "/" + URLID

      removeUser();

      break;

    default:
      console.log("Unimplemented");
  }

  return [data, postURL];
}

function postRequestCleanupSuccess(e, handle, response) {
  switch (handle) {
    case "createUTub":
      // Updating and hiding input fields
      hideIfShown($(e.target).closest(".createDiv"));
      e.target.value = "";

      // Deselect current UTub
      $(".UTub").removeClass("active");
      $("input[type=radio]").prop("checked", false);

      // Find last position
      let i = $(".UTub").last()[0].position + 1;
      let newUTubID = response.UTub_ID;

      $("#listUTubs").append(
        createUTubSelector(response.UTub_name, newUTubID, i),
      );
      changeUTub(newUTubID);

      break;

    case "createURL":
      // Create and display new URL
      let newURLDescription = response.URL.url_description;
      let newURLIDForURL = response.URL.url_ID;

      let URLcol = createURLBlock(
        newURLIDForURL,
        response.URL.url_string,
        newURLDescription,
        [],
        [],
      );
      $(URLcol).insertBefore("#createURL");

      resetCreateURLForm();
      selectURL(URLcol);

      break;

    case "createTag":
      // Create and display new tag in deck
      let tagid = response.tag.tag_ID;
      let string = response.tag.string;

      $(e.target).closest(".createDiv").val("");
      hideIfShown($(e.target).closest(".createDiv"));
      hideIfShown($("#noTagsHeader"));

      createTaginDeck(tagid, string);

      break;

    case "editUTub":
      hideIfShown($(e.target).closest(".createDiv"));

      // Create and display new UTub name
      let UTubName = response.UTub_name;

      // UTub deck entry
      let label = $(".UTub.active");
      label.find("b").text(UTubName);
      label.find("input").value = UTubName;

      // URL deck title
      showIfHidden($("#URLDeckHeader"));
      $("#URLDeckHeader").text(UTubName);

      postData(e, "editUTubDescription");

      break;
    case "editUTubDescription":
      let editUTubDescriptionTextArea = $("#editUTubDescription");
      hideIfShown(editUTubDescriptionTextArea.closest(".createDiv"));

      // Create and display new UTub description
      let UTubDescription = response.UTub_description;
      $("#UTubDescription").text(UTubDescription);
      showIfHidden($("#UTubDescription"));

      // UTub description
      editUTubDescriptionTextArea.text(UTubDescription);

      // Option to edit again
      showIfHidden($("#editUTubButton"));

      break;

    case "addTagToURL":
      console.log(response);
      let newTagForURLID = response.URL.url_id;
      let tagID = response.Tag.id;
      let tagString = response.Tag.tag_string;

      // Add tag to URL
      let tagSpan = createTaginURL(tagID, tagString);
      console.log(tagSpan);

      let targetURLTagContainer = $("div[urlid='" + newTagForURLID + "']").find(
        ".URLTags",
      );
      targetURLTagContainer.append(tagSpan);

      console.log(newTagForURLID);
      console.log(targetURLTagContainer);

      // Check to see if tag is new
      let tagIDArray = currentTagDeckIDs();
      let tagDeckBool = 0;
      // tagDeckBool set to true if tag exists in deck already
      for (let i in tagIDArray) {
        if (tagIDArray[i] == tagID) {
          tagDeckBool = 1;
          break;
        }
      }
      // If tag does not exist in the Tag Deck (brand new tag), add to the Deck
      if (!tagDeckBool) createTaginDeck(tagID, tagString);

      // If edit URL action, rebind the ability to select/deselect URL by clicking it
      rebindSelectBehavior($(e.target).closest(".cardCol"));

      // Updating and hiding input fields
      $(e.target).closest(".createDiv").val("");
      hideIfShown($(e.target).closest(".createDiv"));
      hideIfShown($("#noTagsHeader"));

      break;

    case "editURL":
      break;

    case "editURLDescription":
      console.log("Unimplemented");

      break;

    case "deleteUTub":
      deleteUTub(response.UTub_ID);
      break;

    case "deleteURL":
      deleteURL();
      break;

    case "deleteUser":
      removeUser();
      break;

    default:
      console.log("Unimplemented");
  }
}

function postRequestCleanupFail(e, handle, response, textStatus, xhr) {
  if (
    response.responseJSON.hasOwnProperty("Status") &&
    response.responseJSON.Status == "Failure"
  ) {
    switch (handle) {
      case "createUTub":
        console.log(response.message);
        break;
      case "createURL":
        console.log("Unimplemented");

        console.log(response.responseJSON);
        createURLCleanupFail();

        break;
      case "createTag":
        console.log("Unimplemented");
        break;
      case "editUTubDescription":
        console.log("Unimplemented");
        break;
      case "addTagToURL":
        console.log("Unimplemented");
        break;
      case "editURL":
        console.log("Unimplemented");
        break;
      case "editURLDescription":
        console.log("Unimplemented");
        break;
      case "deleteUTub":
        if (xhr.status == 409) {
          console.log(
            "Failure. Status code: " + xhr.status + ". Status: " + textStatus,
          );
        } else if (xhr.status == 404) {
          $(".invalid-feedback").remove();
          $(".alert").remove();
          $(".form-control").removeClass("is-invalid");
          const error = JSON.parse(xhr.responseJSON);
          for (let key in error) {
            $(
              '<div class="invalid-feedback"><span>' +
                error[key] +
                "</span></div>",
            )
              .insertAfter("#" + key)
              .show();
            $("#" + key).addClass("is-invalid");
          }
        }

        console.log("Error: " + error);

        break;
      case "deleteURL":
        console.log("Unimplemented");
        break;
      case "deleteUser":
        console.log("Unimplemented");
        break;

      default:
        console.log("Unimplemented");
    }
  } else {
    console.log("No error code");
    if (xhr.status == 409) {
    } else if (xhr.status == 404) {
    }
  }
}

function confirmModal(handle) {
  // Modal adjustments
  switch (handle) {
    case "createUTub":
      var modalTitle =
        "Are you sure you want to create a new UTub with this name?";
      var modalBody = "A UTub in your portfolio has a similar name.";
      var buttonText = "Go back";
      break;
    case "deleteUser":
      var modalTitle =
        "Are you sure you want to remove this user from the current UTub?";
      break;
    default:
      console.log("Unimplemented");
  }

  $(".modal-title").text(modalTitle);
  $("#modal-body").text(modalBody);

  $("#confirmModal").modal("show");

  $("#modalSubmit").on("click", function (e) {
    postData(e, handle);
    e.preventDefault();
    switch (handle) {
    }
  });
}

// Creates option dropdown menu of users in RH UTub information panel
function gatherUsers(dictUsers, creator) {
  html = "<option disabled selected value> -- Select a User -- </option>";
  for (let i in dictUsers) {
    let user = dictUsers[i];
    if (user.id == creator) {
      $("#UTubOwner")[0].innerHTML = user.username;
    } else {
      html += "<option value=" + user.id + ">" + user.username + "</option>";
    }
  }
  $("#UTubUsers")[0].innerHTML = html;
}
