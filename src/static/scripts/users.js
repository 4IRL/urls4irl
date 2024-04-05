/** User-related constants **/

// Routes
const ADD_USER_ROUTE = "/user/add/"; // +<int:utub_id>
const REMOVE_USER_ROUTE = "/user/remove/"; // +<int:utub_id>/<int:user_id>

/** User UI Interactions **/

$(document).ready(function () {
  /* Bind click functions */

  // Add user to UTub
  $("#addUserBtn").on("click", function (e) {
    // e.stopPropagation();
    // e.preventDefault();
    hideInputs();
    deselectAllURLs();
    addUserShowInput();
    // Bind enter key (keycode 13) to submit user input
    // DP 12/29 It'd be nice to have a single utils.js function with inputs of function and keyTarget (see semi-successful attempt under bindKeyToFunction() in utils.js)
    unbindEnter();
    $(document).bind("keypress", function (e) {
      if (e.which == 13) {
        addUser();
      }
    });
  });
});

/** User Utility Functions **/

// Simple function to streamline the jQuery selector extraction of selected user ID. And makes it easier in case the ID is encoded in a new location in the future
function getCurrentUserID() {
  return parseInt($("li.nav-item.user").attr("id"));
}

// Simple function to streamline the jQuery selector extraction of selected UTub creator user ID. And makes it easier in case the ID is encoded in a new location in the future
function getCurrentUTubCreatorID() {
  return $("#UTubOwner").find("span").attr("userid");
}

// Clear user selection
function resetNewUserForm() {
  $("#addUser").val("");
  hideIfShown($("#addUser").closest(".createDiv"));
}

// Clear the User Deck
function resetUserDeck() {
  $("#UTubOwner").empty();
  $("#listUsers").empty();
}

/** User Functions **/

// Build center panel URL list for selectedUTub
function buildUserDeck(dictUsers, UTubOwnerID) {
  resetUserDeck();
  const parent = $("#listUsers");
  let numOfUsers = dictUsers.length;
  let UTubUser;
  let UTubUserID;

  // Instantiate deck with list of users with access to current UTub
  for (let i = 0; i < numOfUsers; i++) {
    UTubUser = dictUsers[i];
    UTubUsername = UTubUser.username;
    UTubUserID = UTubUser.id;

    if (UTubUserID == UTubOwnerID) {
      $("#UTubOwner").append(createOwnerBadge(UTubOwnerID, UTubUsername));
    } else {
      parent.append(createUserBadge(UTubUserID, UTubUsername));
    }
  }

  // Subheader prompt
  displayState1UserDeck(numOfUsers);

  // Ability to add users is restricted to UTub owner
  if (getCurrentUTubCreatorID() == UTubOwnerID) {
    showIfHidden($("#addUserBtn"));
    parent.append(createNewUserInputField());
  } else hideIfShown($("#addUserBtn"));
}

// Creates user list item
function createOwnerBadge(UTubOwnerID, UTubUsername) {
  let userSpan = document.createElement("span");

  $(userSpan)
    .attr({ userid: UTubOwnerID })
    .addClass("user")
    .html("<b>" + UTubUsername + "</b>");

  return userSpan;
}

// Creates user list item
function createUserBadge(UTubUserID, UTubUsername) {
  let userListItem = document.createElement("li");
  let userSpan = document.createElement("span");
  let removeButton = document.createElement("a");

  $(userSpan)
    .attr({ userid: UTubUserID })
    .addClass("user")
    .html("<b>" + UTubUsername + "</b>");

  $(removeButton)
    .attr({ class: "btn btn-sm btn-outline-link border-0 user-remove" })
    .on("click", function (e) {
      e.stopPropagation();
      e.preventDefault();
      removeUserShowModal(UTubUserID);
    });
  removeButton.innerHTML = "&times;";

  $(userSpan).append(removeButton);
  $(userListItem).append(userSpan);

  return userListItem;
}

