// Where el is the DOM element you'd like to test for visibility
function isHidden(el) {
  return el.offsetParent === null;
}

// Checks jqueryObj display status, and shows it if hidden
function showIfHidden(jqueryObj) {
  if (isHidden(jqueryObj[0])) {
    jqueryObj.show();
  }
}

// Checks jqueryObj display status, and hides it if shown
function hideIfShown(jqueryObj) {
  if (!isHidden(jqueryObj[0])) {
    jqueryObj.hide();
  }
}

// AJAX request
function AJAXCall(type, url, data) {
  return (request = $.ajax({
    type: type,
    url: url,
    data: data,
  }));
}

// Rebind Enter key to current function submission
// $(document).on("keyup", function (e) {
//   if (e.keyCode === 13) {
//     e.preventDefault();
//     e.target.blur();
//   }
// });