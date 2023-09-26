$(document).ready(function () {
  setToRegisterButton();
  setToLoginButton();
});

function setToRegisterButton() {
  $(".to-register")
    .off("click")
    .on("click", function () {
      registerModalOpener("/register");
    });
}

function setToLoginButton() {
  $(".to-login")
    .off("click")
    .on("click", function () {
      loginModalOpener("/login");
    });
}

function setForgotPasswordButton() {
  $(".to-forgot-password")
    .off("click")
    .on("click", function () {
      forgotPasswordModalOpener("/forgot_password");
    });
}

function setCloseModalButton(shouldLogout = false, shouldReplaceWindow = false) {
  $(".close-modal")
    .off("click")
    .on("click", function () {
      $("#SplashModal").modal("hide");
      if (shouldLogout) {
        logoutUser();
      };
      if (shouldReplaceWindow) {
        window.location.replace("/");
      }
    });
}

function logoutUser() {
  $.get("/logout");
}

function resetPasswordModal() {
  $.get("/confirm_password_reset", function (data) {
    $("#SplashModal .modal-content").html(data);
    $("#SplashModal").modal()
      .on("hide.bs.modal", function (e) {
        let previouslyClicked = false;
        if (!previouslyClicked) {
          window.location.replace("/");
          previouslyClicked = true;
          $("#SplashModal").off("hide.bs.modal");
        }
      });
    setCloseModalButton(shouldReplaceWindow = true);

    $("#submit").click(function (event) {
      event.preventDefault();
      let request = $.ajax({
        url: window.location.pathname,
        type: "POST",
        data: $("#ModalForm").serialize(),
      });

      request.done(function (response, textStatus, xhr) {
        if (xhr.status == 200) {
          // Password changed!
          hideSplashModalAlertBanner();
          showSplashModalAlertBanner(xhr.responseJSON.Message, "success")
          handleUserChangedPassword();
        }
      });

      request.fail(function (xhr, textStatus, error) {
        if (
          xhr.status == 400 &&
          xhr.responseJSON.hasOwnProperty("Error_code")
        ) {
          switch (xhr.responseJSON.Error_code) {
            case 1:
              $(".form-control").removeClass("is-invalid");
              $(".invalid-feedback").remove();
              showSplashModalAlertBanner(xhr.responseJSON.Message, "warning");
              break;
            case 2:
              hideSplashModalAlertBanner();
              handleImproperFormErrors(xhr.responseJSON);
              break;
          }
        } else {
          // TODO: Handle other errors here.
          console.log("You need to handle other errors!");
        }
      });
    })
  })
}

function handleUserChangedPassword() {
  const submitButton = $("#submit");
  submitButton.off("click")
    .prop("type", "button")
    .val("Close")
    .removeClass("btn-success")
    .addClass("btn-warning")
    .on("click", function (e) {
      window.location.replace("/");
    })
}

function emailValidationModal(tokenExpired = "") {
  $.get("/confirm_email", function (data) {
    $("#SplashModal .modal-content").html(data);
    $("#SplashModal").modal()
      .on("hide.bs.modal", function (e) {
        let previouslyClicked = false;
        if (!previouslyClicked) {
          logoutUser();
          previouslyClicked = true;
          $("#SplashModal").off("hide.bs.modal");
        }
      });
    setCloseModalButton(true);
    if (tokenExpired !== undefined && tokenExpired.length != 0) {
      showSplashModalAlertBanner(tokenExpired, "info");
    };
    $("#submit").click(function (event) {
      event.preventDefault();
      let request = $.ajax({
        url: "/send_validation_email",
        type: "POST",
        data: $("#ModalForm").serialize(),
      });

      request.done(function (response, textStatus, xhr) {
        if (xhr.status == 200) {
          // Email sent!
          showSplashModalAlertBanner(xhr.responseJSON.Message, "success");
        }
      });

      request.fail(function (xhr, textStatus, error) {
        if (
          xhr.status == 429 &&
          xhr.responseJSON.hasOwnProperty("Error_code")
        ) {
          switch (xhr.responseJSON.Error_code) {
            case 1:
              showSplashModalAlertBanner(xhr.responseJSON.Message, "danger");
              break;
            case 2:
              showSplashModalAlertBanner(xhr.responseJSON.Message, "warning");
              break;
          }
        } else if (
          xhr.status == 400 &&
          xhr.responseJSON.hasOwnProperty("Error_code")
        ) {
          if (
            xhr.responseJSON.Error_code == 3 ||
            xhr.responseJSON.Error_code == 4
          ) {
            showSplashModalAlertBanner(xhr.responseJSON.Message, "warning");
          }
        } else {
          // TODO: Handle other errors here.
          console.log("You need to handle other errors!");
        }
      });
    });
  });
}

function hideSplashModalAlertBanner() {
  $("#SplashModalAlertBanner")
    .removeClass("alert-banner-splash-modal-display")
    .removeClassStartingWith("alert-")
    .addClass("alert-banner-splash-modal-hide")
}

function showSplashModalAlertBanner(message, category) {
  $("#SplashModalAlertBanner")
    .removeClass("alert-banner-splash-modal-hide")
    .addClass("alert-" + category)
    .addClass("alert-banner-splash-modal-display")
    .text(message);
}

