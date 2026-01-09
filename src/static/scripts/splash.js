"use strict";

$(document).ready(function () {
  setToRegisterButton();
  setToLoginButton();

  $.ajaxPrefilter(function (options, originalOptions, jqXHR) {
    let originalError = options.error;

    options.error = function (jqXHR, textStatus, errorThrown) {
      if (jqXHR.status === 429) {
        showNewPageOnAJAXHTMLResponse(jqXHR.responseText);
        return; // Prevents both .error and .fail() from being called
      }

      if (originalError) {
        originalError.call(this, jqXHR, textStatus, errorThrown);
      }
    };
  });
});

function setToRegisterButton() {
  $(".to-register").offAndOn("click", function () {
    registerModalOpener();
    NAVBAR_TOGGLER.toggler.hide();
  });
}

function setToLoginButton() {
  $(".to-login").offAndOn("click", function () {
    loginModalOpener();
    NAVBAR_TOGGLER.toggler.hide();
  });
}

function loginModalOpener() {
  const modalOpener = $.get(APP_CONFIG.routes.login);

  modalOpener.done((data, _, xhr) => {
    if (xhr.status === 200) {
      $("#SplashModal .modal-content").html(data);
      bootstrap.Modal.getOrCreateInstance("#SplashModal").show();
    }
  });

  modalOpener.fail((xhr) => {
    bootstrap.Modal.getOrCreateInstance("#SplashErrorModal").show();
    $("#SplashErrorModalAlertBanner").text("Unable to load login form...");
  });
}

function loginModalOpenerFromModal() {
  const modalOpener = $.get(APP_CONFIG.routes.login);

  modalOpener.done((data, _, xhr) => {
    xhr.status === 200 ? $("#SplashModal .modal-content").html(data) : null;
  });

  modalOpener.fail((xhr) => {
    bootstrap.Modal.getOrCreateInstance("#SplashErrorModal").show();
    $("#SplashErrorModalAlertBanner").text("Unable to load login form...");
  });
}

function registerModalOpener() {
  const modalOpener = $.get(APP_CONFIG.routes.register);

  modalOpener.done((data, _, xhr) => {
    if (xhr.status === 200) {
      $("#SplashModal .modal-content").html(data);
      bootstrap.Modal.getOrCreateInstance("#SplashModal").show();
    }
  });

  modalOpener.fail((xhr) => {
    bootstrap.Modal.getOrCreateInstance("#SplashErrorModal").show();
    $("#SplashErrorModalAlertBanner").text("Unable to load register form...");
  });
}

function hideSplashModalAlertBanner() {
  $("#SplashModalAlertBanner")
    .removeClass("alert-banner-splash-modal-display")
    .removeClassStartingWith("alert-")
    .addClass("alert-banner-splash-modal-hide");
}

function showSplashModalAlertBanner(message, category) {
  $("#SplashModalAlertBanner")
    .removeClass("alert-banner-splash-modal-hide")
    .removeClassStartingWith("alert-")
    .addClass("alert-" + category)
    .addClass("alert-banner-splash-modal-display")
    .text(message);
}

function disableInputFields() {
  $("input").attr("disabled", true);
}

function handleUserHasAccountNotEmailValidated(message) {
  $(".form-control").removeClass("is-invalid");
  $(".invalid-feedback").remove();
  $(".to-forgot-password").remove();
  const alertBanner = $("#SplashModalAlertBanner");
  alertBanner
    .removeClass("alert-banner-splash-modal-hide")
    .addClass("alert-info alert-banner-splash-modal-show")
    .append($("<div>" + message + "</div>"))
    .append(
      $(
        `<button type="button" class="btn btn-link btn-block">${APP_CONFIG.strings.VALIDATE_MY_EMAIL}</button>`,
      ).offAndOn("click", () => {
        $("#SplashModal").off("hide.bs.modal", logoutOnExit);
        emailValidationModalOpener();
      }),
    );

  $(".register-to-login-footer").remove();
  $(".modal-footer").remove();

  const logoutOnExit = () => {
    $.get(APP_CONFIG.routes.logout);
    $("#SplashModal").off("hide.bs.modal", logoutOnExit);
  };
  $("#SplashModal").on("hide.bs.modal", logoutOnExit);
}

