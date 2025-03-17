"use strict";

// Function to count number of URLs in current UTub
function getNumOfURLs() {
  return $(".urlRow").length;
}

// Function to count number of visible URLs in current UTub, after filtering
function getNumOfVisibleURLs() {
  return $(".urlRow[filterable=true]").length;
}
