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

  wrapperInput
    .append(label)
    .append(input);

  $(submitBtn)
    .on("click", function (e) {
      e.stopPropagation();
      e.preventDefault();
      addUser();
    });

  $(cancelBtn)
    .on("click", function (e) {
      e.stopPropagation();
      e.preventDefault();
      addUserHideInput();
    });

  $(wrapperBtns)
    .addClass("col-3 mb-md-0 py-4 d-flex flex-row")
    .append(submitBtn)
    .append(cancelBtn);

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

  if (numOfUsers === 1) {
    UserDeckSubheader.text("Add a user");
  }
  else {
    UserDeckSubheader.text(numOfUsers + " active users");
  }
}