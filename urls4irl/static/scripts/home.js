// General UI Interactions

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

  // Lol realized this doesn't work the way I intended 04/17/23s
  // Submission of user input data
  // $('.activeInput').on('blur', function () {
  //     console.log("Blur caught")
  //     let inputEl = $(this);
  //     console.log(inputEl)
  //     let handle = inputEl.attr('id');
  //     console.log(handle)

  //     if (document.activeElement.localname == 'input') {
  //         return;
  //     }

  //     if (inputEl[0].value) {
  //         postData(inputEl[0].value, handle)
  //     } else {
  //         // Input is empty
  //     }
  //     inputEl.hide();
  //     inputEl.removeClass('active');
  // })

  // Trigger blur and submit data
  $(document).on("keyup", function (e) {
    if (e.keyCode === 13) {
      e.preventDefault();
      e.target.blur();
    }
  });

  // Keyboard navigation between selected UTubs or URLs
  $(document).on("keyup", function (e) {
    let keycode = e.keyCode ? e.keyCode : e.which;
    let prev = keycode == 37 || keycode == 38;
    let next = keycode == 39 || keycode == 40;

    if ($("#URLFocusRow").length > 0) {
      // Some URL is selected, switch URLs

      let UPRcards = $("#UPRRow").children(".cardCol").length;
      let LWRcards = $("#LWRRow").children(".cardCol").length;

      if (prev && UPRcards > 0) {
        // User wants to highlight previous URL
        let cardCol = $($("#UPRRow").children(".cardCol")[UPRcards - 1]);
        selectURL($(cardCol[0].children).attr("urlid"));
      } else if (next && LWRcards > 0) {
        // User wants to highlight next URL
        let cardCol = $($("#LWRRow").children(".cardCol")[0]);
        selectURL($(cardCol[0].children).attr("urlid"));
      } else if (keycode == 27) {
        let activeURLCard = $(".url.selected").last();
        console.log(activeURLCard.attr("urlid"));
        if (activeURLCard.attr("urlid") == 0) {
          activeURLCard.parent().hide();
        } else {
          deselectURL(activeURLCard.parent());
        }
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

// Request user text input by placing a text input element in the appropriate location and await valid input
function showInput(handle) {
  let inputEl = $("#" + handle);
  let inputDiv = inputEl.closest(".createDiv");

  if (handle == "newURLDescription") {
    selectURL(inputDiv.find(".card").attr("urlid"));
  }

  // Show temporary div element containing input
  inputDiv.show("flex");
  inputEl.addClass("activeInput");

  if (handle.startsWith("editURL")) {
    // split handle, extract urlid, use it to find which inputs to unhide

    let inputEl2 = $("#editURLDescription-" + handle.split("-")[1]);
    let inputDiv2 = inputEl2.closest(".createDiv");
    let URLInfoDiv = inputEl2.closest(".URLInfo");
    let cardDiv = URLInfoDiv.closest(".card");
    let URLOptionsDiv = cardDiv.find(".URLOptions");

    URLInfoDiv.find("h5").hide();
    URLInfoDiv.find("p").hide();
    URLOptionsDiv.find(".editBtn").hide();
    URLOptionsDiv.find("i").show();

    inputDiv2.show("flex");
    inputEl2.addClass("activeInput");
  }

  inputEl.focus();
  inputEl[0].setSelectionRange(0, inputEl[0].value.length);
}

// Once valid data is received from the user, this function processes it and attempts a POST request
function postData(e, handle) {
  console.log("postData initiated");
  let postURL;
  let data;
  $(e.target).closest(".createDiv").hide();

  switcher = handle;

  if (handle.startsWith("editURL")) {
    switcher = "editURL";
  }

  // Extract data to submit in POST request
  switch (switcher) {
    case "createUTub":
      postURL = "/utub/new";
      let newUTubName = e.target.value;
      data = { name: newUTubName };

      break;

    case "createURL":
      postURL = "/url/add/" + currentUTubID();
      var createURLCardCol = $(e.target).parent().parent();
      let newURL = createURLCardCol.find(".card-title")[0].value;
      let newURLDescription = createURLCardCol.find(".card-text")[0].value;
      console.log(newURL);
      console.log(newURLDescription);
      data = {
        url_string: newURL,
        url_description: newURLDescription,
      };

      break;

    case "createTag":
      // postURL unimplemented as of 05/17/23
      postURL = "/tag/new";
      var newTagName = e.target.value;
      data = { tag_string: newTagName };

      break;

    case "editUTubDescription":
      console.log("Unimplemented");

      break;

    case "editURL":
      let URLID = handle.split("-")[1];

      postURL = "/url/edit/" + currentUTubID() + "/" + URLID;

      var URLCardDiv = $(e.target).parent().parent();
      var editedURLfield = URLCardDiv.find("#editURL-" + URLID)[0];
      var editedURL = editedURLfield.value
        ? editedURLfield.value
        : editedURLfield.placeholder;
      var editedURLDescriptionfield = URLCardDiv.find(
        "#editURLDescription-" + URLID,
      )[0];
      var editedURLDescription = editedURLDescriptionfield.value
        ? editedURLDescriptionfield.value
        : editedURLDescriptionfield.placeholder;
      data = {
        url_string: editedURL,
        url_description: editedURLDescription,
      };

      break;

    case "addTag":
      let urlid = $(e.target)[0].id.split("-")[1];

      postURL = "/tag/add/" + currentUTubID() + "/" + urlid;
      var newTagName = e.target.value;
      data = { tag_string: newTagName };

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

    default:
      console.log("Unimplemented");
  }

  let request = $.ajax({
    type: "post",
    url: postURL,
    data: data,
  });

  // Handle response

  request.done(function (response, textStatus, xhr) {
    console.log("success");

    if (xhr.status == 200) {
      switch (switcher) {
        case "createUTub":
          // Clear form and get ready for new input
          e.target.value = "";
          // Deselect current UTub
          $(".UTub").removeClass("active");
          $("input[type=radio]").prop("checked", false);

          createUTub(response.UTub_ID, response.UTub_name);

          break;

        case "createURL":
          // Reset creation block, clear form and get ready for new input
          createURLCardCol.find("#newURL")[0].value = "";
          createURLCardCol.find("#newURLDescription")[0].value = "";

          // Create and display new URL
          let URLDescription = response.URL.url_description;
          var URLID = response.URL.url_ID;

          let URLcol = createURL(
            URLID,
            response.URL.url_string,
            URLDescription,
            [],
            [],
          );
          $(URLcol).insertAfter(".url.selected");

          selectURL(URLID);

          break;

        case "createTag":
          createTaginDeck(response.tag.tag_ID, response.tag.string);

          break;

        case "editUTubDescription":
          console.log("Unimplemented");

          break;

        case "addTag":
          var URLID = response.URL.url_id;
          let tagid = response.Tag.id;

          // Add tag to URL
          let tagSpan = createTaginURL(tagid, response.Tag.tag_string, URLID);

          $("div[urlid=" + URLID + "]")
            .find(".URLTags")
            .append(tagSpan);

          // Check to see if tag is new
          let tagIDArray = currentTagDeckIDs();
          let tagDeckBool = 0;
          // tagDeckBool set to true if tag exists in deck already
          for (let i in tagIDArray) {
            if (tagIDArray[i] == tagid) {
              tagDeckBool = 1;
              break;
            }
          }
          // If tag does not exist in the Tag Deck (brand new tag), add to the Deck
          if (!tagDeckBool) createTaginDeck(tagid, response.Tag.tag_string);

          break;

        case "editURL":
          // Refresh UTub
          changeUTub(currentUTubID());

          break;

        case "editURLDescription":
          console.log("Unimplemented");

          break;

        default:
          console.log("Unimplemented");
      }
    }
  });

  request.fail(function (response, textStatus, xhr) {
    console.log("failed");
    // console.log(response.responseJSON.Error_code)

    if (xhr.status == 404) {
      // Reroute to custom U4I 404 error page
    } else {
      switch (switcher) {
        case "createUTub":
          console.log("Unimplemented");
          break;
        case "createURL":
          console.log("Unimplemented");
          break;
        case "createTag":
          console.log("Unimplemented");
          break;
        case "editUTubDescription":
          console.log("Unimplemented");
          break;
        case "addTag":
          console.log("Unimplemented");
          break;
        case "editURL":
          console.log("Unimplemented");
          break;
        case "editURLDescription":
          console.log("Unimplemented");
          break;
        default:
          console.log("Unimplemented");
      }
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

function cardEdit(selectedUTubID, selectedURLid, infoType) {
  let jQuerySel = "div.url.selected[urlid=" + selectedURLid + "]"; // Find jQuery selector with selected ID
  let inputParent;
  let initString;
  let inputEl;
  let inputID;
  let postURL;
  let originalURL;

  if (infoType == "tag") {
    inputParent = $(jQuerySel).find("div.URLTags"); // Find appropriate card element
    initString = "";
    inputEl = $("#new_tag"); // Temporary input text element
    inputID = "new_tag";
    postURL = "/tag/add/";
  } else {
    inputParent = $(jQuerySel).find("p.card-text"); // Find appropriate card element
    initString = inputParent[0].innerText; // Store pre-edit values
    originalURL = inputParent[0].innerText; // Store pre-edit values
    $(inputParent).html(""); // Clear url card-text
    inputEl = $("#edit_url"); // Temporary input text element
    inputID = "edit_url";
    postURL = "/url/edit/";
  }

  let route;

  if (inputEl.length == 0) {
    // Temporary input text element does not exist, create one and inject
    route = postURL + selectedUTubID + "/" + selectedURLid;

    $("<input></input>")
      .attr({
        // Replace with temporary input
        type: "text",
        id: inputID,
        size: "30",
        value: initString,
      })
      .appendTo($(inputParent));

    inputEl = $("#" + inputID);
  }

  let end = inputEl[0].value.length;
  inputEl.focus();
  inputEl[0].setSelectionRange(0, end);

  inputEl.on("keyup", function (e) {
    // Pressing enter is the same as blur, and submission
    if (e.keyCode === 13) {
      e.target.blur();
    }
  });

  // User submitted a card edit
  inputEl.on("blur", function (e) {
    if (inputEl[0].value != "") {
      let request = $.ajax({
        type: "post",
        url: postURL + selectedUTubID + "/" + selectedURLid,
        data: { tag_string: inputEl[0].value },
      });

      request.done(function (response, textStatus, xhr) {
        if (xhr.status == 200) {
          if (infoType == "url") {
            if (inputEl[0].value == "") {
              inputParent[0].innerHTML = originalURL;
            } else {
              inputParent[0].innerHTML = inputEl[0].value;
            }
          } else {
            if (inputEl[0].value != "") {
              $("<span></span>")
                .attr({
                  // Replace with temporary input
                  class: "tag",
                  tagid: response.Tag.tag_ID,
                })
                .appendTo($(inputParent));
              $(".tag")[$(".tag").length - 1].innerText = inputEl[0].value; // here's where things go to shit
            }
          }
          console.log("finished edit");
          // getUtubInfo(selectedUTubID);
          // console.log("starting to select")
          // selectURL(selectedURLid);
          // console.log("done selecting")
        }
      });
    }

    inputEl.remove();
  });
}
