/** Members UI Interactions **/

$(document).ready(function () {
  /* Bind click functions */

  // Add member to UTub
  $("#addMemberBtn").on("click", function (e) {
    // e.stopPropagation();
    // e.preventDefault();
    hideInputs();
    deselectAllURLs();
    addMemberShowInput();
  });
});

/** Members Utility Functions **/

// Simple function to streamline the jQuery selector extraction of selected user ID. And makes it easier in case the ID is encoded in a new location in the future
function getCurrentUserID() {
  return parseInt($("li.nav-item.user").attr("userID"));
}

// Simple function to streamline the jQuery selector extraction of selected UTub creator user ID. And makes it easier in case the ID is encoded in a new location in the future
function getCurrentUTubOwnerUserID() {
  return $("#UTubOwner").find("span").attr("memberid");
}

// Clear member selection
function resetNewMemberForm() {
  $("#addMember").val("");
  // hideIfShown($("#addMember").closest(".createDiv"));
}

// Clear the Member Deck
function resetMemberDeck() {
  $("#UTubOwner").empty();
  $("#listMembers").empty();
}

/** Member Functions **/

// Build center panel URL list for selectedUTub
function buildMemberDeck(dictMembers, UTubOwnerUserID) {
  resetMemberDeck();
  const parent = $("#listMembers");
  let numOfMembers = dictMembers.length;
  let UTubMember;
  let UTubMemberUsername;
  let UTubMemberUserID;

  // Instantiate deck with list of members with access to current UTub
  for (let i = 0; i < numOfMembers; i++) {
    UTubMember = dictMembers[i];
    UTubMemberUsername = UTubMember.username;
    UTubMemberUserID = UTubMember.id;

    if (UTubMemberUserID == UTubOwnerUserID) {
      $("#UTubOwner").append(
        createOwnerBadge(UTubOwnerUserID, UTubMemberUsername),
      );
    } else {
      parent.append(createMemberBadge(UTubMemberUserID, UTubMemberUsername));
    }
  }

  // Subheader prompt
  displayState1MemberDeck(numOfMembers);

  // Ability to add members is restricted to UTub owner
  if (getCurrentUTubOwnerUserID() == UTubOwnerUserID) {
    showIfHidden($("#addMemberBtn"));
    parent.append(createNewMemberInputField());
  } else hideIfShown($("#addMemberBtn"));
}

// Creates member list item
function createOwnerBadge(UTubOwnerUserID, UTubMemberUsername) {
  let memberSpan = document.createElement("span");

  $(memberSpan)
    .attr({ memberid: UTubOwnerUserID })
    .addClass("member")
    .html("<b>" + UTubMemberUsername + "</b>");

  return memberSpan;
}

// Creates member list item
function createMemberBadge(UTubMemberUserID, UTubMemberUsername) {
  let memberListItem = document.createElement("li");
  let memberSpan = document.createElement("span");
  let removeButton = document.createElement("a");

  $(memberSpan)
    .attr({ memberid: UTubMemberUserID })
    .addClass("member")
    .html("<b>" + UTubMemberUsername + "</b>");

  $(removeButton)
    .attr({ class: "btn btn-sm btn-outline-link border-0 member-remove" })
    .on("click", function (e) {
      e.stopPropagation();
      e.preventDefault();
      removeMemberShowModal(UTubMemberUserID);
    });
  removeButton.innerHTML = "&times;";

  $(memberSpan).append(removeButton);
  $(memberListItem).append(memberSpan);

  return memberListItem;
}

// Creates a typically hidden input text field. When creation of a new UTub is requested, it is shown to the member. Input field recreated here to ensure at the end of list after creation of new UTubs
function createNewMemberInputField() {
  const wrapper = $(document.createElement("div"));
  const wrapperInput = $(document.createElement("div")); // This element wraps the new member input
  const wrapperBtns = $(document.createElement("div")); // This element wraps the buttons

  const label = document.createElement("label"); // This element labels the new member field
  const input = $(document.createElement("input"));
  const submitBtn = makeSubmitButton(30);
  const cancelBtn = makeCancelButton(30);

  $(wrapper)
    .attr({
      style: "display: none",
    })
    .addClass("createDiv row");

  $(label)
    .attr({
      for: "addMember",
      style: "display:block",
    })
    .html("<b> Member Username </b>");

  $(input)
    .attr({
      id: "addMember",
      type: "text",
      placeholder: "Member Username",
    })
    .addClass("Member userInput");

  $(wrapperInput)
    .addClass("col-9 col-lg-9 mb-md-0")
    .append(label)
    .append(input);

  $(submitBtn).on("click", function (e) {
    e.stopPropagation();
    e.preventDefault();
    addMember();
  });

  $(cancelBtn).on("click", function (e) {
    e.stopPropagation();
    e.preventDefault();
    addMemberHideInput();
  });

  $(wrapperBtns)
    .addClass("col-3 mb-md-0 py-4 d-flex flex-row")
    .append(submitBtn)
    .append(cancelBtn);

  wrapper.append(wrapperInput);
  wrapper.append(wrapperBtns);

  return wrapper;
}

/** Member Display State Functions **/

// Display state 0: Clean slate, no UTub selected
function displayState0MemberDeck() {
  resetMemberDeck();

  hideIfShown($("#addMemberBtn"));

  // Subheader prompt hidden
  hideIfShown($("#MemberDeckSubheader").closest(".row"));
}

// Display state 1: Selected UTub has no Members
function displayState1MemberDeck() {
  showIfHidden($("#addMemberBtn"));

  let MemberDeckSubheader = $("#MemberDeckSubheader");

  // Subheader prompt shown
  showIfHidden(MemberDeckSubheader.closest(".row"));

  // Count UTub members
  let numOfMembers = $("#listMembers").find("span.member").length + 1; // plus 1 for owner

  if (numOfMembers === 1) {
    MemberDeckSubheader.text("Add a member");
  } else {
    MemberDeckSubheader.text(numOfMembers + " active members");
  }
}
