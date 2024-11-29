"use strict";

$("#ToLoginFromRegister").offAndOn("click", function () {
  loginModalOpener();
});

$("#submit").click((event) => handleRegister(event));

function handleRegister(event) {
  event.preventDefault();
  $("#submit").attr("disabled", "disabled");

  const registerRequest = $.ajax({
    url: routes.register,
    type: "POST",
    data: $("#ModalForm").serialize(),
  });

  registerRequest.done((response, textStatus, xhr) =>
    handleRegisterSuccess(response, textStatus, xhr),
  );
  registerRequest.fail((xhr, textStatus, error) =>
    handleRegisterFailure(xhr, textStatus, error),
  );
}

function handleRegisterSuccess(response, _, xhr) {
  if (xhr.status === 201) {
    $("#SplashModal .modal-content").html(response);
  }
}

function handleRegisterFailure(xhr, _, error) {
  if (xhr.responseJSON.hasOwnProperty("errorCode")) {
    switch (xhr.status) {
      case 400: {
        handleImproperFormErrors(xhr.responseJSON);
        $("#submit").removeAttr("disabled");
        break;
      }
      case 401: {
        // User found but email not yet validated
        handleUserHasAccountNotEmailValidated(xhr.responseJSON.message);
        $("input").attr("disabled", true);
        break;
      }
    }
  } else {
    // TODO: Handle other errors here.
    showSplashModalAlertBanner("Unable to process request...", "danger");
  }
}
