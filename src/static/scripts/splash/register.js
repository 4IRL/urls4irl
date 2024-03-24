
$(".to-login")
  .off("click")
  .on("click", function () {
    loginModalOpenerFromRegister();
  });

$("#submit").click((event) => handleRegister(event));

function loginModalOpenerFromRegister() {
  const modalOpener = $.get("/login");
  const splashModal = $("#SplashModal .modal-content");

  modalOpener.done((data, textStatus, xhr) => {
    xhr.status === 200 ? $("#SplashModal .modal-content").html(data) : null;
  });

  modalOpener.fail(() => {
    showSplashModalAlertBanner("Unable to load login form...", "danger");
  });
}

function handleRegister(event) {
  event.preventDefault();
  $("#submit").attr("disabled", "disabled");

  const registerRequest = $.ajax({
    url: "/register",
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

function handleRegisterSuccess(response, textStatus, xhr) {
  if (xhr.status === 201) {
    emailValidationModalOpener();
  }
}

function emailValidationModalOpener() {
  const modalOpener = $.get("/confirm-email");
  const splashModal = $("#SplashModal .modal-content");

  modalOpener.done((data, textStatus, xhr) => {
    xhr.status === 200 ? $("#SplashModal .modal-content").html(data) : null;
  });

  modalOpener.fail(() => {
    showSplashModalAlertBanner("Unable to load email validation modal...", "danger");
  });
}

function handleRegisterFailure(xhr, textStatus, error) {
    if (xhr.responseJSON.hasOwnProperty("Error_code")) {
      switch (xhr.status) {
        case 400: {
          handleImproperFormErrors(xhr.responseJSON);
          $("#submit").removeAttr("disabled");
          break;
        }
        case 401: {
          // User found but email not yet validated
          handleUserHasAccountNotEmailValidated(xhr.responseJSON.Message);
          $("input").attr("disabled", true);
          break;
        }
      }
    } else {
      // TODO: Handle other errors here.
      console.log("You need to handle other errors!");
    }
}

