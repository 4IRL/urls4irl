"use strict";

$("#ToRegisterFromLogin").offAndOn("click", () => openRegisterModalFromLogin());

$(".to-forgot-password").offAndOn("click", () => openForgotPasswordModal());

$("#submit").click((event) => handleLogin(event));

function openRegisterModalFromLogin() {
  const modalOpener = $.get(routes.register);

  modalOpener.done((data, _, xhr) => {
    xhr.status === 200 ? $("#SplashModal .modal-content").html(data) : null;
  });

  modalOpener.fail(() => {
    showSplashModalAlertBanner("Unable to load register form...", "danger");
  });
}

function openForgotPasswordModal() {
  const modalOpener = $.get(routes.forgotPassword);

  modalOpener.done((data, _, xhr) => {
    xhr.status === 200 ? $("#SplashModal .modal-content").html(data) : null;
  });

  modalOpener.fail(() => {
    showSplashModalAlertBanner(
      "Unable to load forgot password form...",
      "danger",
    );
  });
}

function handleLogin(event) {
  event.preventDefault();

  const loginRequest = $.ajax({
    url: routes.login,
    type: "POST",
    data: $("#ModalForm").serialize(),
  });

  loginRequest.done((response, textStatus, xhr) =>
    handleLoginSuccess(response, textStatus, xhr),
  );
  loginRequest.fail((xhr, textStatus, error) =>
    handleLoginFailure(xhr, textStatus, error),
  );
}

function handleLoginSuccess(response, _, xhr) {
  if (xhr.status === 200) {
    $("#SplashModal").modal("hide");
    window.location.replace(response);
  }
}

function handleLoginFailure(xhr, _, error) {
  if (
    (xhr.status === 400 || xhr.status === 401) &&
    xhr.responseJSON.hasOwnProperty("errorCode")
  ) {
    switch (xhr.responseJSON.errorCode) {
      case 1: {
        // User found but email not yet validated
        handleUserHasAccountNotEmailValidated(xhr.responseJSON.message);
        $("input").attr("disabled", true);
        break;
      }
      case 2: {
        handleImproperFormErrors(xhr.responseJSON);
        break;
      }
    }
  } else {
    // TODO: Handle other errors here.
    showSplashModalAlertBanner("Unable to process request...", "danger");
    console.log("You need to handle other errors!");
  }
}