function loginModalOpener(url) {
  $.get(url, function (data) {
    $("#SplashModal .modal-content").html(data);
    $("#SplashModal").modal();
    setToRegisterButton();
    setForgotPasswordButton();
    $("#submit").click(function (event) {
      event.preventDefault();
      let request = $.ajax({
        url: url,
        type: "POST",
        data: $("#ModalForm").serialize(),
      });

      request.done(function (response, textStatus, xhr) {
        if (xhr.status == 200) {
          $("#SplashModal").modal("hide");
          window.location.replace(response);
        }
      });

      request.fail(function (xhr, textStatus, error) {
        if (
          xhr.status == 401 &&
          xhr.responseJSON.hasOwnProperty("Error_code")
        ) {
          switch (xhr.responseJSON.Error_code) {
            case 1: {
              // User found but email not yet validated
              handleUserHasAccountNotEmailValidated(xhr.responseJSON.Message);
              break;
            }
            case 2: {
              handleImproperFormErrors(xhr.responseJSON);
              break;
            }
          }
        } else {
          // TODO: Handle other errors here.
          console.log("You need to handle other errors!");
        }
      });
    });
  });
}

function registerModalOpener(url) {
  $.get(url, function (data) {
    $("#SplashModal .modal-content").html(data);
    $("#SplashModal").modal();
    setToLoginButton();
    const registerButton = $("#submit");
    registerButton.click(function (event) {
      registerButton.attr("disabled", "disabled");
      event.preventDefault();
      let request = $.ajax({
        url: url,
        type: "POST",
        data: $("#ModalForm").serialize(),
      });

      request.done(function (response, textStatus, xhr) {
        if (xhr.status == 201) {
          emailValidationModal();
        }
      });

      request.fail(function (xhr, textStatus, error) {
        if (
          xhr.status == 401 &&
          xhr.responseJSON.hasOwnProperty("Error_code")
        ) {
          switch (xhr.responseJSON.Error_code) {
            case 1: {
              // User found but email not yet validated
              handleUserHasAccountNotEmailValidated(xhr.responseJSON.Message);
              break;
            }
            case 2: {
              handleImproperFormErrors(xhr.responseJSON);
              registerButton.removeAttr("disabled");
              break;
            }
          }
        } else {
          // TODO: Handle other errors here.
          console.log("You need to handle other errors!");
        }
      });
    });
  });
}

function forgotPasswordModalOpener(url) {
  $.get(url, function (data) {
    $("#SplashModal .modal-content").html(data);
    $("#SplashModal").modal();
    $("#submit").click(function (event) {
      event.preventDefault();
      let request = $.ajax({
        url: url,
        type: "POST",
        data: $("#ModalForm").serialize(),
      });

      request.done(function (response, textStatus, xhr) {
        if (xhr.status == 200) {
          $(".form-control").removeClass("is-invalid");
          $(".invalid-feedback").remove();
          showSplashModalAlertBanner(xhr.responseJSON.Message, "success");
          disableSendPasswordResetEmailButton();
        }
      });

      request.fail(function (xhr, textStatus, error) {
        if (
          xhr.status == 401 &&
          xhr.responseJSON.hasOwnProperty("Error_code")
        ) {
          switch (xhr.responseJSON.Error_code) {
            case 1: {
              handleImproperFormErrors(xhr.responseJSON);
            }
          }
        } else {
          // TODO: Handle other errors here.
          console.log("You need to handle other errors!");
        }
      });
    });
  });
}

function disableSendPasswordResetEmailButton() {
  const submitButton = $("#submit");
  submitButton.prop("type", "button")
    .off("click")
    .prop("disabled", true)
    .on("click", function (e) {
      submitButton.prop("disabled", true);
    });
}

function handleUserHasAccountNotEmailValidated(message) {
  $(".form-control").removeClass("is-invalid");
  $(".invalid-feedback").remove();
  const alertBanner = $("#SplashModalAlertBanner");
  alertBanner.removeClass("alert-banner-splash-modal-hide")
    .addClass("alert-info alert-banner-splash-modal-show")
    .append($("<div>" + message + "</div>"))
    .append(
      $(
        '<button type="button" class="btn btn-link btn-block">Validate My Email</button>',
      )
        .off("click")
        .on("click", function () {
          emailValidationModal();
        }),
    );

  $(".register-to-login-footer").remove();
  $(".modal-footer").remove();

  $(".close-register-login-modal")
    .off("click")
    .on("click", function () {
      $("#SplashModal").modal("hide");
      logoutUser();
    });
}

function handleImproperFormErrors(errorResponse) {
  $(".invalid-feedback").remove();
  $(".alert").each(function () {
    if ($(this).attr("id") !== "SplashModalAlertBanner") {
      $(this).remove();
    }
  });
  $(".form-control").removeClass("is-invalid");
  for (let key in errorResponse.Errors) {
    switch (key) {
      case "username":
      case "password":
      case "email":
      case "confirm_email":
      case "confirm_password":
      case "new_password":
      case "confirm_new_password":
        let errorMessage = errorResponse.Errors[key][0];
        displayFormErrors(key, errorMessage);
        break;
      default:
        // Error for a field that doens't exist
        console.log("No op.");
    }
  }
}

function displayFormErrors(key, errorMessage) {
  $('<div class="invalid-feedback"><span>' + errorMessage + "</span></div>")
    .insertAfter("#" + key)
    .show();
  $("#" + key).addClass("is-invalid");
}

// Extension to allow removal of a class based on a prefix
$.fn.removeClassStartingWith = function (filter) {
  $(this).removeClass(function (index, className) {
    return (className.match(new RegExp("\\S*" + filter + "\\S*", 'g')) || []).join(' ')
  });
  return this;
};