// Creates a typically hidden input text field. When creation of a new UTub is requested, it is shown to the user. Input field recreated here to ensure at the end of list after creation of new UTubs
function createNewUserInputField() {
  const wrapper = $(document.createElement("div"));
  const wrapperInput = $(document.createElement("fieldset")); // This element wraps the new user input
  const wrapperBtns = $(document.createElement("div"));

  const label = document.createElement("label"); // This element labels the new user field
  const input = $(document.createElement("input"));
  const submitBtn = makeSubmitButton(30);
  const cancelBtn = makeCancelButton(30);

  $(wrapper)
    .attr({
      style: "display: none",
    })
    .addClass("createDiv row");

  $(wrapperInput).addClass("col-9 col-lg-9 mb-md-0");

  $(label)
    .attr({
      for: "addUser",
      style: "display:block",
    })
    .html("<b> Username </b>");

  $(input)
    .attr({
      id: "addUser",
      type: "text",
      placeholder: "Username",
    })
    .addClass("User userInput");

  wrapperInput.append(label).append(input);

  $(wrapperBtns).addClass("col-3 mb-md-0 py-4 d-flex flex-row");

  // // Submit addUser checkbox
  // let htmlString =
  //   '<svg xmlns="http://www.w3.org/2000/svg" fill="currentColor" class="b=i bi-check-square-fill" viewBox="0 0 16 16" width="' +
  //   ICON_WIDTH +
  //   '" height="' +
  //   ICON_HEIGHT +
  //   '">' +
  //   '<path d="M2 0a2 2 0 0 0-2 2v12a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V2a2 2 0 0 0-2-2zm10.03 4.97a.75.75 0 0 1 .011 1.05l-3.992 4.99a.75.75 0 0 1-1.08.02L4.324 8.384a.75.75 0 1 1 1.06-1.06l2.094 2.093 3.473-4.425a.75.75 0 0 1 1.08-.022z"/></svg>';

  // $(submit)
  //   .addClass("mx-1 green-clickable")
  //   .on("click", function (e) {
  //     e.stopPropagation();
  //     e.preventDefault();
  //     addUser();
  //   })
  //   .html(htmlString);

  wrapperBtns.append(submitBtn);

  // // Cancel add User x-box
  // htmlString =
  //   '<svg xmlns="http://www.w3.org/2000/svg" fill="currentColor" class="bi bi-x-square-fill text-danger" viewBox="0 0 16 16" width="' +
  //   ICON_WIDTH +
  //   '" height="' +
  //   ICON_HEIGHT +
  //   '">' +
  //   '<path d="M2 0a2 2 0 0 0-2 2v12a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V2a2 2 0 0 0-2-2zm3.354 4.646L8 7.293l2.646-2.647a.5.5 0 0 1 .708.708L8.707 8l2.647 2.646a.5.5 0 0 1-.708.708L8 8.707l-2.646 2.647a.5.5 0 0 1-.708-.708L7.293 8 4.646 5.354a.5.5 0 1 1 .708-.708"/></svg>';

  // $(cancel)
  //   .addClass("mx-1")
  //   .on("click", function (e) {
  //     e.stopPropagation();
  //     e.preventDefault();
  //     hideIfShown(wrapper);
  //   })
  //   .html(htmlString);

  wrapperBtns.append(cancelBtn);

  wrapper.append(wrapperInput);
  wrapper.append(wrapperBtns);

  return wrapper;
}

/** User Display State Functions **/

// Display state 0: Clean slate, no UTub selected
function displayState0UserDeck() {
  resetUserDeck();

  // Subheader prompt hidden
  hideIfShown($("#UserDeckSubheader").closest(".row"));

  hideIfShown($("#addUserBtn"));
}

// Display state 1: Selected UTub has no Users
function displayState1UserDeck() {
  // Subheader prompt shown
  showIfHidden($("#UserDeckSubheader").closest(".row"));

  showIfHidden($("#addUserBtn"));

  let numOfUsers = $("#listUsers").find("span.user").length + 1; // plus 1 for owner
  let UserDeckSubheader = $("#UserDeckSubheader");
  if (numOfUsers === 1) UserDeckSubheader.text("Add a user");
  else UserDeckSubheader.text(numOfUsers + " active users");
}