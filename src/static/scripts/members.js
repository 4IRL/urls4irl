/** Members UI Interactions **/

$(document).ready(function () {
  /* Bind click functions */

  // Add member to UTub
  $("#memberBtnCreate").on("click.createMember", function () {
    hideInputs();
    deselectAllUrls();
    createMemberShowInput();
  });
});

/** Members Utility Functions **/

// Simple function to streamline the jQuery selector extraction of selected user ID. And makes it easier in case the ID is encoded in a new location in the future
function getCurrentUserID() {
  return parseInt($("li.nav-item.user").attr("userID"));
}

// Simple function to streamline the jQuery selector extraction of selected UTub creator user ID. And makes it easier in case the ID is encoded in a new location in the future
function getCurrentUTubOwnerUserID() {
  return parseInt($("#UTubOwner").find("span").attr("memberid"));
}

// Clear member selection
function resetNewMemberForm() {
  $("#memberCreate").val(null);
}

// Clear the Member Deck
function resetMemberDeck() {
  $("#UTubOwner").empty();
  $("#listMembers").empty();
}

/** Member Functions **/

// Build center panel URL list for selectedUTub
function buildMemberDeck(dictMembers, UTubOwnerUserID, isCurrentUserOwner) {
  resetMemberDeck();
  const parent = $("#listMembers");
  const numOfMembers = dictMembers.length;
  let UTubMember;
  let UTubMemberUsername;
  let UTubMemberUserID;

  // Instantiate deck with list of members with access to current UTub
  for (let i = 0; i < numOfMembers; i++) {
    UTubMember = dictMembers[i];
    UTubMemberUsername = UTubMember.username;
    UTubMemberUserID = UTubMember.id;

    if (UTubMemberUserID === UTubOwnerUserID) {
      $("#UTubOwner").append(
        createOwnerBadge(UTubOwnerUserID, UTubMemberUsername),
      );
    } else {
      parent.append(
        createMemberBadge(
          UTubMemberUserID,
          UTubMemberUsername,
          isCurrentUserOwner,
        ),
      );
    }
  }

  // Subheader prompt
  displayState1MemberDeck(numOfMembers);

  // Ability to add members is restricted to UTub owner
  if (isCurrentUserOwner) {
    hideIfShown($("#memberSelfBtnDelete"));
    showIfHidden($("#memberBtnCreate"));
  } else {
    hideIfShown($("#memberBtnCreate"));
    showIfHidden($("#memberSelfBtnDelete"));
  }
}

// Creates member list item
function createOwnerBadge(UTubOwnerUserID, UTubMemberUsername) {
  const memberSpan = document.createElement("span");

  $(memberSpan)
    .attr({ memberid: UTubOwnerUserID })
    .addClass("member full-width flex-row")
    .html("<b>" + UTubMemberUsername + "</b>");

  return memberSpan;
}

// Creates member list item
function createMemberBadge(
  UTubMemberUserID,
  UTubMemberUsername,
  isCurrentUserOwner,
) {
  const memberSpan = $(document.createElement("span"));

  $(memberSpan)
    .attr({ memberid: UTubMemberUserID })
    .addClass("member full-width flex-row justify-space-between align-center")
    .html("<b>" + UTubMemberUsername + "</b>");

  if (isCurrentUserOwner) {
    const removeIcon = createMemberRemoveIcon();
    removeIcon.off("click.removeMember").on("click.removeMember", function (e) {
      e.stopPropagation();
      removeMemberShowModal(UTubMemberUserID, isCurrentUserOwner);
    });
    $(memberSpan).append(removeIcon);
  } else {
    // Leave UTub if member
    $("#memberSelfBtnDelete")
      .off("click.removeMember")
      .on("click.removeMember", function (e) {
        e.stopPropagation();
        hideInputs();
        deselectAllUrls();
        removeMemberShowModal(getCurrentUserID(), isCurrentUserOwner);
      });
  }

  return memberSpan;
}

// Dynamically generates the remove member icon when needed
function createMemberRemoveIcon() {
  const WIDTH_HEIGHT_PX = "24px";
  const SVG_NS = "http://www.w3.org/2000/svg";
  const removeMemberOuterIconSvg = $(document.createElementNS(SVG_NS, "svg"));
  const removeMemberInnerIconPath = $(document.createElementNS(SVG_NS, "path"));
  const path =
    "M1 14s-1 0-1-1 1-4 6-4 6 3 6 4-1 1-1 1zm5-6a3 3 0 1 0 0-6 3 3 0 0 0 0 6m6.146-2.854a.5.5 0 0 1 .708 0L14 6.293l1.146-1.147a.5.5 0 0 1 .708.708L14.707 7l1.147 1.146a.5.5 0 0 1-.708.708L14 7.707l-1.146 1.147a.5.5 0 0 1-.708-.708L13.293 7l-1.147-1.146a.5.5 0 0 1 0-.708";

  removeMemberInnerIconPath.attr({
    "fill-rule": "evenodd",
    d: path,
  });

  removeMemberOuterIconSvg
    .attr({
      xmlns: SVG_NS,
      width: WIDTH_HEIGHT_PX,
      height: WIDTH_HEIGHT_PX,
      fill: "currentColor",
      class: "bi bi-person-x-fill memberOtherBtnDelete pointerable",
      viewBox: "0 0 16 16",
    })
    .append(removeMemberInnerIconPath);

  return removeMemberOuterIconSvg;
}

/** Member Display State Functions **/

// Display state 0: Clean slate, no UTub selected
function displayState0MemberDeck() {
  resetMemberDeck();

  hideIfShown($("#memberBtnCreate"));
  hideIfShown($("#memberSelfBtnDelete"));

  // Subheader prompt hidden
  hideIfShown($("#MemberDeckSubheader").closest(".titleElement"));
}

// Display state 1: Selected UTub has no Members
function displayState1MemberDeck() {
  showIfHidden($("#memberBtnCreate"));

  let MemberDeckSubheader = $("#MemberDeckSubheader");

  // Subheader prompt shown
  showIfHidden(MemberDeckSubheader.closest(".titleElement"));

  // Count UTub members
  let numOfMembers = $("#listMembers").find("span.member").length + 1; // plus 1 for owner

  if (numOfMembers === 1) {
    MemberDeckSubheader.text("Add a member");
  } else {
    MemberDeckSubheader.text(numOfMembers + " members");
  }
}
