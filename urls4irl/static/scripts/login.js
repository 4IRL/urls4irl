$(document).ready(function () {
  $(".to-register")
    .off("click")
    .on("click", function () {
      registerModalOpener("/register");
    });

  $(".to-login")
    .off("click")
    .on("click", function () {
      loginModalOpener("/login");
    });

  $(".close-email-modal")
    .off("click")
    .on("click", function () {
      $("#loginRegisterModal").modal("hide");
      logoutUser();
    });

});

function logoutUser() {
  $.get("/logout");
}

function emailValidationModal() {
  $.get("/confirm_email", function (data) {
    $("#loginRegisterModal .modal-content").html(data);
    $("#loginRegisterModal").modal();
    $("#loginRegisterModal").one("hide.bs.modal", function (e) {
      logoutUser();
    })
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
          console.log("Email sent to the user")
        }
      });

      request.fail(function (xhr, textStatus, error) {
        if (xhr.status == 401) {
          handleImproperFormErrors(xhr.responseJSON);
        } else if (xhr.status == 403) {
          // Email invalid
          window.location.replace(xhr.responseJSON.redirect);
        } else if (xhr.status == 429 && xhr.responseJSON.hasOwnProperty("Error_code")) {
          if (xhr.responseJSON.Error_code == 1) {
            showEmailValidationAlert(xhr.responseJSON.Message, "danger")
          }

          if (xhr.responseJSON.Error_code == 2) {
            showEmailValidationAlert(xhr.responseJSON.Message, "warning")
          }
          // Too many attempts
          console.log(xhr.responseJSON.Message)
        } else {
          // TODO: Handle other errors here.
          console.log("You need to handle other errors!");
        }
      });
    });
  })
}

function showEmailValidationAlert(message, category) {
  $("#ValidateEmailMessage").addClass("alert-" + category).css({
    "display": "inherit"
  }).text(message)
}

function loginModalOpener(url) {
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
          $("#loginRegisterModal").modal("hide");
          window.location.replace(response);
        }
      });

      request.fail(function (xhr, textStatus, error) {
        if (xhr.status == 401 && xhr.responseJSON.hasOwnProperty("Error_code")) {
          switch (xhr.responseJSON.Error_code) {
            case 1: {
              // User found but email not yet validated
              handleUserHasAccountNotEmailValidated(xhr.responseJSON.Message)
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
    $("#submit").click(function (event) {
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
        if (xhr.status == 401 && xhr.responseJSON.hasOwnProperty("Error_code")) {
          switch (xhr.responseJSON.Error_code) {
            case 1: {
              // User found but email not yet validated
              handleUserHasAccountNotEmailValidated(xhr.responseJSON.Message)
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

function handleUserHasAccountNotEmailValidated(message) {
  $(".form-control").removeClass("is-invalid");
  $(".invalid-feedback").remove();
  const alertBanner = $("#ValidateEmailMessage");
  alertBanner.addClass("alert-warning").css({
    "display": "flex",
    "flex-direction": "column",
    "align-items": "center",
    "text-align": "center"
  })
    .append($('<div>' + message + '</div>'))
    .append(
      $('<button type="button" class="btn btn-link btn-block">Validate My Email</button>').click(emailValidationModal)
    )

  $(".register-to-login-footer").remove()
  $(".modal-footer").remove()

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
      $(this).remove()
    }
  })
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
