"use strict";

$(document).ready(function () {
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
      return true;
    },
  });
});

const globalBeforeSend = function (xhr, settings) {
  const csrftoken = $("meta[name=csrf-token]").attr("content");
  if (!/^(GET|HEAD|OPTIONS|TRACE)$/i.test(settings.type) && !this.crossDomain) {
    xhr.setRequestHeader("X-CSRFToken", csrftoken);
  }
};

// AJAX request
function ajaxCall(type, url, data, timeout = 1000) {
  let request;
  return (request = $.ajax({
    type: type,
    url: url,
    data: data,
    timeout: timeout,
  }));
}

// Enable all child elements to be tabbable
function enableTabbableChildElements(parent) {
  $(parent).find(".tabbable").enableTab();
}

function disableTabbableChildElements(parent) {
  $(parent).find(".tabbable").disableTab();
}

// jQuery plugins
(function ($) {
  $.fn.enableTab = function () {
    this.attr({ tabindex: 0 });
    return this;
  };

  $.fn.disableTab = function () {
    this.attr({ tabindex: -1 });
    return this;
  };

  $.fn.offAndOn = function (eventName, callback) {
    this.off(eventName).on(eventName, callback);
    return this;
  };

  $.fn.removeClassStartingWith = function (filter) {
    $(this).removeClass(function (_, className) {
      return (
        className.match(new RegExp("\\S*" + filter + "\\S*", "g")) || []
      ).join(" ");
    });
    return this;
  };

  $.fn.showClassNormal = function () {
    this.removeClass("hidden").addClass("visible");
    return this;
  };

  $.fn.showClassFlex = function () {
    this.removeClassStartingWith("hidden").addClass("visible-flex");
    return this;
  };

  $.fn.hideClass = function () {
    this.removeClassStartingWith("visible").addClass("hidden");
    return this;
  };
})(jQuery);
