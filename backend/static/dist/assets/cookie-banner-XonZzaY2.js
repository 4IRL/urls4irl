import { $ as e, A as l } from "./navbar-shared-gG1g8UXG.js";
function u(t) {
  e("body").fadeOut(150, function () {
    document.open(),
      document.write(t),
      document.close(),
      (document.body.style.opacity = "0"),
      window.addEventListener("load", function () {
        e("body").css("opacity", "1").hide().fadeIn(150);
      });
  });
}
function b() {
  const t = e("meta[name=csrf-token]").attr("content");
  e.ajaxSetup({
    beforeSend: function (i, n) {
      return (
        !/^(GET|HEAD|OPTIONS|TRACE)$/i.test(n.type) &&
          !this.crossDomain &&
          i.setRequestHeader("X-CSRFToken", t),
        !0
      );
    },
  }),
    e.ajaxPrefilter(function (i, n, o) {
      let r = i.error;
      i.error = function (s, a, c) {
        if (s.status === 429) {
          u(s.responseText);
          return;
        }
        r && r.call(this, s, a, c);
      };
    });
}
function h() {
  (e.fn.enableTab = function () {
    return this.attr({ tabindex: 0 }), this;
  }),
    (e.fn.disableTab = function () {
      return this.attr({ tabindex: -1 }), this;
    }),
    (e.fn.offAndOn = function (t, i) {
      return this.off(t).on(t, i), this;
    }),
    (e.fn.onExact = function (t, i, n = {}) {
      return this.on(t, function (o) {
        if (e(o.currentTarget).is(this)) {
          if (n.except) {
            const r = Array.isArray(n.except) ? n.except : [n.except];
            if (e(o.target).closest(r.join(",")).length) return;
          }
          i.call(this, o);
        }
      });
    }),
    (e.fn.offAndOnExact = function (t, i, n = {}) {
      return this.off(t).onExact(t, i, n);
    }),
    (e.fn.removeClassStartingWith = function (t) {
      return (
        e(this).removeClass(function (i, n) {
          return (n.match(new RegExp("\\S*" + t + "\\S*", "g")) || []).join(
            " ",
          );
        }),
        this
      );
    }),
    (e.fn.showClassNormal = function () {
      return this.removeClass("hidden").addClass("visible"), this;
    }),
    (e.fn.showClassFlex = function () {
      return (
        this.removeClassStartingWith("hidden").addClass("visible-flex"), this
      );
    }),
    (e.fn.hideClass = function () {
      return this.removeClassStartingWith("visible").addClass("hidden"), this;
    }),
    (e.fn.removeHideClass = function () {
      return this.removeClass("hidden"), this;
    });
}
function E(t) {
  e(t).find(".tabbable").enableTab();
}
function m(t) {
  e(t).find(".tabbable").disableTab();
}
const f = {
    ENTER: "Enter",
    ESCAPE: "Escape",
    ARROW_UP: "ArrowUp",
    ARROW_DOWN: "ArrowDown",
  },
  T = Object.freeze({ CREATE: Symbol("Create"), UPDATE: Symbol("Update") }),
  C = Object.freeze({
    TEXT: Symbol("text"),
    URL: Symbol("url"),
    EMAIL: Symbol("email"),
  }),
  S = 992,
  g = 50;
function O() {
  const t = e("#CookieBanner");
  if (!t.length) return;
  setTimeout(() => {
    document.cookie.includes(l.strings.COOKIE_BANNER_SEEN) ||
      t.addClass("is-visible");
  }, 0);
  function i() {
    const s = new Date();
    s.setTime(s.getTime() + 365 * 24 * 60 * 60 * 1e3);
    const a = "expires=" + s.toUTCString(),
      c = location.protocol === "https:" ? "; Secure" : "";
    document.cookie = `${l.strings.COOKIE_BANNER_SEEN};${a}; path=/; SameSite=Lax${c}`;
  }
  function n() {
    i(),
      t.removeClass("is-visible"),
      e(document).off("click.clickOutsideBanner keyup.clickOutsideBanner");
  }
  const o = [
    "a",
    "button",
    ".UTubSelector",
    ".memberOtherBtnDelete",
    ".clickable",
    ".tagFilter",
    ".urlRow",
  ];
  e(document).on("click.clickOutsideBanner", (s) => {
    e(s.target.closest(o.join(","))).length > 0 && n();
  });
  const r = [".UTubSelector", ".clickable", ".tagFilter", ".urlRow"];
  e(document).on("keyup.clickOutsideBanner", (s) => {
    s.originalEvent.repeat ||
      (s.key === f.ENTER && e(s.target.closest(r.join(","))).length > 0 && n());
  });
}
export {
  C as I,
  f as K,
  T as M,
  g as S,
  S as T,
  b as a,
  m as d,
  E as e,
  O as i,
  h as r,
  u as s,
};
//# sourceMappingURL=cookie-banner-XonZzaY2.js.map
