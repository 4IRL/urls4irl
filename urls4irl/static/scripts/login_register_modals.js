function modalOpener(url) {
  $.get(url, function (data) {
    $("#Modal .modal-content").html(data);
    $("#Modal").modal();
    $("#submit").click(function (event) {
      event.preventDefault();
      $.ajax({
        url: url,
        type: "POST",
        data: $("#ModalForm").serialize(),
        statusCode: {
          200: function (response) {
            $("#Modal").modal("hide");
            window.location = response;
          },
          422: function (response) {
            var obj = JSON.parse(response.responseJSON);
            $(".invalid-feedback").remove();
            $(".alert").remove();
            $(".form-control").removeClass("is-invalid");
            for (var key in obj) {
              switch (key) {
                case "username":
                case "password":
                case "email":
                case "confirm_email":
                case "confirm_password":
                  var value = obj[key];
                  $(
                    '<div class="invalid-feedback"><span>' +
                      value +
                      "</span></div>",
                  )
                    .insertAfter("#" + key)
                    .show();
                  $("#" + key).addClass("is-invalid");
                  break;
                default:
                  const flash_message = obj.flash.flash_message;
                  const flash_category = obj.flash.flash_category;
                  $(
                    '<div class="alert alert-' +
                      flash_category +
                      ' alert-dismissible fade show" role="alert">' +
                      flash_message +
                      '<button type="button" class="close" data-dismiss="alert" aria-label="Close"><span aria-hidden="false">&times;</span></button></div>',
                  )
                    .insertBefore("#modal-body")
                    .show();
                  $(".alert-" + flash_category).css("margin-bottom", "0rem");
              }
            }
          },
        },
      });
    });
  });
}

$(document).ready(function () {
  $(".to_register").click(function () {
    modalOpener("/register");
  });

  $(".to_login").click(function () {
    modalOpener("/login");
  });
  $(".edit-modal-opener").click(function () {
    var url = $(this).data("for-modal");
    modalOpener(url);
  });
});
