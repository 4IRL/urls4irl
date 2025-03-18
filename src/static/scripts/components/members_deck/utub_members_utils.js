"use strict";

// Streamline the jQuery selector extraction of selected user ID.
function getCurrentUserID() {
  return parseInt($("li.nav-item.user").attr("userID"));
}

// Streamline the jQuery selector extraction of selected UTub creator user ID
function getCurrentUTubOwnerUserID() {
  return parseInt($("#UTubOwner").find("span").attr("memberid"));
}
