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

  // Allow user to attach a query param `next` if browser URL currently includes it
  // This allows for User to be given a link to a UTubID but they haven't logged in recently
  let url = routes.login;
  const searchParams = new URLSearchParams(window.location.search);
  const nextQueryParam = searchParams.get("next");
  if (searchParams.size === 1 && nextQueryParam !== null) {
    url = `${url}?${searchParams.toString()}`;
  }

  const loginRequest = $.ajax({
    url: url,
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
  if (!xhr.hasOwnProperty("responseJSON")) {
    if (
      xhr.status === 403 &&
      xhr.getResponseHeader("Content-Type") === "text/html; charset=utf-8"
    ) {
      $("body").html(xhr.responseText);
      return;
    }
    window.location.assign(routes.errorPage);
    return;
  }

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
  }
}
