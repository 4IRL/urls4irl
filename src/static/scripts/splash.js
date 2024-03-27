$(document).ready(function () {
  setToRegisterButton();
  setToLoginButton();
});

function setToRegisterButton() {
  $(".to-register")
    .off("click")
    .on("click", function () {
      registerModalOpener();
    });
}

function setToLoginButton() {
  $(".to-login")
    .off("click")
    .on("click", function () {
      loginModalOpener();
    });
}

function loginModalOpener() {
  const modalOpener = $.get("/login");

  modalOpener.done((data, textStatus, xhr) => {
    if (xhr.status === 200) {
      $("#SplashModal .modal-content").html(data);
      bootstrap.Modal.getOrCreateInstance("#SplashModal").show();
    };
  });

  modalOpener.fail(() => {
    bootstrap.Modal.getOrCreateInstance("#SplashErrorModal").show();
    $("#SplashErrorModalAlertBanner").text("Unable to load login form...");
  });
}

function registerModalOpener() {
  const modalOpener = $.get("/register");

  modalOpener.done((data, textStatus, xhr) => {
    if (xhr.status === 200) {
      $("#SplashModal .modal-content").html(data);
      bootstrap.Modal.getOrCreateInstance("#SplashModal").show();
    };
  });

  modalOpener.fail(() => {
    bootstrap.Modal.getOrCreateInstance("#SplashErrorModal").show();
    $("#SplashErrorModalAlertBanner").text("Unable to load register form...");
  });
}


function resetPasswordModalOpener() {
  $.get("/confirm-password-reset", function (data) {
    $("#SplashModal .modal-content").html(data);
    const newModal = new bootstrap.Modal("#SplashModal").show();
    $("#SplashModal")
      .modal()
      .on("hide.bs.modal", function (e) {
        let previouslyClicked = false;
        if (!previouslyClicked) {
          window.location.replace("/");
          previouslyClicked = true;
          $("#SplashModal").off("hide.bs.modal");
        }
      });
    //setCloseModalButton((shouldReplaceWindow = true));

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
          showSplashModalAlertBanner(xhr.responseJSON.Message, "success");
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
    });
  });
}

function handleUserChangedPassword() {
  const submitButton = $("#submit");
  submitButton
    .off("click")
    .prop("type", "button")
    .val("Close")
    .removeClass("btn-success")
    .addClass("btn-warning")
    .on("click", function (e) {
      window.location.replace("/");
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
       '<button type="button" class="btn btn-link btn-block">Validate My Email</button>',
     )
       .off("click")
       .on("click", () => {
          $("#SplashModal").off("hide.bs.modal", logoutOnExit);
          emailValidationModalOpener();
       }),
   );

  $(".register-to-login-footer").remove();
  $(".modal-footer").remove();

  const logoutOnExit = () => { 
    $.get("/logout") 
    $("#SplashModal").off("hide.bs.modal", logoutOnExit);
  };
  $("#SplashModal").on("hide.bs.modal", logoutOnExit);     
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
        // Error for a field that doesn't exist
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
    return (
      className.match(new RegExp("\\S*" + filter + "\\S*", "g")) || []
    ).join(" ");
  });
  return this;
};
