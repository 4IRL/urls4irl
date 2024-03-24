 
$("#submit").click((event) => handleForgotPassword(event));

function handleForgotPassword(event) {
  event.preventDefault();
  $("#submit").attr("disabled", "disabled");

  const forgotPasswordRequest = $.ajax({
    url: "/forgot-password",
    type: "POST",
    data: $("#ModalForm").serialize(),
  });

  forgotPasswordRequest.done((response, textStatus, xhr) =>
    handleForgotPasswordSuccess(response, textStatus, xhr),
  );
  forgotPasswordRequest.fail((xhr, textStatus, error) =>
    handleForgotPasswordFailure(xhr, textStatus, error),
  );
}

function handleForgotPasswordSuccess(response, textStatus, xhr) {
  if (xhr.status === 200) {
    $(".form-control").removeClass("is-invalid");
    $(".invalid-feedback").remove();
    showSplashModalAlertBanner(xhr.responseJSON.Message, "success");
    disableSendPasswordResetEmailButton();
  }
}

function disableSendPasswordResetEmailButton() {
  const submitButton = $("#submit");
  submitButton
    .prop("type", "button")
    .off("click")
    .prop("disabled", true)
    .on("click", function (e) {
      submitButton.prop("disabled", true);
    });
}

function handleForgotPasswordFailure(xhr, textStatus, error) {
  if (
    xhr.status === 401 &&
    xhr.responseJSON.hasOwnProperty("Error_code")
  ) {
    switch (xhr.responseJSON.Error_code) {
      case 1: {
        handleImproperFormErrors(xhr.responseJSON);
        $("#submit").removeAttr("disabled");
      }
    }
  } else {
    // TODO: Handle other errors here.
    console.log("You need to handle other errors!");
  }
}
