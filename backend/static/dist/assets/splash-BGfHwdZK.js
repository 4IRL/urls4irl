import "./security-check-2tLiMbrB.js";
import { i as M, b as i, $ as o, A as r } from "./navbar-shared-gG1g8UXG.js";
import { s as p, r as C, a as P, i as A } from "./cookie-banner-XonZzaY2.js";
const u = { toggler: null };
function N() {
  M(),
    (u.toggler = new i.Collapse("#NavbarNavDropdown", { toggle: !1 })),
    o("#NavbarNavDropdown")
      .on("show.bs.collapse", () => {
        k();
      })
      .on("hide.bs.collapse", () => {
        E();
      });
}
function k() {
  const e = o(document.createElement("div")).addClass("navbar-backdrop");
  e.on("click", function () {
    u.toggler.hide();
  }),
    setTimeout(function () {
      e.addClass("navbar-backdrop-show");
    }, 0),
    o(".navbar-brand").addClass("z9999"),
    o(".navbar-toggler").addClass("z9999"),
    o("#NavbarNavDropdown").addClass("z9999"),
    o("#mainNavbar").append(e);
}
function E() {
  const e = o(".navbar-backdrop");
  e.addClass("navbar-backdrop-fade"),
    setTimeout(function () {
      e.remove();
    }, 300),
    o(".navbar-brand").removeClass("z9999"),
    o(".navbar-toggler").removeClass("z9999"),
    o("#NavbarNavDropdown").removeClass("z9999");
}
function _() {
  o("#ToLoginFromForgotPassword").offAndOn("click", function () {
    w();
  }),
    o("#submit").offAndOn("click", (e) => F(e));
}
function F(e) {
  e.preventDefault(), o("#submit").attr("disabled", "disabled");
  const a = o.ajax({
    url: r.routes.forgotPassword,
    type: "POST",
    data: o("#ModalForm").serialize(),
  });
  a.done((s, t, n) => T(s, t, n)), a.fail((s, t, n) => y(s));
}
function T(e, a, s) {
  s.status === 200 &&
    (o(".form-control").removeClass("is-invalid"),
    o(".invalid-feedback").remove(),
    l(s.responseJSON.message, "success"),
    R());
}
function R() {
  const e = o("#submit");
  e.prop("type", "button")
    .prop("disabled", !0)
    .offAndOn("click", function (a) {
      e.prop("disabled", !0);
    });
}
function y(e, a, s) {
  if (!e.hasOwnProperty("responseJSON")) {
    if (
      e.getResponseHeader("Content-Type") === "text/html; charset=utf-8" &&
      e.status === 403
    ) {
      o("body").html(e.responseText);
      return;
    }
    window.location.assign(r.routes.errorPage);
    return;
  }
  e.status === 401 && e.responseJSON.hasOwnProperty("errorCode")
    ? e.responseJSON.errorCode === 1 &&
      (f(e.responseJSON), o("#submit").removeAttr("disabled"))
    : console.log("You need to handle other errors!");
}
function b() {
  o("#ToRegisterFromLogin").offAndOn("click", () => S()),
    o(".to-forgot-password").offAndOn("click", () => J()),
    o("#submit").offAndOn("click", (e) => I(e));
}
function J() {
  const e = o.get(r.routes.forgotPassword);
  e.done((a, s, t) => {
    t.status === 200 && (o("#SplashModal .modal-content").html(a), _());
  }),
    e.fail((a) => {
      l("Unable to load forgot password form...", "danger");
    });
}
function I(e) {
  e.preventDefault();
  let a = r.routes.login;
  const s = new URLSearchParams(window.location.search),
    t = s.get("next");
  s.size === 1 && t !== null && (a = `${a}?${s.toString()}`);
  const n = o.ajax({ url: a, type: "POST", data: o("#ModalForm").serialize() });
  n.done((d, c, g) => L(d, c, g)), n.fail((d, c, g) => B(d));
}
function L(e, a, s) {
  if (s.status === 200) {
    i.Modal.getOrCreateInstance("#SplashModal").hide();
    const t = e.redirect_url || r.routes.home;
    window.location.replace(t);
  }
}
function B(e, a, s) {
  if (!e.hasOwnProperty("responseJSON")) {
    if (e.getResponseHeader("Content-Type") === "text/html; charset=utf-8")
      switch (e.status) {
        case 403:
        case 429: {
          p(e.responseText);
          return;
        }
      }
    window.location.assign(r.routes.errorPage);
    return;
  }
  if (
    (e.status === 400 || e.status === 401) &&
    e.responseJSON.hasOwnProperty("errorCode")
  )
    switch (e.responseJSON.errorCode) {
      case 1: {
        v(e.responseJSON.message), o("input").attr("disabled", !0);
        break;
      }
      case 2: {
        f(e.responseJSON);
        break;
      }
    }
  else l("Unable to process request...", "danger");
}
function m(e = !1) {
  o("#submit").offAndOn("click", (a) => h(a)),
    o("#SplashModal").on("hide.bs.modal", function (a) {
      o("#SplashModal").off("hide.bs.modal"),
        new URLSearchParams(window.location.search).has("token")
          ? window.location.replace(r.routes.logout)
          : o.get(r.routes.logout);
    }),
    e && h();
}
function h(e = null) {
  e !== null && e.preventDefault();
  const a = o.ajax({
    url: r.routes.sendValidationEmail,
    type: "POST",
    data: o("#ModalForm").serialize(),
  });
  a.done((s, t, n) => U(s, t, n)), a.fail((s, t, n) => D(s));
}
function U(e, a, s) {
  s.status === 200 && l(s.responseJSON.message, "success");
}
function D(e, a, s) {
  if (e.status !== 400 && e.status !== 429) {
    window.location.assign(r.routes.errorPage);
    return;
  }
  if (!e.hasOwnProperty("responseJSON")) {
    window.location.assign(r.routes.errorPage);
    return;
  }
  if (!e.responseJSON.hasOwnProperty("errorCode")) {
    l("Unable to process request...", "danger");
    return;
  }
  const t = r.constants.VALIDATE_EMAIL_ERROR_CODES;
  switch (e.responseJSON.errorCode) {
    case t.MAX_TOTAL_EMAIL_VALIDATION_ATTEMPTS:
      l(e.responseJSON.message, "danger");
      break;
    case t.MAX_TIME_EMAIL_VALIDATION_ATTEMPTS:
    case t.EMAIL_SEND_FAILURE:
    case t.MAILJET_SERVER_FAILURE:
      l(e.responseJSON.message, "warning");
      break;
    default:
      window.location.assign(r.routes.errorPage);
  }
}
function V() {
  o("#ToLoginFromRegister").offAndOn("click", function () {
    w();
  }),
    o("#submit").offAndOn("click", (e) => z(e));
}
function z(e) {
  e.preventDefault(), o("#submit").attr("disabled", "disabled");
  const a = o.ajax({
    url: r.routes.register,
    type: "POST",
    data: o("#ModalForm").serialize(),
  });
  a.done((s, t, n) => q(s, t, n)), a.fail((s, t, n) => j(s));
}
function q(e, a, s) {
  s.status === 201 && (o("#SplashModal .modal-content").html(e), m(!0));
}
function j(e, a, s) {
  if (!e.hasOwnProperty("responseJSON")) {
    if (e.getResponseHeader("Content-Type") === "text/html; charset=utf-8")
      switch (e.status) {
        case 403:
        case 429: {
          p(e.responseText);
          return;
        }
      }
    window.location.assign(r.routes.errorPage);
    return;
  }
  if (e.responseJSON.hasOwnProperty("errorCode"))
    switch (e.status) {
      case 400: {
        f(e.responseJSON), o("#submit").removeAttr("disabled");
        break;
      }
      case 401: {
        v(e.responseJSON.message), o("input").attr("disabled", !0);
        break;
      }
    }
  else l("Unable to process request...", "danger");
}
function H() {
  o("#submit").offAndOn("click", (e) => $(e)),
    o("#SplashModal").on("hide.bs.modal", function (e) {
      o("#SplashModal").off("hide.bs.modal"), window.location.replace("/");
    });
}
function $(e) {
  e.preventDefault();
  const a = o.ajax({
    url: window.location.pathname,
    type: "POST",
    data: o("#ModalForm").serialize(),
  });
  a.done((s, t, n) => {
    G(s, t, n);
  }),
    a.fail((s, t, n) => {
      W(s);
    });
}
function G(e, a, s) {
  s.status === 200 &&
    (o(".form-control").removeClass("is-invalid"),
    o(".invalid-feedback").remove(),
    O(),
    l(s.responseJSON.message, "success"),
    Q());
}
function Q() {
  o("#submit").removeClass("login-register-buttons"),
    o("#submit")
      .prop("type", "button")
      .val("Close")
      .removeClass("btn-success")
      .addClass("btn-warning")
      .offAndOn("click", function (e) {
        i.Modal.getOrCreateInstance("#SplashModal").hide();
      });
}
function W(e, a, s) {
  if (!e.hasOwnProperty("responseJSON")) {
    if (
      e.getResponseHeader("Content-Type") === "text/html; charset=utf-8" &&
      e.status === 403
    ) {
      o("body").html(e.responseText);
      return;
    }
    window.location.assign(r.routes.errorPage);
    return;
  }
  if (e.status === 400 && e.responseJSON.hasOwnProperty("errorCode"))
    switch (e.responseJSON.errorCode) {
      case 1:
        o(".form-control").removeClass("is-invalid"),
          o(".invalid-feedback").remove(),
          f(e.responseJSON);
        break;
      case 2:
        O(), l(e.responseJSON.message, "warning");
        break;
    }
  else l("Unable to process request...", "danger");
}
function X() {
  Y(),
    K(),
    o.ajaxPrefilter(function (e, a, s) {
      let t = e.error;
      e.error = function (n, d, c) {
        if (n.status === 429) {
          p(n.responseText);
          return;
        }
        t && t.call(this, n, d, c);
      };
    });
}
function Y() {
  o(".to-register").offAndOn("click", function () {
    S(), u.toggler.hide();
  });
}
function K() {
  o(".to-login").offAndOn("click", function () {
    Z(), u.toggler.hide();
  });
}
function Z() {
  const e = o.get(r.routes.login);
  e.done((a, s, t) => {
    t.status === 200 &&
      (o("#SplashModal .modal-content").html(a),
      b(),
      i.Modal.getOrCreateInstance("#SplashModal").show());
  }),
    e.fail((a) => {
      i.Modal.getOrCreateInstance("#SplashErrorModal").show(),
        o("#SplashErrorModalAlertBanner").text("Unable to load login form...");
    });
}
function w() {
  const e = o.get(r.routes.login);
  e.done((a, s, t) => {
    t.status === 200 && (o("#SplashModal .modal-content").html(a), b());
  }),
    e.fail((a) => {
      i.Modal.getOrCreateInstance("#SplashErrorModal").show(),
        o("#SplashErrorModalAlertBanner").text("Unable to load login form...");
    });
}
function S() {
  const e = o.get(r.routes.register);
  e.done((a, s, t) => {
    t.status === 200 &&
      (o("#SplashModal .modal-content").html(a),
      V(),
      i.Modal.getOrCreateInstance("#SplashModal").show());
  }),
    e.fail((a) => {
      i.Modal.getOrCreateInstance("#SplashErrorModal").show(),
        o("#SplashErrorModalAlertBanner").text(
          "Unable to load register form...",
        );
    });
}
function O() {
  o("#SplashModalAlertBanner")
    .removeClass("alert-banner-splash-modal-display")
    .removeClassStartingWith("alert-")
    .addClass("alert-banner-splash-modal-hide");
}
function l(e, a) {
  o("#SplashModalAlertBanner")
    .removeClass("alert-banner-splash-modal-hide")
    .removeClassStartingWith("alert-")
    .addClass("alert-" + a)
    .addClass("alert-banner-splash-modal-display")
    .text(e);
}
function v(e) {
  o(".form-control").removeClass("is-invalid"),
    o(".invalid-feedback").remove(),
    o(".to-forgot-password").remove(),
    o("#SplashModalAlertBanner")
      .removeClass("alert-banner-splash-modal-hide")
      .addClass("alert-info alert-banner-splash-modal-show")
      .append(o("<div>" + e + "</div>"))
      .append(
        o(
          `<button type="button" class="btn btn-link btn-block">${r.strings.VALIDATE_MY_EMAIL}</button>`,
        ).offAndOn("click", () => {
          o("#SplashModal").off("hide.bs.modal", s), x();
        }),
      ),
    o(".register-to-login-footer").remove(),
    o(".modal-footer").remove();
  const s = () => {
    o.get(r.routes.logout), o("#SplashModal").off("hide.bs.modal", s);
  };
  o("#SplashModal").on("hide.bs.modal", s);
}
function x() {
  const e = o.get(r.routes.confirmEmailAfterRegister);
  e.done((a, s, t) => {
    t.status === 200 && (o("#SplashModal .modal-content").html(a), m(!0));
  }),
    e.fail((a) => {
      l("Unable to load email validation modal...", "danger");
    });
}
function f(e) {
  o(".invalid-feedback").remove(),
    o(".alert").each(function () {
      o(this).attr("id") !== "SplashModalAlertBanner" && o(this).remove();
    }),
    o(".form-control").removeClass("is-invalid");
  for (let a in e.errors)
    switch (a) {
      case "username":
      case "password":
      case "email":
      case "confirmEmail":
      case "confirmPassword":
      case "newPassword":
      case "confirmNewPassword":
        let s = e.errors[a][0];
        ee(a, s);
        break;
      default:
        console.log("No op.");
    }
}
function ee(e, a) {
  o('<div class="invalid-feedback"><span>' + a + "</span></div>")
    .insertAfter("#" + e)
    .show(),
    o("#" + e).addClass("is-invalid");
}
C();
P();
A();
function oe() {
  o("#ModalForm[data-modal-type='reset-password']").length &&
    (i.Modal.getOrCreateInstance("#SplashModal").show(), H());
}
function ae() {
  o("#ModalForm[data-modal-type='email-validation']").length &&
    (i.Modal.getOrCreateInstance("#SplashModal").show(), m(!1));
}
o(document).ready(function () {
  X(), N(), oe(), ae();
});
//# sourceMappingURL=splash-BGfHwdZK.js.map
