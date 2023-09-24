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
      console.log("User trying to reset their password.")
    });
}

function setCloseEmailModalButton() {
  $(".close-email-modal")
    .off("click")
    .on("click", function () {
      $("#loginRegisterModal").modal("hide");
    });
}

function logoutUser() {
  $.get("/logout");
}

function emailValidationModal(tokenExpired = "") {
  $.get("/confirm_email", function (data) {
    $("#loginRegisterModal .modal-content").html(data);
    $("#loginRegisterModal").modal();
    setCloseEmailModalButton();
    $("#loginRegisterModal").one("hide.bs.modal", function (e) {
      logoutUser();
    });
    if (tokenExpired !== undefined && tokenExpired.length != 0) {
      showEmailRelatedAlertBanner(tokenExpired, "info");
    }
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
          showEmailRelatedAlertBanner(xhr.responseJSON.Message, "success");
        }
      });

      request.fail(function (xhr, textStatus, error) {
        if (
          xhr.status == 429 &&
          xhr.responseJSON.hasOwnProperty("Error_code")
        ) {
          if (xhr.responseJSON.Error_code == 1) {
            showEmailRelatedAlertBanner(xhr.responseJSON.Message, "danger");
          } else if (xhr.responseJSON.Error_code == 2) {
            showEmailRelatedAlertBanner(xhr.responseJSON.Message, "warning");
          }
        } else if (
          xhr.status == 400 &&
          xhr.responseJSON.hasOwnProperty("Error_code")
        ) {
          if (
            xhr.responseJSON.Error_code == 3 ||
            xhr.responseJSON.Error_code == 4
          ) {
            showEmailRelatedAlertBanner(xhr.responseJSON.Message, "warning");
          }
        } else {
          // TODO: Handle other errors here.
          console.log("You need to handle other errors!");
        }
      });
    });
  });
}

function showEmailRelatedAlertBanner(message, category) {
  $("#EmailAlertBanner")
    .removeClass("alert-banner-email-validation-hide")
    .addClass("alert-" + category)
    .css({
      display: "inherit",
    })
    .text(message);
}

function loginModalOpener(url) {
  $.get(url, function (data) {
    $("#loginRegisterModal .modal-content").html(data);
    $("#loginRegisterModal").modal();
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
          $("#loginRegisterModal").modal("hide");
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
    $("#loginRegisterModal .modal-content").html(data);
    $("#loginRegisterModal").modal();
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
    $("#loginRegisterModal .modal-content").html(data);
    $("#loginRegisterModal").modal();
    $("#submit").click(function (event) {
      event.preventDefault();
      let request = $.ajax({
        url: url,
        type: "POST",
        data: $("#ModalForm").serialize(),
      });

      request.done(function (response, textStatus, xhr) {
        if (xhr.status == 200) {
          showEmailRelatedAlertBanner(xhr.responseJSON.Message, "success");
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
  submitButton.prop("type", "button");
  submitButton.click(function (e) {
    if ($(this).hasClass('form-submitted')) {
      e.preventDefault();
      return;
    }
    $(this).addClass('form-submitted');
  });
  submitButton.prop("disabled", true);
}

function handleUserHasAccountNotEmailValidated(message) {
  $(".form-control").removeClass("is-invalid");
  $(".invalid-feedback").remove();
  const alertBanner = $("#EmailAlertBanner");
  alertBanner
    .removeClass("alert-banner-email-validation-hide")
    .addClass("alert-info alert-banner-email-validation-show")
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
      $("#loginRegisterModal").modal("hide");
      logoutUser();
    });
}

function handleImproperFormErrors(errorResponse) {
  $(".invalid-feedback").remove();
  $(".alert").each(function () {
    if ($(this).attr("id") !== "ValidateEmailMessage") {
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
