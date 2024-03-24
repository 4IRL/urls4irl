
$(".to-register").off("click")
    .on("click", () => openRegisterModal())

$(".to-forgot-password").off("click")
    .on("click", () => forgotPasswordModal())

$("#submit").click((event) => handleLogin(event));

function openRegisterModal() {
    $.get("/register", (data) => {
        $("#SplashModal .modal-content").html(data);
    })
}

function forgotPasswordModal() {
    $.get("/forgot-password", (data) => {
        $("#SplashModal .modal-content").html(data);
    })
}

function handleLogin(event) {
    event.preventDefault();
    console.log("Handling login")

    const loginRequest = $.ajax({
        url: "/login",
        type: "POST",
        data: $("#ModalForm").serialize(),
    });

    loginRequest.done( (response, textStatus, xhr) => handleLoginSuccess(response, textStatus, xhr));
    loginRequest.fail( (xhr, textStatus, error) => handleLoginFailure(xhr, textStatus, error));
}

function handleLoginSuccess(response, _, xhr) {
    if (xhr.status === 200) {
        $("#SplashModal").modal("hide");
        window.location.replace(response);
    }
}

function handleLoginFailure(xhr, textStatus, error) {
    if (
        xhr.status == 401 &&
        xhr.responseJSON.hasOwnProperty("Error_code")
    ) {
        switch (xhr.responseJSON.Error_code) {
        case 1: {
            // User found but email not yet validated
            handleUserHasAccountNotEmailValidated(xhr.responseJSON.Message);
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
        console.log("You need to handle other errors!");
    }
}

function handleUserHasAccountNotEmailValidated(message) {
  $(".form-control").removeClass("is-invalid");
  $(".invalid-feedback").remove();
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
        .on("click", function () {
          emailValidationModalOpener();
        }),
    );

  $(".register-to-login-footer").remove();
  $(".modal-footer").remove();
  $("#ForgotPasswordLink").remove();

  $(".close-register-login-modal")
    .off("click")
    .on("click", function () {
      $("#SplashModal").modal("hide");
      $.get("/logout");
    });
}