function emailValidationModalOpener() {
  const modalOpener = $.get(APP_CONFIG.routes.confirmEmailAfterRegister);

  modalOpener.done((data, _, xhr) => {
    xhr.status === 200 ? $("#SplashModal .modal-content").html(data) : null;
  });

  modalOpener.fail((xhr) => {
    showSplashModalAlertBanner(
      "Unable to load email validation modal...",
      "danger",
    );
  });
  modalOpener.fail(() => {});
}

function handleImproperFormErrors(errorResponse) {
  $(".invalid-feedback").remove();
  $(".alert").each(function () {
    if ($(this).attr("id") !== "SplashModalAlertBanner") {
      $(this).remove();
    }
  });
  $(".form-control").removeClass("is-invalid");
  for (let key in errorResponse.errors) {
    switch (key) {
      case "username":
      case "password":
      case "email":
      case "confirmEmail":
      case "confirmPassword":
      case "newPassword":
      case "confirmNewPassword":
        let errorMessage = errorResponse.errors[key][0];
        displayFormErrors(key, errorMessage);
        break;
      default:
        // Error for a field that doesn't exist
        console.log("No op.");
    }
  }
}

const NAVBAR_TOGGLER = { toggler: null };

$(document).ready(function () {
  // Grab toggler for the navbar
  NAVBAR_TOGGLER.toggler = new bootstrap.Collapse("#NavbarNavDropdown", {
    toggle: false,
  });

  // Event listeners when hiding and showing the mobile navbar
  $("#NavbarNavDropdown")
    .on("show.bs.collapse", () => {
      onMobileNavbarOpened();
    })
    .on("hide.bs.collapse", () => {
      onMobileNavbarClosed();
    });
});

function onMobileNavbarOpened() {
  const navbarBackdrop = $(document.createElement("div")).addClass(
    "navbar-backdrop",
  );

  navbarBackdrop.on("click", function () {
    NAVBAR_TOGGLER.toggler.hide();
  });

  setTimeout(function () {
    navbarBackdrop.addClass("navbar-backdrop-show");
  }, 0);

  $(".navbar-brand").addClass("z9999");
  $(".navbar-toggler").addClass("z9999");
  $("#NavbarNavDropdown").addClass("z9999");

  $("#mainNavbar").append(navbarBackdrop);
}

function onMobileNavbarClosed() {
  const navbarBackdrop = $(".navbar-backdrop");
  navbarBackdrop.addClass("navbar-backdrop-fade");

  setTimeout(function () {
    navbarBackdrop.remove();
  }, 300);

  $(".navbar-brand").removeClass("z9999");
  $(".navbar-toggler").removeClass("z9999");
  $("#NavbarNavDropdown").removeClass("z9999");
}

function displayFormErrors(key, errorMessage) {
  $('<div class="invalid-feedback"><span>' + errorMessage + "</span></div>")
    .insertAfter("#" + key)
    .show();
  $("#" + key).addClass("is-invalid");
}

function showNewPageOnAJAXHTMLResponse(htmlText) {
  $("body").fadeOut(150, function () {
    document.open();
    document.write(htmlText);
    document.close();

    // Hide body initially
    document.body.style.opacity = "0";

    // Wait for everything to load
    window.addEventListener("load", function () {
      $("body").css("opacity", "1").hide().fadeIn(150);
    });
  });
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

  // Extension to allow removal of a class based on a prefix
  $.fn.removeClassStartingWith = function (filter) {
    $(this).removeClass(function (_, className) {
      return (
        className.match(new RegExp("\\S*" + filter + "\\S*", "g")) || []
      ).join(" ");
    });
    return this;
  };
})(jQuery);
