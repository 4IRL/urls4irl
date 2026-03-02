import "./security-check-2tLiMbrB.js";
import { $ as t, A as c, b as S, i as Un } from "./navbar-shared-gG1g8UXG.js";
import {
  s as Ee,
  e as ue,
  S as we,
  K as b,
  d as Re,
  M as De,
  T as A,
  I as st,
  r as hn,
  a as Cn,
  i as Sn,
} from "./cookie-banner-XonZzaY2.js";
function vn() {
  return {
    utubs: [],
    activeUTubID: null,
    activeUTubName: null,
    activeUTubDescription: null,
    isCurrentUserOwner: !1,
    currentUserID: null,
    utubOwnerID: null,
    selectedURLCardID: null,
    selectedTagIDs: [],
    urls: [],
    tags: [],
    members: [],
  };
}
let ot = vn();
function p() {
  return { ...ot };
}
function m(e) {
  Object.assign(ot, e);
}
function T(e, n, a, s = 1e3) {
  let o = t.ajax({ type: e, url: n, data: a, timeout: s });
  return (
    o.fail(function (i) {
      if (((i._429Handled = !1), i.status === 429)) {
        let r = i.getResponseHeader("Content-Type");
        r &&
          r.includes("text/html") &&
          ((i._429Handled = !0), Ee(i.responseText));
      }
    }),
    o
  );
}
function M(e) {
  return e.offsetParent === null || t(e).get(0).offsetParent === null;
}
function Ln() {
  t(window).on("focus", () => {
    const e = t(".focus");
    if (e.length === 0) return;
    if (e.length > 1) {
      e.removeClass("focus");
      return;
    }
    const n = e.closest(".urlRow");
    e.hasClass("goToUrlIcon") &&
      n.find(".goToUrlIcon").addClass("visible-on-focus").trigger("focus");
  }),
    t(window).on("blur", () => {
      if (document.activeElement !== null) {
        const e = t(document.activeElement),
          n = e.closest(".urlRow");
        if (n.length == 0) {
          e.addClass("focus");
          return;
        }
        n.attr({ urlselected: !0 }), ue(n);
      }
    });
}
const _ = new Map(),
  g = Object.freeze({
    UTUB_SELECTED: "utub:selected",
    UTUB_DELETED: "utub:deleted",
    TAG_FILTER_CHANGED: "tag:filter-changed",
    TAG_DELETED: "tag:deleted",
    STALE_DATA_DETECTED: "stale-data:detected",
  });
function h(e, n) {
  return _.has(e) || _.set(e, new Set()), _.get(e).add(n), () => En(e, n);
}
function En(e, n) {
  _.get(e)?.delete(n);
}
function X(e, n) {
  _.get(e)?.forEach((a) => a(n));
}
const ke = "AccessURLModalURLString";
function B(e) {
  if (e.startsWith("http")) {
    window.open(e, "_blank").focus();
    return;
  }
  Dn(e);
}
function wn() {
  t("#confirmModal").modal("hide").removeClass("accessExternalURLModal"),
    t("#confirmModalBody").removeClass("white-space-pre-line"),
    t("#" + ke).remove();
}
function Rn(e) {
  const n = t(document.createElement("strong"));
  return n.attr("id", ke).text(e), n;
}
function Dn(e) {
  const n = "🚦 Caution! 🚦",
    a = `${c.strings.ACCESS_URL_WARNING}

`,
    s = "Nevermind",
    o = "Let's go!";
  t("#confirmModalTitle").text(n),
    t("#confirmModalBody")
      .text(a)
      .addClass("white-space-pre-line")
      .append(Rn(e)),
    t("#modalDismiss")
      .offAndOn("click", function (i) {
        i.preventDefault(), wn();
      })
      .text(s),
    t("#modalSubmit")
      .offAndOn("click", function (i) {
        i.preventDefault(), window.open(e, "_blank").focus();
      })
      .text(o),
    t("#confirmModal")
      .addClass("accessExternalURLModal")
      .modal("show")
      .on("hidden.bs.modal", () => {
        t("#confirmModal").removeClass("accessExternalURLModal"),
          t("#confirmModalBody").removeClass("white-space-pre-line"),
          t("#" + ke).remove();
      }),
    t("#modalRedirect").hide(),
    t("#modalRedirect").hideClass();
}
function it(e) {
  return !e || !e.trim();
}
function kn() {
  const e = t(".urlRow[filterable=true]").toArray();
  let n;
  for (let a = 1; a < e.length; a++)
    (n = t(e[a])),
      a % 2 === 0
        ? n.removeClass("odd").addClass("even")
        : n.removeClass("even").addClass("odd");
}
function An(e) {
  e.find(".tabbable").enableTab();
}
function Bn(e) {
  e.find(".tabbable").disableTab();
}
function In(e) {
  const n = e.find(".urlTitleBtnUpdate");
  n.length > 0 && n.hideClass();
}
function xn(e) {
  const n = e.find(".urlTitleBtnUpdate");
  n.length > 0 && n.removeHideClass();
}
function rt(e) {
  if (!e || typeof e != "string") return !1;
  let n = e.toLowerCase();
  if (
    ((n = n.trim()),
    !n ||
      (/^[a-z][a-z0-9+.-]*:/.test(n) || (n = "https://" + n), !URL.canParse(n)))
  )
    return !1;
  const s = On(n);
  if (!s) return !1;
  const o = s.protocol;
  return !["javascript:", "data:", "vbscript:"].includes(o);
}
function On(e) {
  try {
    return new URL(e);
  } catch {
    return null;
  }
}
function yn(e) {
  e.find(".urlCardDualLoadingRing").addClass("dual-loading-ring");
}
function Nn(e) {
  e.find(".urlCardDualLoadingRing").removeClass("dual-loading-ring");
}
function de(e) {
  return setTimeout(function () {
    yn(e);
  }, we);
}
function U(e, n) {
  clearTimeout(e), Nn(n);
}
async function lt(e, n) {
  const a = S.Tooltip.getOrCreateInstance(n);
  try {
    await navigator.clipboard.writeText(e),
      a.setContent({ ".tooltip-inner": `${c.strings.COPIED_URL_TOOLTIP}` }),
      a.show(),
      setTimeout(() => {
        a.hide(),
          setTimeout(() => {
            a.setContent({ ".tooltip-inner": `${c.strings.COPY_URL_TOOLTIP}` });
          }, 200);
      }, 1500);
  } catch (s) {
    a.setContent({
      ".tooltip-inner": `${c.strings.COPIED_URL_FAILURE_TOOLIP}`,
    }),
      a.show(),
      console.log("Couldn't copy url", s),
      setTimeout(() => {
        a.hide(),
          setTimeout(() => {
            a.setContent({ ".tooltip-inner": `${c.strings.COPY_URL_TOOLTIP}` });
          }, 200);
      }, 1500);
  }
}
const w = { toggler: null };
function Mn() {
  t("button#toMembers").on("click", () => {
    qs();
  }),
    t("button#toURLs").on("click", () => {
      y();
    }),
    t("button#toUTubs").on("click", () => {
      js();
    }),
    t("button#toTags").on("click", () => {
      Xs();
    }),
    Un(),
    (w.toggler = new S.Collapse("#NavbarNavDropdown", { toggle: !1 })),
    t("#NavbarNavDropdown")
      .on("show.bs.collapse", () => {
        _n();
      })
      .on("hide.bs.collapse", () => {
        Fn();
      });
}
function _n() {
  const e = t(document.createElement("div")).addClass("navbar-backdrop");
  e.on("click", function () {
    w.toggler.hide();
  }),
    setTimeout(function () {
      e.addClass("navbar-backdrop-show");
    }, 0),
    t(".navbar-brand").addClass("z9999"),
    t(".navbar-toggler").addClass("z9999"),
    t("#NavbarNavDropdown").addClass("z9999"),
    t("#mainNavbar").append(e);
}
function Fn() {
  const e = t(".navbar-backdrop");
  e.addClass("navbar-backdrop-fade"),
    setTimeout(function () {
      e.remove();
    }, 300),
    t(".navbar-brand").removeClass("z9999"),
    t(".navbar-toggler").removeClass("z9999"),
    t("#NavbarNavDropdown").removeClass("z9999");
}
function Hn(e, n) {
  return e.filter((a) => !a.name.toLowerCase().includes(n)).map((a) => a.id);
}
function Pn() {
  return t.map(t(".UTubSelector"), (e) => ({
    id: parseInt(t(e).attr("utubid")),
    name: t(e).find(".UTubName").text(),
  }));
}
function Ze(e) {
  if (e.length === 0) {
    t(".UTubSelector").removeClass("hidden");
    return;
  }
  const n = new Set(e),
    a = t(".UTubSelector");
  let s;
  for (let o = 0; o < a.length; o++)
    (s = parseInt(t(a[o]).attr("utubid"))),
      n.has(s) ? t(a[o]).addClass("hidden") : t(a[o]).removeClass("hidden");
}
function Wn() {
  const e = t("#SearchUTubWrap"),
    n = t("#UTubSearchFilterIcon"),
    a = t("#UTubSearchFilterIconClose"),
    s = t("#UTubNameSearch");
  n.offAndOnExact("click.searchInputShow", function (o) {
    e.addClass("visible").removeClass("hidden"),
      t("#UTubDeckSubheader").addClass("hidden"),
      n.addClass("hidden"),
      a.removeClass("hidden"),
      setTimeout(() => {
        s.addClass("utub-search-expanded");
      }, 0),
      s.focus();
  }),
    a.offAndOnExact("click.searchInputClose", function (o) {
      G(), s.removeClass("utub-search-expanded");
    }),
    s
      .offAndOn("focus.searchInputEsc", function (o) {
        s.offAndOn("keydown.searchInputEsc", function (i) {
          i.key === b.ESCAPE &&
            (s.blur(), G(), s.removeClass("utub-search-expanded"));
        });
      })
      .offAndOn("blur.searchInputEsc", function () {
        s.off("keydown.searchInputEsc");
      })
      .offAndOn("input", function () {
        const o = s.val().toLowerCase();
        if (o.length < c.constants.UTUBS_MIN_NAME_LENGTH) {
          Ze([]);
          return;
        }
        const i = Hn(Pn(), o);
        Ze(i);
      });
}
function G() {
  t("#UTubSearchFilterIconClose").addClass("hidden"),
    t("#UTubSearchFilterIcon").removeClass("hidden"),
    t("#SearchUTubWrap").addClass("hidden").removeClass("visible"),
    t("#UTubDeckSubheader").removeClass("hidden"),
    t("#UTubNameSearch").val(""),
    t(".UTubSelector").removeClass("hidden");
}
function Ae(e, n) {
  return {
    toRemove: e.filter((a) => !n.includes(a)),
    toAdd: n.filter((a) => !e.includes(a)),
    toUpdate: e.filter((a) => n.includes(a)),
  };
}
function Be() {
  t("#UTubOwner").empty(), t("#listMembers").empty();
}
function Gn(e, n, a) {
  const s = p().members.map((u) => u.id),
    o = t.map(e, (u) => u.id),
    { toRemove: i, toAdd: r } = Ae(s, o);
  i.forEach((u) => {
    t(".member[memberid=" + u + "]").remove();
  });
  const l = t("#listMembers");
  r.forEach((u) => {
    const d = e.find((f) => f.id === u);
    l.append(We(d.id, d.username, n, a));
  });
}
function $n(e, n, a, s, o) {
  Be();
  const i = t("#listMembers"),
    r = e.length;
  let l, u, d;
  a && Bs(o);
  for (let f = 0; f < r; f++)
    (l = e[f]),
      (u = l.username),
      (d = l.id),
      d === n ? t("#UTubOwner").append(As(n, u)) : i.append(We(d, u, a, o));
  a || vs(a, s, o), xe(a);
}
function Ie() {
  Be(),
    t("#memberBtnCreate").hideClass(),
    t("#memberSelfBtnDelete").hideClass(),
    t("#MemberDeckSubheader").text(null);
}
function xe(e = !0) {
  const n = t("#listMembers").find("span.member").length + 1,
    a = t("#MemberDeckSubheader");
  a.parent().addClass("height-2rem"),
    e
      ? (t("#memberSelfBtnDelete").hideClass(),
        t("#memberBtnCreate").showClassNormal(),
        n === 1 ? a.text("Add a member") : a.text(n + " members"))
      : (t("#memberBtnCreate").hideClass(),
        t("#memberSelfBtnDelete").showClassNormal(),
        a.text(n + " members")),
    a.closest(".titleElement").show();
}
h(
  g.UTUB_SELECTED,
  ({
    members: e,
    utubOwnerID: n,
    isCurrentUserOwner: a,
    currentUserID: s,
    utubID: o,
  }) => $n(e, n, a, s, o),
);
h(g.STALE_DATA_DETECTED, ({ members: e, utubID: n }) =>
  Gn(e, p().isCurrentUserOwner, n),
);
function ct() {
  return p().tags.map((e) => e.id);
}
function Se(e) {
  return ct().includes(e);
}
function ut() {
  return p().selectedTagIDs.length > 0;
}
function zn(e, n) {
  return n.map(({ urlId: a, tagIDs: s }) => ({
    urlId: a,
    visible: e.every((o) => s.includes(o)),
  }));
}
function Vn(e, n) {
  const a = new Map();
  return (
    n.forEach((s) => a.set(`${s}`, 0)),
    e.forEach((s) => {
      s.forEach((o) => {
        a.set(o, (a.get(o) || 0) + 1);
      });
    }),
    a
  );
}
function Jn(e) {
  return [...e].sort((n, a) => a.visibleCount - n.visibleCount);
}
const Oe = Object.freeze({ INCREMENT: 1, DECREMENT: -1 });
function jn(e) {
  e.forEach(({ urlId: n, visible: a }) => {
    t(`.urlRow[utuburlid=${n}]`).attr({ filterable: a });
  });
}
function I() {
  const e = p().selectedTagIDs,
    n = p().urls.map((s) => ({ urlId: s.utubUrlID, tagIDs: s.utubUrlTagIDs })),
    a = zn(e, n);
  jn(a), ft(), X(g.TAG_FILTER_CHANGED, { selectedTagIDs: e }), qn(), Xn();
}
function qn() {
  const e = ct(),
    n = t(".urlRow[filterable=true]"),
    a = [];
  n.each((r, l) => {
    const u = t(l).attr("data-utub-url-tag-ids");
    a.push(u ? u.split(",") : []);
  });
  const s = Vn(a, e);
  let o, i;
  for (let r = 0; r < e.length; r++) {
    const l = e[r];
    (o = t(`.tagFilter[data-utub-tag-id=${l}] .tagAppliedToUrlsCount`)),
      (i = o.text().split(" / ")),
      !(!i || i.length !== 2) && o.text(`${s.get(`${l}`)} / ${i[1]}`);
  }
}
function dt(e, n, a) {
  const s = t(`.tagFilter[data-utub-tag-id="${e}"] .tagAppliedToUrlsCount`),
    o = s.text().split(" / ");
  if (!o || o.length !== 2) {
    s.text(`${n} / ${n}`);
    return;
  }
  let i;
  a === Oe.DECREMENT ? (i = -1) : (i = 1),
    s.text(`${parseInt(o[0]) + i} / ${n}`);
}
function ft() {
  t(".urlRow[filterable=true]:visible").each((n, a) => {
    t(a)
      .removeClass("odd even")
      .addClass(n % 2 == 0 ? "even" : "odd");
  });
}
function Xn() {
  const e = t("#listTags"),
    a = e
      .children(".tagFilter")
      .get()
      .map((i) => {
        const r = t(i)
          .find(".tagAppliedToUrlsCount")
          .text()
          .trim()
          .split(" / ");
        return { el: i, visibleCount: parseInt(r[0]) || 0 };
      });
  Jn(a)
    .map(({ el: i }) => t(i).detach())
    .forEach((i) => e.append(i));
}
function bt(e) {
  const n = t(".urlString");
  for (let a = 0; a < n.length; a++) if (t(n[a]).attr("href") === e) return !0;
  return !1;
}
function fe() {
  ut() ? I() : ft();
}
h(g.TAG_DELETED, () => I());
h(g.STALE_DATA_DETECTED, ({ tags: e }) => {
  m({
    selectedTagIDs: p().selectedTagIDs.filter((n) => e.some((a) => a.id === n)),
  }),
    fe();
});
function Yn() {
  t("#utubTagBtnUpdateAllOpen")
    .on("click.openUTubTagUpdate", function () {
      re(), le();
    })
    .offAndOn("focus.openUTubTagUpdate", function () {
      t(document).offAndOn("keyup.openUTubTagUpdate", function (a) {
        a.key === b.ENTER && (re(), le());
      });
    })
    .offAndOn("blur.openUTubTagUpdate", function () {
      t(document).off("keyup.openUTubTagUpdate");
    }),
    t("#utubTagBtnUpdateAllClose")
      .on("click.closeUTubTagUpdate", function () {
        x(), z();
      })
      .offAndOn("focus.closeUTubTagUpdate", function () {
        t(document).offAndOn("keyup.closeUTubTagUpdate", function (a) {
          a.key === b.ENTER && (x(), z());
        });
      })
      .offAndOn("blur.closeUTubTagUpdate", function () {
        t(document).off("keyup.closeUTubTagUpdate");
      });
}
function Kn() {
  t("#utubTagBtnUpdateAllOpen")
    .offAndOn("click.openUTubTagUpdate", function () {
      re(), le();
    })
    .offAndOn("focus.openUTubTagUpdate", function () {
      t(document).offAndOn("keyup.openUTubTagUpdate", function (a) {
        a.key === b.ENTER && (re(), le());
      });
    })
    .offAndOn("blur.openUTubTagUpdate", function () {
      t(document).off("keyup.openUTubTagUpdate");
    }),
    t("#utubTagBtnUpdateAllClose")
      .offAndOn("click.closeUTubTagUpdate", function () {
        x(), z(), I();
      })
      .offAndOn("focus.closeUTubTagUpdate", function () {
        t(document).offAndOn("keyup.closeUTubTagUpdate", function (a) {
          a.key === b.ENTER && (x(), z(), I());
        });
      })
      .offAndOn("blur.closeUTubTagUpdate", function () {
        t(document).off("keyup.closeUTubTagUpdate");
      });
}
function re() {
  t("#utubTagStandardBtns").hideClass(),
    t("#utubTagCloseUpdateTagBtnContainer").showClassNormal();
}
function x() {
  t("#utubTagStandardBtns").showClassFlex(),
    t("#utubTagCloseUpdateTagBtnContainer").hideClass();
}
function le() {
  t(".tagCountWrap").hideClass(),
    t(".tagMenuWrap").showClassNormal(),
    t(".tagFilter").addClass("disabled").disableTab(),
    ue(t("#listTags"));
}
function z() {
  Re(t("#listTags")),
    t(".tagCountWrap").showClassNormal(),
    t(".tagMenuWrap").hideClass(),
    t(".tagFilter").removeClass("disabled").enableTab();
}
function Qn() {
  t("#confirmModal").modal("hide");
}
function Zn(e, n, a) {
  const s = "Are you sure you want to delete this Tag?",
    o = t("<strong>").text(`'${a}'`),
    i = `${c.strings.UTUB_TAG_DELETE_WARNING}`.replace(
      "{{ tag_string }}",
      o.prop("outerHTML"),
    ),
    r = "Nevermind...",
    l = "Delete this sucka!";
  t("#confirmModalTitle").text(s),
    t("#confirmModalBody").html(i),
    t("#modalDismiss")
      .removeClass()
      .addClass("btn btn-secondary")
      .offAndOn("click", function (u) {
        u.preventDefault(), Qn();
      })
      .text(r),
    t("#modalSubmit")
      .removeClass()
      .addClass("btn btn-danger")
      .text(l)
      .offAndOn("click", function (u) {
        u.preventDefault(), ta(e, n);
      }),
    t("#confirmModal").modal("show"),
    t("#modalRedirect").hide();
}
function ea(e, n) {
  return c.routes.deleteUTubTag(e, n);
}
function ta(e, n) {
  let a = ea(e, n);
  const s = T("delete", a, []);
  s.done(function (o, i, r) {
    r.status === 200 && na(o);
  }),
    s.fail(function (o, i, r) {
      aa(o);
    });
}
function na(e) {
  t("#confirmModal").modal("hide");
  const n = e.utubTag.utubTagID,
    a = new Set(e.utubUrlIDs);
  m({
    tags: p().tags.filter((o) => o.id !== n),
    urls: p().urls.map((o) =>
      a.has(o.utubUrlID)
        ? { ...o, utubUrlTagIDs: o.utubUrlTagIDs.filter((i) => i !== n) }
        : o,
    ),
    selectedTagIDs: p().selectedTagIDs.filter((o) => o !== n),
  });
  const s = t(".tagFilter[data-utub-tag-id=" + n + "]");
  s.fadeOut("fast", () => {
    t(".tagBadge[data-utub-tag-id=" + n + "]").remove(),
      s.remove(),
      t(".tagFilter").length === 0 &&
        (t("#utubTagBtnUpdateAllOpen").hideClass(),
        t("#unselectAllTagFilters").hideClass(),
        t("#utubTagCloseUpdateTagBtnContainer").hideClass(),
        t("#utubTagStandardBtns").showClassFlex()),
      X(g.TAG_DELETED, { utubTagID: n });
  });
}
function aa(e) {
  if (!e._429Handled) {
    if (
      e.status === 403 &&
      e.getResponseHeader("Content-Type") === "text/html; charset=utf-8"
    ) {
      t("body").html(e.responseText);
      return;
    }
    t("#HomeModalAlertBanner")
      .showClassNormal()
      .append(`${c.strings.MAY_HAVE_ALREADY_BEEN_DELETED}<br>`)
      .append("Click ")
      .append(
        t(document.createElement("a"))
          .attr({ href: "#", id: "Reloader" })
          .text("here"),
      )
      .append(" to reload the UTub."),
      t("#Reloader").offAndOn("click", (n) => {
        n.preventDefault(), window.location.reload();
      }),
      t("#modalSubmit").addClass("disabled");
  }
}
function sa() {
  t("#unselectAllTagFilters").on("click.unselectAllTags", function () {
    pt();
  });
}
function oa() {
  t("#unselectAllTagFilters")
    .removeClass("red-icon-disabled")
    .on("click.unselectAllTags", function () {
      pt();
    })
    .attr({ tabindex: 0 });
}
function ye() {
  t("#unselectAllTagFilters")
    .addClass("red-icon-disabled")
    .off(".unselectAllTags")
    .attr({ tabindex: -1 });
}
function ia() {
  t("#TagDeckSubheader").text(
    "0 of " + c.constants.TAGS_MAX_ON_URLS + " tag filters applied",
  );
}
function pt() {
  t(".tagFilter")
    .removeClass("selected unselected disabled")
    .addClass("unselected")
    .each((e, n) => {
      t(n)
        .offAndOn("click.tagFilterSelected", function () {
          O(t(n));
        })
        .offAndOn("focus.tagFilterSelected", function () {
          t(document).on("keyup.tagFilterSelected", function (a) {
            a.key === b.ENTER && O(t(n));
          });
        })
        .offAndOn("blur.tagFilterSelected", function () {
          t(document).off("keyup.tagFilterSelected");
        })
        .attr({ tabindex: 0 });
    }),
    ye(),
    m({ selectedTagIDs: [] }),
    I();
}
function ra(e = 15) {
  const n = e + "px",
    a = "http://www.w3.org/2000/svg",
    s = t(document.createElementNS(a, "svg")),
    o = t(document.createElementNS(a, "path"));
  return (
    o.attr({
      d: "M11.46.146A.5.5 0 0 0 11.107 0H4.893a.5.5 0 0 0-.353.146L.146 4.54A.5.5 0 0 0 0 4.893v6.214a.5.5 0 0 0 .146.353l4.394 4.394a.5.5 0 0 0 .353.146h6.214a.5.5 0 0 0 .353-.146l4.394-4.394a.5.5 0 0 0 .146-.353V4.893a.5.5 0 0 0-.146-.353zm-6.106 4.5L8 7.293l2.646-2.647a.5.5 0 0 1 .708.708L8.707 8l2.647 2.646a.5.5 0 0 1-.708.708L8 8.707l-2.646 2.647a.5.5 0 0 1-.708-.708L7.293 8 4.646 5.354a.5.5 0 1 1 .708-.708",
    }),
    s
      .attr({
        xmlns: a,
        width: n,
        height: n,
        fill: "currentColor",
        class: "bi bi-x-octagon-fill",
        viewBox: "0 0 16 16",
      })
      .append(o),
    s
  );
}
function Y(e, n, a, s = 0) {
  const o = t(document.createElement("div")),
    i = t(document.createElement("span")),
    r = t(document.createElement("div")),
    l = t(document.createElement("div")),
    u = t(document.createElement("span")),
    d = t(document.createElement("button"));
  return (
    o
      .addClass("tagFilter pointerable unselected col-12")
      .attr({ "data-utub-tag-id": n, tabindex: 0 })
      .on("click.tagFilterSelected", function () {
        O(o);
      })
      .on("focus.tagFilterSelected", function () {
        o.offAndOn("keyup.tagFilterSelected", function (f) {
          f.key === b.ENTER && t(f.target).hasClass("tagFilter") && O(o);
        });
      })
      .on("blur.tagFilterSelected", function () {
        o.off("keyup.tagFilterSelected");
      }),
    i.text(a),
    r.addClass("tagCountWrap"),
    l.addClass("tagMenuWrap hidden"),
    u.addClass("tagAppliedToUrlsCount").text(`${s} / ${s}`),
    d
      .addClass("utubTagBtnDelete align-center pointerable tabbable")
      .onExact("click.removeUtubTag", function (f) {
        Zn(e, n, a);
      }),
    d.append(ra(22)),
    o.append(i),
    r.append(u),
    o.append(r),
    l.append(d),
    o.append(l),
    o
  );
}
function O(e) {
  const n = t.map(t(".tagFilter.selected"), (s) =>
    parseInt(t(s).attr("data-utub-tag-id")),
  );
  if (n.length >= c.constants.TAGS_MAX_ON_URLS && e.hasClass("unselected"))
    return;
  if (e.hasClass("selected")) {
    switch (n.length) {
      case c.constants.TAGS_MAX_ON_URLS:
        la();
        break;
      case 1:
        ye();
        break;
    }
    e.addClass("unselected").removeClass("selected");
  } else
    switch ((e.removeClass("unselected").addClass("selected"), n.length)) {
      case c.constants.TAGS_MAX_ON_URLS - 1:
        ca();
        break;
      case 0:
        oa();
        break;
    }
  const a = t.map(t(".tagFilter.selected"), (s) =>
    parseInt(t(s).attr("data-utub-tag-id")),
  );
  m({ selectedTagIDs: a }), I();
}
function la() {
  t(".tagFilter.unselected")
    .removeClass("disabled")
    .each((n, a) => {
      t(a)
        .on("click.tagFilterSelected", function (s) {
          t(s.target).closest(".tagFilter").is(this) && O(t(a));
        })
        .offAndOn("focus.tagFilterSelected", function () {
          t(a).on("keyup.tagFilterSelected", function (s) {
            s.key === b.ENTER && O(t(a));
          });
        })
        .offAndOn("blur.tagFilterSelected", function () {
          t(a).off("keyup.tagFilterSelected");
        })
        .attr({ tabindex: 0 });
    });
}
function ca() {
  t(".tagFilter.unselected")
    .addClass("disabled")
    .each((n, a) => {
      t(a).off(".tagFilterSelected").attr({ tabindex: -1 });
    });
}
function ua(e) {
  t("#utubTagBtnCreate").offAndOn("click.createUTubTag", function () {
    pa(e);
  });
}
function Ne() {
  t("#utubTagCreate").val(null);
}
function da(e) {
  const n = t("#utubTagSubmitBtnCreate"),
    a = t("#utubTagCancelBtnCreate");
  n.offAndOnExact("click.createUTubTagSubmit", function (o) {
    gt(e);
  }),
    a.offAndOnExact("click.createUTubTagEscape", function (o) {
      K();
    });
  const s = t("#utubTagCreate");
  s.offAndOn("focus.createUTubTagSubmitEscape", function () {
    fa(e, s);
  }),
    s.offAndOn("blur.createUTubTagSubmitSubmitEscape", function () {
      ba(s);
    });
}
function mt() {
  t("#memberCreate").off(".createUTubTagSubmitEscape");
}
function fa(e, n) {
  n.offAndOn("keydown.createUTubTagSubmitEscape", function (a) {
    if (!a.originalEvent.repeat)
      switch (a.key) {
        case b.ENTER:
          gt(e);
          break;
        case b.ESCAPE:
          K();
          break;
      }
  });
}
function ba(e) {
  e.off(".createUTubTagSubmitEscape");
}
function pa(e) {
  t("#createUTubTagWrap").showClassFlex(),
    t("#listTags").hideClass(),
    t("#utubTagStandardBtns").hideClass(),
    da(e),
    t("#utubTagCreate").trigger("focus");
}
function K() {
  t("#createUTubTagWrap").hideClass(),
    t("#listTags").showClassNormal(),
    he() !== 0 && t("#utubTagStandardBtns").showClassFlex(),
    mt(),
    Me(),
    Ne();
}
function ma(e) {
  const n = c.routes.createUTubTag(e),
    s = { tagString: t("#utubTagCreate").val() };
  return [n, s];
}
function gt(e) {
  let n, a;
  ([n, a] = ma(e)), Me();
  const s = T("post", n, a);
  s.done(function (o, i, r) {
    r.status === 200 && ga(o, e);
  }),
    s.fail(function (o, i, r) {
      Ta(o);
    });
}
function ga(e, n) {
  Ne(),
    m({
      tags: [
        ...p().tags,
        {
          id: e.utubTag.utubTagID,
          tagString: e.utubTag.tagString,
          tagApplied: e.tagCountsInUtub,
        },
      ],
    }),
    t("#listTags").append(Y(n, e.utubTag.utubTagID, e.utubTag.tagString)),
    t("#unselectAllTagFilters").showClassNormal(),
    t("#utubTagBtnUpdateAllOpen").showClassNormal(),
    K();
}
function Ta(e) {
  if (!e._429Handled) {
    if (!e.hasOwnProperty("responseJSON")) {
      if (
        e.status === 403 &&
        e.getResponseHeader("Content-Type") === "text/html; charset=utf-8"
      ) {
        t("body").html(e.responseText);
        return;
      }
      window.location.assign(c.routes.errorPage);
      return;
    }
    switch (e.status) {
      case 400:
        const n = e.responseJSON,
          a = n.hasOwnProperty("errors"),
          s = n.hasOwnProperty("message");
        if (a) {
          Ua(n.errors);
          break;
        } else if (s) {
          Tt("utubTag", n.message);
          break;
        }
      default:
        window.location.assign(c.routes.errorPage);
    }
  }
}
function Ua(e) {
  for (let n in e)
    if (n === "tagString") {
      let a = e[n][0];
      Tt(n, a);
      return;
    }
}
function Tt(e, n) {
  t("#utubTagCreate-error").addClass("visible").text(n),
    t("#utubTagCreate").addClass("invalid-field");
}
function Me() {
  ["utubTag"].forEach((n) => {
    t("#" + n + "Create-error").removeClass("visible"),
      t("#" + n + "Create").removeClass("invalid-field");
  });
}
let oe = null;
function ha(e, n) {
  Ca(), ua(n), Kn();
  const a = t("#listTags");
  if (e.length > 0) {
    const s = t("#unselectAllTagFilters");
    s.showClassNormal(),
      s.addClass("red-icon-disabled"),
      t("#utubTagBtnUpdateAllOpen").showClassNormal();
  }
  for (let s in e) a.append(Y(n, e[s].id, e[s].tagString, e[s].tagApplied));
  (oe = h(g.TAG_FILTER_CHANGED, ({ selectedTagIDs: s }) => {
    La(s.length);
  })),
    t("#utubTagBtnCreate").showClassNormal(),
    t("#TagDeck > .dynamic-subheader").addClass("height-2p5rem");
}
function Ca() {
  oe && (oe(), (oe = null)),
    t("#listTags").empty(),
    ia(),
    ye(),
    t("#utubTagBtnCreate").hideClass(),
    t("#unselectAllTagFilters").hideClass(),
    t("#utubTagBtnUpdateAllOpen").hideClass(),
    K(),
    z(),
    x();
}
function Sa() {
  t("#listTags").empty(),
    t("#createUTubTagWrap").hideClass(),
    t("#utubTagBtnCreate").hideClass(),
    t("#unselectAllTagFilters").hideClass(),
    x(),
    t("#utubTagBtnUpdateAllOpen").hideClass(),
    mt(),
    Me(),
    Ne();
}
function va(e, n) {
  const a = p().tags.map((l) => l.id),
    s = t.map(e, (l) => l.id),
    { toRemove: o, toAdd: i } = Ae(a, s);
  o.forEach((l) => {
    t(".tagFilter[data-utub-tag-id=" + l + "]").remove();
  });
  const r = t("#listTags");
  i.forEach((l) => {
    const u = e.find((d) => d.id === l);
    r.append(Y(n, u.id, u.tagString));
  });
}
function _e() {
  t("#TagDeckSubheader").text(null);
}
function La(e) {
  t("#TagDeckSubheader").text(
    e + " of " + c.constants.TAGS_MAX_ON_URLS + " tag filters applied",
  );
}
function Ea(e) {
  t(".tagFilter[data-utub-tag-id=" + e + "]").remove();
}
h(g.UTUB_SELECTED, ({ tags: e, utubID: n }) => ha(e, n));
h(g.STALE_DATA_DETECTED, ({ tags: e, utubID: n }) => va(e, n));
function Fe() {
  return t(".urlRow").length;
}
function Ut() {
  return t(".urlRow[filterable=true]").length;
}
function wa() {
  t(document).offAndOn("keyup.switchurls", function (e) {
    const n = e.key === b.ARROW_UP,
      a = e.key === b.ARROW_DOWN;
    if (!n && !a) return;
    const s = jt(),
      o = t(".urlRow"),
      i = o.length;
    if (i === 0) return;
    if (s === null) {
      v(t(o[0]));
      return;
    }
    const r = o.index(s);
    n && v(r === 0 ? t(o[i - 1]) : t(o[r - 1])),
      a && (r === i - 1 ? v(t(o[0])) : v(t(o[r + 1])));
  });
}
function Ra(e) {
  const n = "20px",
    a = "http://www.w3.org/2000/svg",
    s = t(document.createElementNS(a, "svg")),
    o = t(document.createElementNS(a, "path"));
  return (
    o.attr({
      d: "M14 0a2 2 0 0 1 2 2v12a2 2 0 0 1-2 2H2a2 2 0 0 1-2-2V2a2 2 0 0 1 2-2zM5.904 10.803 10 6.707v2.768a.5.5 0 0 0 1 0V5.5a.5.5 0 0 0-.5-.5H6.525a.5.5 0 1 0 0 1h2.768l-4.096 4.096a.5.5 0 0 0 .707.707",
    }),
    s
      .attr({
        xmlns: a,
        width: n,
        height: n,
        fill: "currentColor",
        class: "bi bi-arrow-up-right-square-fill pointerable",
        viewBox: "0 0 16 16",
      })
      .append(o),
    t(document.createElement("button"))
      .append(s)
      .addClass("self-start goToUrlIcon")
      .enableTab()
      .onExact("click", (l) => {
        B(e);
      })
  );
}
function ht(e) {
  return t(document.createElement("h6"))
    .addClass("urlTitle long-text-ellipsis")
    .text(e);
}
function Da(e, n, a) {
  const s = t(document.createElement("div")).addClass(
      "flex-row ninetyfive-width",
    ),
    o = t(document.createElement("div")).addClass(
      "flex-row ninetyfive-width urlTitleAndUpdateIconWrap",
    ),
    i = t(document.createElement("div")).addClass(
      "flex-row full-width urlTitleAndUpdateIconInnerWrap",
    );
  return (
    i.append(ht(e)).append(ka(n)),
    o.append(i),
    s.append(o).append(Aa(e, n, a)),
    s
  );
}
function ka(e) {
  return li(20)
    .addClass("urlTitleBtnUpdate")
    .onExact("click.showUpdateURLTitle", function (n) {
      const a = t(n.target).closest(".urlTitleAndUpdateIconWrap");
      ro(a, e);
    });
}
function Aa(e, n, a) {
  const s = Ke("urlTitle", De.UPDATE.description).addClass(
    "updateUrlTitleWrap hidden",
  );
  s.find("label").text("URL Title");
  const o = s.find("input");
  o
    .prop("minLength", c.constants.URLS_TITLE_MIN_LENGTH)
    .prop("maxLength", c.constants.URLS_TITLE_MAX_LENGTH)
    .val(e),
    o.offAndOn("focus.updateURLTitleInputFocus", function () {
      o.on("keydown.updateURLTitleSubmitEscape", function (l) {
        if (!l.originalEvent.repeat)
          switch (l.key) {
            case b.ENTER:
              nt(o, n, a);
              break;
            case b.ESCAPE:
              V(n);
              break;
          }
      });
    }),
    o.offAndOn("blur.updateURLTitleInputFocus", function () {
      o.off("keydown.updateURLTitleSubmitEscape");
    });
  const i = Xe(30).addClass("urlTitleSubmitBtnUpdate");
  i.onExact("click.updateUrlTitle", function (l) {
    nt(o, n, a);
  });
  const r = Ye(30).addClass("urlTitleCancelBtnUpdate tabbable");
  return (
    r.onExact("click.updateUrlTitle", function (l) {
      V(n);
    }),
    s.append(i).append(r),
    s
  );
}
function Ct() {
  const e = "24px",
    n = "http://www.w3.org/2000/svg",
    a = t(document.createElementNS(n, "svg")),
    s = t(document.createElementNS(n, "path")),
    o = t(document.createElementNS(n, "rect")),
    i =
      "M21,12l-4.37,6.16C16.26,18.68,15.65,19,15,19h-3l0-2h3l3.55-5L15,7H5v3H3V7c0-1.1,0.9-2,2-2h10c0.65,0,1.26,0.31,1.63,0.84 L21,12z M10,15H7v-3H5v3H2v2h3v3h2v-3h3V15z",
    r = { stroke: "#000", "stroke-width": "1" };
  return (
    s.attr({ d: i, ...r }),
    o.attr({ fill: "none", height: 16, width: 16 }),
    a
      .attr({
        xmlns: n,
        width: e,
        height: e,
        fill: "currentColor",
        viewBox: "0 0 24 24",
      })
      .append(o)
      .append(s),
    a
  );
}
function Ba(e) {
  const n = t(document.createElement("button"));
  return (
    n
      .addClass(
        "btn btn-info urlTagBtnCreate tabbable flex-column justify-center fourty-p-width fourty-p-height",
      )
      .attr({
        type: "button",
        "data-bs-toggle": "tooltip",
        "data-bs-custom-class": "urlTagBtnCreate-tooltip",
        "data-bs-placement": "top",
        "data-bs-trigger": "hover",
        "data-bs-title": `${c.strings.ADD_URL_TAG_TOOLTIP}`,
      })
      .disableTab()
      .onExact("click", function (a) {
        St(e, n);
      })
      .append(Ct()),
    S.Tooltip.getOrCreateInstance(n),
    n
  );
}
function Ia(e, n) {
  const a = Ke("urlTag", De.CREATE.description).addClass(
    "createUrlTagWrap hidden flex-start gap-5p",
  );
  a.find("label").text("Tag");
  const s = a
    .find("input")
    .prop("minLength", c.constants.TAGS_MIN_LENGTH)
    .prop("maxLength", c.constants.TAGS_MAX_LENGTH);
  Ga(s, e, n);
  const o = Xe(30).addClass("urlTagSubmitBtnCreate");
  o.onExact("click.createURLTag", function (r) {
    vt(s, e, n);
  });
  const i = Ye(30).addClass("urlTagCancelBtnCreate");
  return (
    i.onExact("click.createURLTag", function (r) {
      Q(e);
    }),
    a.append(o).append(i),
    a
  );
}
function St(e, n) {
  const a = e.find(".createUrlTagWrap");
  ue(a),
    t(a).showClassFlex(),
    R() && a.find("input").focus(),
    setTimeout(function () {
      a.find("input").trigger("focus");
    }, 100),
    e.find(".urlBtnAccess").hideClass(),
    e.find(".urlStringBtnUpdate").hideClass(),
    e.find(".urlBtnDelete").hideClass(),
    e.find(".urlBtnCopy").hideClass(),
    e.find(".tagBadge").removeClass("tagBadgeHoverable");
  const s = S.Tooltip.getInstance(n);
  s && (s.hide(), s.disable()),
    n
      .removeClass("fourty-p-width")
      .addClass("cancel urlTagCancelBigBtnCreate")
      .text("Cancel")
      .offAndOnExact("click", function (o) {
        Q(e), s && s.enable();
      }),
    wt(e),
    In(e),
    ge(e);
}
function Q(e) {
  Et(e);
  const n = e.find(".urlTagBtnCreate");
  n.removeClass("cancel urlTagCancelBigBtnCreate")
    .addClass("fourty-p-width")
    .offAndOnExact("click", function (s) {
      St(e, n);
    })
    .text("")
    .append(Ct());
  const a = e.find(".createUrlTagWrap");
  Re(a),
    a.hideClass(),
    a.find("input").val(null),
    e.find(".urlBtnAccess").showClassFlex(),
    e.find(".urlStringBtnUpdate").showClassFlex(),
    e.find(".urlBtnDelete").showClassFlex(),
    e.find(".urlBtnCopy").showClassFlex(),
    e.find(".tagBadge").addClass("tagBadgeHoverable"),
    Rt(e),
    xn(e),
    me(e);
}
function xa(e, n, a) {
  const s = c.routes.createURLTag(n, a),
    o = { tagString: e.val() };
  return [s, o];
}
async function vt(e, n, a) {
  const s = parseInt(n.attr("utuburlid"));
  let o, i;
  [o, i] = xa(e, a, s);
  let r;
  try {
    (r = de(n)), await ee(a, s, n);
    const l = T("post", o, i);
    l.done(function (u, d, f) {
      f.status === 200 && (Et(n), Oa(u, n, a));
    }),
      l.fail(function (u, d, f) {
        ya(u, n);
      }),
      l.always(function () {
        U(r, n);
      });
  } catch (l) {
    U(r, n),
      te(l, n, { showError: !0, message: "Another user has deleted this URL" });
  }
}
function Oa(e, n, a) {
  Q(n);
  const s = parseInt(n.attr("utuburlid"));
  m({
    urls: p().urls.map((u) =>
      u.utubUrlID === s ? { ...u, utubUrlTagIDs: e.utubUrlTagIDs } : u,
    ),
    tags: p().tags.map((u) =>
      u.id === e.utubTag.utubTagID
        ? { ...u, tagApplied: e.tagCountsInUtub }
        : u,
    ),
  });
  const o = e.utubTag.utubTagID,
    i = e.utubTag.tagString,
    r = e.tagCountsInUtub;
  n.find(".urlTagsContainer").append(be(o, i, n, a));
  const l = n.attr("data-utub-url-tag-ids") || "";
  if (
    (l.trim()
      ? n.attr("data-utub-url-tag-ids", l + `,${o}`)
      : n.attr("data-utub-url-tag-ids", o),
    t("#unselectAllTagFilters").showClassNormal(),
    Se(o))
  )
    dt(o, r, Oe.INCREMENT);
  else {
    const u = Y(a, o, i, r);
    t(".tagFilter.selected").length === c.constants.TAGS_MAX_ON_URL &&
      u.addClass("disabled").off(".tagFilterSelected"),
      t("#listTags").append(u);
  }
}
function ya(e, n) {
  if (!e._429Handled) {
    if (!e.hasOwnProperty("responseJSON")) {
      if (
        e.status === 403 &&
        e.getResponseHeader("Content-Type") === "text/html; charset=utf-8"
      ) {
        t("body").html(e.responseText);
        return;
      }
      window.location.assign(c.routes.errorPage);
      return;
    }
    if (e.status === 400) {
      const a = e.responseJSON;
      a.hasOwnProperty("message") &&
        (a.hasOwnProperty("errors")
          ? Na(a.errors, n)
          : Lt("urlTag", a.message, n));
    } else window.location.assign(c.routes.errorPage);
  }
}
function Na(e, n) {
  for (let a in e)
    if (a === "tagString") {
      let s = e[a][0];
      Lt("urlTag", s, n);
      return;
    }
}
function Lt(e, n, a) {
  a
    .find("." + e + "Create-error")
    .addClass("visible")
    .text(n),
    a.find("." + e + "Create").addClass("invalid-field");
}
function Et(e) {
  ["urlTag"].forEach((a) => {
    e.find("." + a + "Create").removeClass("invalid-field"),
      e.find("." + a + "Create-error").removeClass("visible");
  });
}
function Ma(e, n, a) {
  return c.routes.deleteURLTag(e, n, a);
}
async function _a(e, n, a, s) {
  const o = parseInt(a.attr("utuburlid"));
  let i;
  try {
    if (((i = de(a)), await ee(s, o, a), !Pa(e, a))) {
      U(i, a);
      return;
    }
    const r = Ma(s, o, e),
      l = T("delete", r, []);
    l.done(function (u, d, f) {
      f.status === 200 && Fa(u, n, a);
    }),
      l.fail(function (u, d, f) {
        Ha(u);
      }),
      l.always(function () {
        U(i, a);
      });
  } catch (r) {
    U(i, a),
      te(r, a, { showError: !0, message: "Another user has deleted this URL" });
  }
}
function Fa(e, n, a) {
  const s = e.utubTag.utubTagID,
    o = parseInt(a.attr("utuburlid"));
  m({
    urls: p().urls.map((r) =>
      r.utubUrlID === o ? { ...r, utubUrlTagIDs: e.utubUrlTagIDs } : r,
    ),
    tags: p().tags.map((r) =>
      r.id === s ? { ...r, tagApplied: e.tagCountsInUtub } : r,
    ),
  }),
    dt(s, e.tagCountsInUtub, Oe.DECREMENT);
  const i = a.attr("data-utub-url-tag-ids") || "";
  if (i.trim()) {
    let r = i.split(",").map((u) => u.trim());
    const l = r.findIndex((u) => parseInt(u) === s);
    l !== -1 && r.splice(l, 1), a.attr("data-utub-url-tag-ids", r.join(","));
  }
  n.remove(), fe();
}
function Ha(e) {
  if (!e._429Handled) {
    if (
      e.status === 403 &&
      e.getResponseHeader("Content-Type") === "text/html; charset=utf-8"
    ) {
      t("body").html(e.responseText);
      return;
    }
    window.location.assign(c.routes.errorPage);
  }
}
function wt(e) {
  const n = e.find(".urlTagBtnDelete");
  for (let a = 0; a < n.length; a++) t(n[a]).addClass("hidden");
}
function Rt(e) {
  const n = e.find(".urlTagBtnDelete");
  for (let a = 0; a < n.length; a++) t(n[a]).removeClass("hidden");
}
function Pa(e, n) {
  return (
    n.find(".urlTagsContainer > .tagBadge[data-utub-tag-id=" + e + "]").length >
    0
  );
}
function Wa(e, n, a, s) {
  const o = t(document.createElement("div")).addClass(
    "urlTagsContainer flex-row flex-start",
  );
  for (let i in n) {
    let r = e.find(function (u) {
        if (u.id === n[i]) return u;
      }),
      l = be(r.id, r.tagString, a, s);
    t(o).append(l);
  }
  return o;
}
function Ga(e, n, a) {
  e.offAndOn("focus.createURLTagFocus", function () {
    t(document).offAndOn("keyup.createURLTagFocus", function (s) {
      switch (s.key) {
        case b.ENTER:
          vt(e, n, a);
          break;
        case b.ESCAPE:
          Q(n);
          break;
      }
    });
  }),
    e.offAndOn("blur.createURLTagFocus", function () {
      t(document).off("keyup.createURLTagFocus");
    });
}
function be(e, n, a, s) {
  const o = t(document.createElement("span")),
    i = t(document.createElement("button")),
    r = t(document.createElement("span")).addClass("tagText").text(n);
  return (
    o
      .addClass(
        "tagBadge tagBadgeHoverable flex-row-reverse align-center justify-flex-end",
      )
      .attr({ "data-utub-tag-id": e }),
    i
      .addClass("urlTagBtnDelete flex-row align-center pointerable tabbable")
      .onExact("click", function (l) {
        _a(e, o, a, s);
      }),
    i.append($a()),
    t(o).append(i).append(r),
    o
  );
}
function $a(e = 15) {
  const n = e + "px",
    a = "http://www.w3.org/2000/svg",
    s = t(document.createElementNS(a, "svg")),
    o = t(document.createElementNS(a, "path"));
  return (
    o.attr({
      d: "M11.46.146A.5.5 0 0 0 11.107 0H4.893a.5.5 0 0 0-.353.146L.146 4.54A.5.5 0 0 0 0 4.893v6.214a.5.5 0 0 0 .146.353l4.394 4.394a.5.5 0 0 0 .353.146h6.214a.5.5 0 0 0 .353-.146l4.394-4.394a.5.5 0 0 0 .146-.353V4.893a.5.5 0 0 0-.146-.353zm-6.106 4.5L8 7.293l2.646-2.647a.5.5 0 0 1 .708.708L8.707 8l2.647 2.646a.5.5 0 0 1-.708.708L8 8.707l-2.646 2.647a.5.5 0 0 1-.708-.708L7.293 8 4.646 5.354a.5.5 0 1 1 .708-.708",
    }),
    s
      .attr({
        xmlns: a,
        width: n,
        height: n,
        fill: "currentColor",
        class: "bi bi-x-octagon-fill",
        viewBox: "0 0 16 16",
      })
      .append(o),
    s
  );
}
function za() {
  const e = "20px",
    n = "http://www.w3.org/2000/svg",
    a = t(document.createElementNS(n, "svg")),
    s = t(document.createElementNS(n, "path")).attr({ "fill-rule": "evenodd" }),
    o = t(document.createElementNS(n, "path")).attr({ "fill-rule": "evenodd" }),
    i =
      "M8.636 3.5a.5.5 0 0 0-.5-.5H1.5A1.5 1.5 0 0 0 0 4.5v10A1.5 1.5 0 0 0 1.5 16h10a1.5 1.5 0 0 0 1.5-1.5V7.864a.5.5 0 0 0-1 0V14.5a.5.5 0 0 1-.5.5h-10a.5.5 0 0 1-.5-.5v-10a.5.5 0 0 1 .5-.5h6.636a.5.5 0 0 0 .5-.5",
    r =
      "M16 .5a.5.5 0 0 0-.5-.5h-5a.5.5 0 0 0 0 1h3.793L6.146 9.146a.5.5 0 1 0 .708.708L15 1.707V5.5a.5.5 0 0 0 1 0z",
    l = {
      stroke: "#000",
      "stroke-width": "1",
      "stroke-linecap": "round",
      "stroke-linejoin": "round",
    };
  return (
    s.attr({ d: i, ...l }),
    o.attr({ d: r, ...l }),
    a
      .attr({
        xmlns: n,
        width: e,
        height: e,
        fill: "currentColor",
        class: "bi bi-box-arrow-up-right",
        viewBox: "0 0 16 16",
      })
      .append(s)
      .append(o),
    a
  );
}
function Va(e) {
  const n = t(document.createElement("button"));
  return (
    n
      .addClass(
        "btn btn-primary urlBtnAccess tabbable flex-column justify-center sixty-p-width fourty-p-height",
      )
      .attr({
        type: "button",
        "data-bs-toggle": "tooltip",
        "data-bs-custom-class": "urlBtnAccess-tooltip",
        "data-bs-placement": "top",
        "data-bs-offset": "10,0",
        "data-bs-trigger": "hover",
        "data-bs-title": `${c.strings.ACCESS_URL_TOOLTIP}`,
      })
      .disableTab()
      .onExact("click", function (a) {
        const s = S.Tooltip.getInstance(this);
        s && s.hide(), B(e.urlString);
      }),
    n.append(za()),
    S.Tooltip.getOrCreateInstance(n),
    n
  );
}
function Ja() {
  const e = "16px",
    n = "http://www.w3.org/2000/svg",
    a = t(document.createElementNS(n, "svg")),
    s = t(document.createElementNS(n, "path")),
    o =
      "M4 2a2 2 0 0 1 2-2h8a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2zm2-1a1 1 0 0 0-1 1v8a1 1 0 0 0 1 1h8a1 1 0 0 0 1-1V2a1 1 0 0 0-1-1zM2 5a1 1 0 0 0-1 1v8a1 1 0 0 0 1 1h8a1 1 0 0 0 1-1v-1h1v1a2 2 0 0 1-2 2H2a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2h1v1z",
    i = { stroke: "#000", "stroke-width": "1", "fill-rule": "evenodd" };
  return (
    s.attr({ d: o, ...i }),
    a
      .attr({
        xmlns: n,
        width: e,
        height: e,
        fill: "currentColor",
        viewBox: "0 0 16 16",
      })
      .append(s),
    a
  );
}
function ja(e) {
  const n = t(document.createElement("button"));
  return (
    n
      .addClass(
        "btn btn-info urlBtnCopy tabbable flex-column flex-center justify-center fourty-p-width fourty-p-height",
      )
      .attr({
        type: "button",
        "data-bs-toggle": "tooltip",
        "data-bs-custom-class": "urlBtnCopy-tooltip",
        "data-bs-placement": "top",
        "data-bs-title": `${c.strings.COPY_URL_TOOLTIP}`,
      })
      .disableTab()
      .onExact("click", function (a) {
        lt(e.urlString, this);
      })
      .append(Ja())
      .on("blur", function () {
        n.off("keyup.copyURL");
      }),
    S.Tooltip.getOrCreateInstance(n),
    n
  );
}
function Dt() {
  const e = "16px",
    n = "http://www.w3.org/2000/svg",
    a = t(document.createElementNS(n, "svg")),
    s = t(document.createElementNS(n, "path")),
    o =
      "M12.854.146a.5.5 0 0 0-.707 0L10.5 1.793 14.207 5.5l1.647-1.646a.5.5 0 0 0 0-.708zm.646 6.061L9.793 2.5 3.293 9H3.5a.5.5 0 0 1 .5.5v.5h.5a.5.5 0 0 1 .5.5v.5h.5a.5.5 0 0 1 .5.5v.5h.5a.5.5 0 0 1 .5.5v.207zm-7.468 7.468A.5.5 0 0 1 6 13.5V13h-.5a.5.5 0 0 1-.5-.5V12h-.5a.5.5 0 0 1-.5-.5V11h-.5a.5.5 0 0 1-.5-.5V10h-.5a.5.5 0 0 1-.175-.032l-.179.178a.5.5 0 0 0-.11.168l-2 5a.5.5 0 0 0 .65.65l5-2a.5.5 0 0 0 .168-.11z",
    i = { stroke: "#000", "stroke-width": "1" };
  return (
    s.attr({ d: o, ...i }),
    a
      .attr({
        xmlns: n,
        width: e,
        height: e,
        fill: "currentColor",
        viewBox: "0 0 16 16",
      })
      .append(s),
    a
  );
}
function qa(e) {
  const n = t(document.createElement("button"));
  return (
    n
      .addClass(
        "btn btn-light urlStringBtnUpdate tabbable flex-column justify-center fourty-p-width fourty-p-height",
      )
      .attr({
        type: "button",
        "data-bs-toggle": "tooltip",
        "data-bs-custom-class": "urlStringBtnUpdate-tooltip",
        "data-bs-placement": "top",
        "data-bs-trigger": "hover",
        "data-bs-title": `${c.strings.EDIT_URL_TOOLTIP}`,
      })
      .disableTab()
      .onExact("click", function (a) {
        Wt(e, n);
      })
      .append(Dt()),
    S.Tooltip.getOrCreateInstance(n),
    n
  );
}
function Xa() {
  t("#confirmModal").modal("hide").removeClass("deleteUrlModal");
}
function Ya(e, n, a) {
  const s = "Are you sure you want to delete this URL from the UTub?",
    o = `${c.strings.DELETE_URL_WARNING}`,
    i = "Just kidding",
    r = "Delete URL";
  t("#confirmModalTitle").text(s),
    t("#confirmModalBody").text(o),
    t("#modalDismiss")
      .offAndOn("click", function (l) {
        l.preventDefault(), Xa();
      })
      .text(i),
    t("#modalSubmit")
      .offAndOn("click", function (l) {
        l.preventDefault(), Qa(e, n, a);
      })
      .text(r),
    t("#confirmModal")
      .addClass("deleteUrlModal")
      .modal("show")
      .on("hidden.bs.modal", () => {
        t("#confirmModal").removeClass("deleteUrlModal");
      }),
    t("#modalRedirect").hide(),
    t("#modalRedirect").hideClass();
}
function Ka(e, n) {
  return c.routes.deleteURL(e, n);
}
async function Qa(e, n, a) {
  try {
    await ee(a, e, n);
    const s = Ka(a, e),
      o = T("delete", s, []);
    o.done(function (i, r, l) {
      l.status === 200 && Za(i, n);
    }),
      o.fail(function (i, r, l) {
        es(i);
      });
  } catch (s) {
    te(s, n, { showError: !1 });
  }
}
function Za(e, n) {
  t("#confirmModal").modal("hide"),
    m({ urls: p().urls.filter((s) => s.utubUrlID !== e.URL.utubUrlID) });
  const a = n.attr("data-utub-url-tag-ids") || "";
  if (a.trim()) {
    let s = a.split(",").map((l) => l.trim()),
      o,
      i,
      r;
    for (let l = 0; l < s.length; l++)
      (i = s[l]),
        (o = t(`.tagFilter[data-utub-tag-id=${i}] .tagAppliedToUrlsCount`)),
        (r = o.text().split(" / ")),
        !(!r || r.length !== 2) &&
          o.text(`${parseInt(r[0]) - 1} / ${parseInt(r[1]) - 1}`);
  }
  n.fadeOut("slow", function () {
    n.remove(),
      t("#listURLs .urlRow").length === 0
        ? (t("#accessAllURLsBtn").hideClass(),
          t("#NoURLsSubheader").showClassFlex(),
          t("#urlBtnDeckCreateWrap").showClassFlex())
        : fe();
  });
}
function es(e) {
  if (!e._429Handled) {
    if (
      e.status === 403 &&
      e.getResponseHeader("Content-Type") === "text/html; charset=utf-8"
    ) {
      t("body").html(e.responseText);
      return;
    }
    switch (e.status) {
      default:
        window.location.assign(c.routes.errorPage);
    }
  }
}
function ts() {
  const e = "28px",
    n = "http://www.w3.org/2000/svg",
    a = t(document.createElementNS(n, "svg")),
    s = t(document.createElementNS(n, "path")).attr({ fill: "none" }),
    o = t(document.createElementNS(n, "path")),
    i = "M0 0h24v24H0V0z",
    r =
      "M16 9v10H8V9h8m-1.5-6h-5l-1 1H5v2h14V4h-3.5l-1-1zM18 7H6v12c0 1.1.9 2 2 2h8c1.1 0 2-.9 2-2V7z";
  return (
    s.attr({ d: i }),
    o.attr({ d: r }),
    a
      .attr({
        xmlns: n,
        width: e,
        height: e,
        fill: "currentColor",
        class: "bi bi-trash urlDeleteSvgIcon",
        viewBox: "0 0 24 24",
      })
      .append(s)
      .append(o),
    a
  );
}
function ns(e, n, a) {
  const s = t(document.createElement("button"));
  return (
    s
      .addClass(
        "btn btn-danger urlBtnDelete tabbable flex-column justify-center fourty-p-width fourty-p-height",
      )
      .attr({
        type: "button",
        "data-bs-toggle": "tooltip",
        "data-bs-custom-class": "urlBtnDelete-tooltip",
        "data-bs-placement": "top",
        "data-bs-trigger": "hover",
        "data-bs-title": `${c.strings.DELETE_URL_TOOLTIP}`,
      })
      .disableTab()
      .onExact("click", function (o) {
        Ya(e.utubUrlID, n, a);
      })
      .append(ts()),
    S.Tooltip.getOrCreateInstance(s),
    s
  );
}
function as(e, n, a) {
  const s = t(document.createElement("div")).addClass(
    "urlOptions justify-content-start flex-row gap-15p",
  );
  s.append(Va(e)).append(Ba(n)).append(ja(e)),
    e.canDelete && s.append(qa(n)).append(ns(e, n, a));
  const o = t(document.createElement("div")).addClass("urlCardDualLoadingRing");
  return s.append(o), s;
}
function ss(e, n, a, s) {
  const o = e.find(".urlTitle"),
    i = e.find(".urlString");
  o.text() !== n.urlTitle && o.text(n.urlTitle),
    i.attr("href") !== n.urlString &&
      i.text(n.urlString).attr({ href: n.urlString });
  const r = e.find(".tagBadge"),
    l = t.map(r, (f) => parseInt(t(f).attr("data-utub-tag-id")));
  for (let f = 0; f < l.length; f++)
    n.utubUrlTagIDs.includes(l[f]) ||
      r.each(function (D, Qe) {
        if (parseInt(t(Qe).attr("data-utub-tag-id")) === l[f])
          return t(Qe).remove(), !1;
      });
  const u = e.find(".urlTagsContainer");
  let d;
  for (let f = 0; f < n.utubUrlTagIDs.length; f++)
    l.includes(n.utubUrlTagIDs[f]) ||
      ((d = a.find((D) => D.id === n.utubUrlTagIDs[f])),
      u.append(be(d.id, d.tagString, e, s)));
}
function He(e, n, a) {
  const s = t(document.createElement("div"))
      .addClass("urlRow flex-column full-width pad-in-15p pointerable")
      .enableTab(),
    o = t(document.createElement("div")).addClass(
      "flex-row full-width align-center jc-sb",
    );
  return (
    e.canDelete ? o.append(Da(e.urlTitle, s, a)) : o.append(ht(e.urlTitle)),
    o.append(Ra(e.urlString)),
    s
      .append(o)
      .attr({
        utubUrlID: e.utubUrlID,
        urlSelected: !1,
        filterable: !0,
        "data-utub-url-tag-ids": e.utubUrlTagIDs.join(","),
      }),
    e.canDelete ? s.append(to(e.urlString, s, a)) : s.append(zt(e.urlString)),
    s.append(os(e, n, s, a)),
    Xt(s),
    kt(s),
    s
  );
}
function kt(e) {
  const n = e.attr("utuburlid");
  e.offAndOn("focus.focusURLCard" + n, function () {
    e.find(".goToUrlIcon").addClass("visible-on-focus"),
      t(document).on("keyup.focusURLCard" + n, function (a) {
        a.key === b.ENTER && (v(e), e.trigger("focusout"));
      });
  }),
    e.offAndOn("focusout.focusURLCard" + n, function (a) {
      const s = t(a.target);
      s.closest(".urlRow").is(e) &&
        (s.hasClass("goToUrlIcon") &&
          e.find(".goToUrlIcon").removeClass("visible-on-focus"),
        t(document).off("keyup.focusURLCard" + n));
    });
}
function os(e, n, a, s) {
  const o = t(document.createElement("div")).addClass(
      "tagsAndButtonsWrap full-width",
    ),
    i = t(document.createElement("div")).addClass("urlTags flex-column"),
    r = Wa(n, e.utubUrlTagIDs, a, s);
  return o.append(i), i.append(r), i.append(Ia(a, s)), o.append(as(e, a, s)), o;
}
function is(e, n) {
  const a = e.find("#urlSubmitBtnCreate"),
    s = e.find("#urlCancelBtnCreate"),
    o = e.find("#urlTitleCreate"),
    i = e.find("#urlStringCreate");
  t(a).onExact("click.createURL", function (l) {
    xt(o, i, n);
  }),
    t(s).onExact("click.createURL", function (l) {
      It();
    });
  const r = [i, o];
  for (let l = 0; l < r.length; l++)
    t(r[l]).on("focus.createURL", function () {
      ls(t(r[l]), i, o, n);
    }),
      t(r[l]).on("blur.createURL", function () {
        cs(t(r[l]));
      });
}
function At() {
  yt(),
    t("#urlSubmitBtnCreate").off(),
    t("#urlCancelBtnCreate").off(),
    t(document).off(".createURL"),
    t("#urlTitleCreate").off(".createURL"),
    t("#urlStringCreate").off(".createURL");
}
async function Bt(e) {
  const n = await J(e),
    a = n.name,
    s = n.description;
  rs(n.id, a, s);
  const o = n.urls,
    i = n.tags,
    r = n.members;
  X(g.STALE_DATA_DETECTED, { utubID: n.id, urls: o, tags: i, members: r }),
    m({ urls: o, tags: i, members: r });
}
function rs(e, n, a) {
  const s = $("#URLDeckHeader"),
    o = $("UTubSelector[utubid=" + e + "] > .UTubName"),
    i = $("#URLDeckSubheader");
  s.text() !== n && (s.text(n), o.text(n)), i.text() !== a && i.text(a);
}
function ls(e, n, a, s) {
  t(e).on("keydown.createURL", function (o) {
    if (!o.originalEvent.repeat)
      switch (o.key) {
        case b.ENTER:
          xt(a, n, s);
          break;
        case b.ESCAPE:
          It();
          break;
      }
  });
}
function cs(e) {
  t(e).off(".createURL");
}
function Pe() {
  t("#urlTitleCreate").val(null),
    t("#urlStringCreate").val(null),
    t("#createURLWrap").hideClass(),
    At(),
    t("#urlBtnCreate").showClassNormal();
}
function It() {
  Pe(),
    Fe() ||
      (t("#NoURLsSubheader").showClassNormal(),
      t("#urlBtnDeckCreateWrap").showClassFlex());
}
function et(e) {
  Fe() ||
    (t("#NoURLsSubheader").hideClass(), t("#urlBtnDeckCreateWrap").hideClass());
  const n = t("#createURLWrap");
  n.showClassFlex(),
    is(n, e),
    t("#urlTitleCreate").trigger("focus"),
    t("#urlBtnCreate").hideClass(),
    t("#urlBtnDeckCreateWrap").hideClass();
}
function us(e, n, a) {
  const s = c.routes.createURL(a),
    o = e.val(),
    r = { urlString: n.val(), urlTitle: o };
  return [s, r];
}
function xt(e, n, a) {
  let s, o;
  if ((([s, o] = us(e, n, a)), !it(o.urlString) && !rt(o.urlString))) {
    Ot({ urlString: [c.strings.INVALID_URL] });
    return;
  }
  const i = setTimeout(function () {
      t("#urlCreateDualLoadingRing").addClass("dual-loading-ring");
    }, we),
    r = T("post", s, o, 35e3);
  r.done(function (l, u, d) {
    d.status === 200 && ds(l, a);
  }),
    r.fail(function (l, u, d) {
      yt(), fs(l, a);
    }),
    r.always(function () {
      clearTimeout(i),
        t("#urlCreateDualLoadingRing").removeClass("dual-loading-ring");
    });
}
function ds(e, n) {
  Pe();
  const a = e.URL;
  (a.utubUrlTagIDs = []),
    (a.canDelete = !0),
    m({
      urls: [
        ...p().urls,
        {
          utubUrlID: a.utubUrlID,
          urlString: a.urlString,
          urlTitle: a.urlTitle,
          utubUrlTagIDs: [],
          canDelete: !0,
        },
      ],
    });
  const s = Ut(),
    o = He(a, [], n).addClass("even");
  t("#accessAllURLsBtn").showClassNormal(),
    o.insertAfter(t("#createURLWrap")),
    s === 0 || kn(),
    ut() ? o.attr({ filterable: !1 }) : v(o);
}
function fs(e, n) {
  if (e._429Handled) return;
  if (!e.hasOwnProperty("responseJSON")) {
    if (
      e.status === 403 &&
      e.getResponseHeader("Content-Type") === "text/html; charset=utf-8"
    ) {
      t("body").html(e.responseText);
      return;
    }
    ie("urlString", "Server timed out while validating URL. Try again later.");
    return;
  }
  const a = e.responseJSON,
    s = a.hasOwnProperty("errors"),
    o = a.hasOwnProperty("message");
  switch (e.status) {
    case 400:
      a !== void 0 && o && (s ? Ot(a.errors) : ie("urlString", a.message));
      break;
    case 409:
      a.hasOwnProperty("urlString") && (bt(a.urlString) || Bt(n)),
        ie("urlString", a.message);
      break;
    default:
      window.location.assign(c.routes.errorPage);
  }
}
function Ot(e) {
  for (let n in e)
    switch (n) {
      case "urlString":
      case "urlTitle":
        let a = e[n][0];
        ie(n, a);
    }
}
function ie(e, n) {
  t("#" + e + "Create-error")
    .addClass("visible")
    .text(n),
    t("#" + e + "Create").addClass("invalid-field");
}
function yt() {
  ["urlString", "urlTitle"].forEach((n) => {
    t("#" + n + "Create").removeClass("invalid-field"),
      t("#" + n + "Create-error").removeClass("visible");
  });
}
function bs(e) {
  const n = "#urlBtnCreate",
    a = "#urlBtnDeckCreate",
    s = t(n),
    o = t(a);
  s.offAndOnExact("click", function (i) {
    et(e);
  }),
    o.offAndOnExact("click", function (i) {
      et(e);
    });
}
function ps() {
  Pe(), At(), t(".urlRow").remove(), t("#urlBtnCreate").hideClass(), E();
}
function ms() {
  t("#urlBtnCreate").hideClass(),
    t("#NoURLsSubheader").hideClass(),
    t("#urlBtnDeckCreateWrap").hideClass(),
    t("#updateUTubDescriptionBtn")
      .removeClass("visibleBtn")
      .addClass("hiddenBtn");
}
function gs(e) {
  const a = t("#URLDeckErrorIndicator"),
    s = "URLDeckErrorIndicatorShow";
  a.text(e).addClass(s).trigger("focus"),
    setTimeout(() => {
      a.removeClass(s);
    }, 1e3 * 3.5);
}
function Ts(e, n, a) {
  const s = p().urls.map((d) => d.utubUrlID),
    o = t.map(e, (d) => d.utubUrlID),
    { toRemove: i, toAdd: r, toUpdate: l } = Ae(s, o);
  i.forEach((d) => {
    const f = t(".urlRow[utuburlid=" + d + "]");
    f.fadeOut("fast", function () {
      f.remove();
    });
  });
  const u = t("#listURLs");
  r.forEach((d) => {
    u.append(
      He(
        e.find((f) => f.utubUrlID === d),
        n,
        a,
      ),
    );
  }),
    l.forEach((d) => {
      const f = t(".urlRow[utuburlid=" + d + "]");
      ss(
        f,
        e.find((D) => D.utubUrlID === d),
        n,
        a,
      );
    });
}
function Us(e, n, a, s) {
  ps(), bs(e), Eo(e), po(e);
  const o = t("#listURLs");
  if ((a.length ? a.length : 0) !== 0) {
    for (let r = 0; r < a.length; r++)
      o.append(He(a[r], s, e).addClass(r % 2 === 0 ? "even" : "odd"));
    t("#accessAllURLsBtn").showClassNormal(),
      t("#NoURLsSubheader").hideClass(),
      t("#urlBtnDeckCreateWrap").hideClass();
  } else
    t("#NoURLsSubheader").showClassNormal(),
      t("#urlBtnDeckCreateWrap").showClassFlex(),
      t("#accessAllURLsBtn").hideClass();
  t("#urlBtnCreate").showClassNormal(), Zt(n);
}
function hs() {
  t(".urlRow").remove(),
    t("#URLDeckHeader").text("URLs"),
    t(".updateUTubBtn").hideClass(),
    t("#urlBtnCreate").hideClass(),
    t("#accessAllURLsBtn").hideClass(),
    t("#utubNameBtnUpdate").hideClass(),
    t("#updateUTubDescriptionBtn")
      .removeClass("visibleBtn")
      .addClass("hiddenBtn"),
    Te();
  const e = t("#URLDeckSubheader");
  e.text(`${c.strings.UTUB_SELECT}`),
    e.show(),
    t("#UTubDescriptionSubheaderWrap").removeClass("hidden"),
    t("#utubNameBtnUpdate").removeClass("visibleBtn");
}
function Cs() {
  wa();
}
h(g.UTUB_SELECTED, ({ utubID: e, utubName: n, urls: a, tags: s }) =>
  Us(e, n, a, s),
);
h(g.STALE_DATA_DETECTED, ({ urls: e, tags: n, utubID: a }) => Ts(e, n, a));
h(g.UTUB_DELETED, () => ms());
function pe() {
  se(),
    _e(),
    Sa(),
    hs(),
    Ie(),
    Be(),
    t(".dynamic-subheader").removeClass("height-2p5rem"),
    t(".sidePanelTitle").addClass("pad-b-0-25rem"),
    t(".UTubSelector.active").removeClass("active").removeClass("focus"),
    t(".UTubSelector:focus").blur();
}
function Ce() {
  pe(),
    Ko().then((e) => {
      Jo(e.utubs), Ie(), _e();
    });
}
function Ss() {
  const e = "24px",
    n = "http://www.w3.org/2000/svg",
    a = t(document.createElementNS(n, "svg")),
    s = t(document.createElementNS(n, "path")),
    o = t(document.createElement("button"));
  return (
    s.attr({
      "fill-rule": "evenodd",
      d: "M1 14s-1 0-1-1 1-4 6-4 6 3 6 4-1 1-1 1zm5-6a3 3 0 1 0 0-6 3 3 0 0 0 0 6m6.146-2.854a.5.5 0 0 1 .708 0L14 6.293l1.146-1.147a.5.5 0 0 1 .708.708L14.707 7l1.147 1.146a.5.5 0 0 1-.708.708L14 7.707l-1.146 1.147a.5.5 0 0 1-.708-.708L13.293 7l-1.147-1.146a.5.5 0 0 1 0-.708",
    }),
    a
      .attr({
        xmlns: n,
        width: e,
        height: e,
        fill: "currentColor",
        class: "bi bi-person-x-fill pointerable",
        viewBox: "0 0 16 16",
      })
      .append(s),
    o
      .append(a)
      .addClass("memberOtherBtnDelete flex-row align-center")
      .enableTab(),
    o
  );
}
function vs(e, n, a) {
  t("#memberSelfBtnDelete").offAndOnExact("click.removeMember", function (s) {
    se(), ne(), ve(n, e, a);
  });
}
function Ls() {
  t("#confirmModal").modal("hide");
}
function ve(e, n, a) {
  const s = n
      ? "Are you sure you want to remove this member from the UTub?"
      : "Are you sure you want to leave this UTub?",
    o = n
      ? `${c.strings.MEMBER_DELETE_WARNING}`
      : `${c.strings.MEMBER_LEAVE_WARNING}`,
    i = n ? "Keep member" : "Stay in UTub",
    r = n ? "Remove member" : "Leave UTub";
  t("#confirmModalTitle").text(s),
    t("#confirmModalBody").text(o),
    t("#modalDismiss")
      .addClass("btn btn-secondary")
      .offAndOn("click", function (l) {
        l.preventDefault(), Ls();
      })
      .text(i),
    t("#modalSubmit")
      .removeClass()
      .addClass("btn btn-danger")
      .text(r)
      .offAndOn("click", function (l) {
        l.preventDefault(), ws(e, n, a);
      })
      .text(r),
    t("#confirmModal").modal("show"),
    t("#modalRedirect").hide();
}
function Es(e, n) {
  return c.routes.removeMember(n, e);
}
function ws(e, n, a) {
  let s = Es(e, a),
    o = T("delete", s, []);
  o.done(function (i, r, l) {
    l.status === 200 && (n ? Rs(e) : Ds(a));
  }),
    o.fail(function (i, r, l) {
      ks(i);
    });
}
function Rs(e) {
  t("#confirmModal").modal("hide"),
    m({ members: p().members.filter((a) => a.id !== e) });
  const n = t("span[memberid=" + e + "]");
  n.fadeOut("slow", function () {
    n.remove();
  }),
    xe(),
    he() === 0 && je();
}
function Ds(e) {
  t("#confirmModal").modal("hide"),
    t("#memberSelfBtnDelete").hideClass(),
    t("#confirmModal").modal("hide"),
    pe();
  const n = t(".UTubSelector[utubid=" + e + "]");
  n.fadeOut("slow", function () {
    n.remove(), Ue();
  }),
    setTimeout(function () {
      window.history.pushState(null, null, "/home"),
        window.history.replaceState(null, null, "/home");
    }, 0);
}
function ks(e) {
  if (!e._429Handled) {
    if (
      e.status === 403 &&
      e.getResponseHeader("Content-Type") === "text/html; charset=utf-8"
    ) {
      t("body").html(e.responseText);
      return;
    }
    switch (e.status) {
      default:
        window.location.assign(c.routes.errorPage);
    }
  }
}
function As(e, n) {
  const a = document.createElement("span");
  return (
    t(a)
      .attr({ memberid: e })
      .addClass("member full-width flex-row flex-start align-center")
      .html("<b>" + n + "</b>"),
    a
  );
}
function We(e, n, a, s) {
  const o = t(document.createElement("span"));
  if (
    (t(o)
      .attr({ memberid: e })
      .addClass("member full-width flex-row jc-sb align-center flex-start")
      .html("<b>" + n + "</b>"),
    a)
  ) {
    const i = Ss();
    i.offAndOnExact("click.removeMember", function (r) {
      ve(e, a, s);
    }),
      t(o).append(i);
  } else
    t("#memberSelfBtnDelete").offAndOnExact("click.removeMember", function (i) {
      se(), ne(), ve(e, a, s);
    });
  return o;
}
function Bs(e) {
  const n = t("#memberBtnCreate");
  n.offAndOn("click.createMember", function () {
    tt(e);
  }),
    n.offAndOn("focus", function () {
      n.on("keydown.createMember", function (a) {
        a.key === b.ENTER && tt(e);
      });
    }),
    n.offAndOn("blur", function () {
      n.off(".createMember");
    });
}
function Is(e) {
  const n = t("#memberSubmitBtnCreate"),
    a = t("#memberCancelBtnCreate");
  n.offAndOnExact("click.createMemberSubmit", function (o) {
    Mt(e);
  }),
    a.offAndOnExact("click.createMemberEscape", function (o) {
      Z();
    });
  const s = t("#memberCreate");
  s.on("focus.createMemberSubmitEscape", function () {
    Os(e, s);
  }),
    s.on("blur.createMemberSubmitSubmitEscape", function () {
      ys();
    });
}
function xs() {
  t("#memberCreate").off(".createMemberSubmitEscape");
}
function Os(e, n) {
  n.on("keydown.createMemberSubmitEscape", function (a) {
    if (!a.originalEvent.repeat)
      switch (a.key) {
        case b.ENTER:
          Mt(e);
          break;
        case b.ESCAPE:
          Z();
          break;
      }
  });
}
function ys() {
  t("#memberCreate").off(".createMemberSubmitEscape");
}
function Nt() {
  t("#memberCreate").val(null);
}
function tt(e) {
  t("#createMemberWrap").showClassFlex(),
    t("#displayMemberWrap").hideClass(),
    t("#memberBtnCreate").hideClass(),
    Is(e),
    t("#memberCreate").trigger("focus");
}
function Z() {
  t("#createMemberWrap").hideClass(),
    t("#displayMemberWrap").showClassFlex(),
    t("#memberBtnCreate").showClassNormal(),
    xs(),
    Ft(),
    Nt();
}
function Ns(e) {
  const n = c.routes.createMember(e),
    s = { username: t("#memberCreate").val() };
  return [n, s];
}
function Mt(e) {
  let n, a;
  ([n, a] = Ns(e)), Ft();
  const s = T("post", n, a);
  s.done(function (o, i, r) {
    r.status === 200 && Ms(o, e);
  }),
    s.fail(function (o, i, r) {
      _s(o);
    });
}
function Ms(e, n) {
  Nt(),
    m({ members: [...p().members, e.member] }),
    t("#listMembers").append(We(e.member.id, e.member.username, !0, n)),
    Z(),
    xe(!0);
}
function _s(e) {
  if (!e._429Handled) {
    if (!e.hasOwnProperty("responseJSON")) {
      if (
        e.status === 403 &&
        e.getResponseHeader("Content-Type") === "text/html; charset=utf-8"
      ) {
        t("body").html(e.responseText);
        return;
      }
      window.location.assign(c.routes.errorPage);
      return;
    }
    switch (e.status) {
      case 400:
        const n = e.responseJSON,
          a = n.hasOwnProperty("errors"),
          s = n.hasOwnProperty("message");
        if (a) {
          Fs(n.errors);
          break;
        } else if (s) {
          _t("username", n.message);
          break;
        }
      default:
        window.location.assign(c.routes.errorPage);
    }
  }
}
function Fs(e) {
  for (let n in e)
    if (n === "username") {
      let a = e[n][0];
      _t(n, a);
      return;
    }
}
function _t(e, n) {
  t("#memberCreate-error").addClass("visible").text(n),
    t("#memberCreate").addClass("invalid-field");
}
function Ft() {
  ["member"].forEach((n) => {
    t("#" + n + "Create-error").removeClass("visible"),
      t("#" + n + "Create").removeClass("invalid-field");
  });
}
const F = ".deck#UTubDeck",
  H = ".deck#MemberDeck",
  P = ".deck#TagDeck",
  L = [F, H, P];
function Hs() {
  R() ? Ht() : Ws();
}
function Ht() {
  t("#UTubDeckHeaderAndCaret").removeClass("clickable"),
    t("#MemberDeckHeaderAndCaret").removeClass("clickable"),
    t("#TagDeckHeaderAndCaret").removeClass("clickable");
}
function Ps() {
  t("#UTubDeckHeaderAndCaret").addClass("clickable"),
    t("#MemberDeckHeaderAndCaret").addClass("clickable"),
    t("#TagDeckHeaderAndCaret").addClass("clickable");
}
function Ws() {
  $s(), zs(), Vs();
}
function Gs() {
  const e = t("#UTubDeckHeaderAndCaret .title-caret");
  e.hasClass("closed") &&
    (e.removeClass("closed"), t(F).removeClass("collapsed"));
  const n = t("#MemberDeckHeaderAndCaret .title-caret");
  if (n.hasClass("closed")) {
    n.removeClass("closed"),
      t(H).removeClass("collapsed"),
      k() || t("#MemberDeck > .sidePanelTitle").addClass("pad-b-0-25rem");
    return;
  }
  const a = t("#TagDeckHeaderAndCaret .title-caret");
  if (a.hasClass("closed")) {
    a.removeClass("closed"),
      t(P).removeClass("collapsed"),
      k() || t("#TagDeck > .sidePanelTitle").addClass("pad-b-0-25rem");
    return;
  }
}
function $s() {
  const e = t("#UTubDeckHeaderAndCaret");
  e.hasClass("clickable") || e.addClass("clickable"),
    e.offAndOn("click.collapsibleUTubDeck", () => {
      if (R()) return;
      const n = t("#UTubDeckHeaderAndCaret .title-caret");
      if (n.hasClass("closed")) {
        n.removeClass("closed"), t(F).removeClass("collapsed");
        return;
      }
      const a = Ge();
      n.addClass("closed"),
        t(F).addClass("collapsed"),
        G(),
        k() && ae(),
        a >= 2 && $e(),
        ze(F);
    });
}
function zs() {
  const e = t("#MemberDeckHeaderAndCaret");
  e.hasClass("clickable") || e.addClass("clickable"),
    e.offAndOn("click.collapsibleMemberDeck", () => {
      if (R()) return;
      const n = t("#MemberDeckHeaderAndCaret .title-caret");
      if (n.hasClass("closed")) {
        n.removeClass("closed"),
          t(H).removeClass("collapsed"),
          k() || t("#MemberDeck > .sidePanelTitle").addClass("pad-b-0-25rem");
        return;
      }
      const a = Ge();
      n.addClass("closed"),
        t(H).addClass("collapsed"),
        k() && Z(),
        t("#MemberDeck > .sidePanelTitle").removeClass("pad-b-0-25rem"),
        a >= 2 && $e(),
        ze(H);
    });
}
function Vs() {
  const e = t("#TagDeckHeaderAndCaret");
  e.hasClass("clickable") || e.addClass("clickable"),
    e.offAndOn("click.collapsibleUTubTagDeck", () => {
      if (R()) return;
      const n = t("#TagDeckHeaderAndCaret .title-caret");
      if (n.hasClass("closed")) {
        n.removeClass("closed"),
          t(P).removeClass("collapsed"),
          k() || t("#TagDeck > .sidePanelTitle").addClass("pad-b-0-25rem");
        return;
      }
      const a = Ge();
      n.addClass("closed"),
        t(P).addClass("collapsed"),
        k() && K(),
        t("#TagDeck > .sidePanelTitle").removeClass("pad-b-0-25rem"),
        a >= 2 && $e(),
        ze(P);
    });
}
function Ge() {
  let e = 0;
  for (let n = 0; n < L.length; n++) t(L[n]).hasClass("collapsed") && (e += 1);
  return e;
}
function $e(e) {
  let n;
  for (let s = 0; s < L.length; s++)
    if (t(L[s]).attr("data-last-collapsed") === "true") {
      n = L[s];
      break;
    }
  const a = t(n);
  a.find(".title-caret").first().removeClass("closed"),
    a.removeClass("collapsed");
}
function ze(e) {
  for (let n = 0; n < L.length; n++)
    e === L[n]
      ? t(e).attr("data-last-collapsed", "true")
      : t(L[n]).attr("data-last-collapsed", "false");
}
function R() {
  return t(window).width() < A;
}
function Js() {
  h(g.UTUB_SELECTED, () => {
    R() && y();
  }),
    matchMedia("(max-width: " + A + "px)").addEventListener(
      "change",
      function () {
        t(window).width() < A
          ? (Gs(), p().activeUTubID !== null ? y() : Pt(), Ht())
          : (Ys(), Ps());
      },
    );
}
function y() {
  t(".panel#leftPanel").addClass("hidden"),
    t(".panel#centerPanel").addClass("visible-flex"),
    t("button#toUTubs").removeClass("hidden"),
    t("button#toMembers").removeClass("hidden"),
    t("button#toTags").removeClass("hidden"),
    t("button#toURLs").addClass("hidden"),
    t(".deck#MemberDeck").removeClass("visible-flex"),
    t(".deck#TagDeck").removeClass("visible-flex"),
    w.toggler.hide();
}
function Pt() {
  t("button#toUTubs").addClass("hidden"),
    t("button#toMembers").addClass("hidden"),
    t("button#toTags").addClass("hidden"),
    t("button#toURLs").addClass("hidden"),
    t(".panel#centerPanel").removeClass("visible-flex"),
    t(".deck#MemberDeck").removeClass("visible-flex"),
    t(".deck#TagDeck").removeClass("visible-flex"),
    t(".deck#UTubDeck").removeClass("hidden"),
    w.toggler.hide();
}
function js() {
  t("button#toUTubs").addClass("hidden"),
    t("button#toMembers").removeClass("hidden"),
    t("button#toTags").removeClass("hidden"),
    t("button#toURLs").removeClass("hidden"),
    t(".panel#leftPanel").removeClass("hidden"),
    t(".panel#centerPanel").removeClass("visible-flex"),
    t(".deck#MemberDeck").removeClass("visible-flex"),
    t(".deck#TagDeck").removeClass("visible-flex"),
    t(".deck#UTubDeck").removeClass("hidden"),
    w.toggler.hide(),
    t(".UTubSelector.active").length && Mo(t(".UTubSelector.active"));
}
function qs() {
  t("button#toMembers").addClass("hidden"),
    t(".deck#MemberDeck").addClass("visible-flex").removeClass("hidden"),
    t(".panel#leftPanel").removeClass("hidden"),
    t(".panel#centerPanel").removeClass("visible-flex"),
    t(".deck#UTubDeck").addClass("hidden"),
    t(".deck#TagDeck").removeClass("visible-flex").addClass("hidden"),
    t("button#toUTubs").removeClass("hidden"),
    t("button#toTags").removeClass("hidden"),
    t("button#toURLs").removeClass("hidden"),
    w.toggler.hide();
}
function Xs() {
  t("button#toTags").addClass("hidden"),
    t(".deck#TagDeck").addClass("visible-flex").removeClass("hidden"),
    t(".panel#leftPanel").removeClass("hidden"),
    t(".panel#centerPanel").removeClass("visible-flex"),
    t(".deck#UTubDeck").addClass("hidden"),
    t(".deck#MemberDeck").removeClass("visible-flex").addClass("hidden"),
    t("button#toUTubs").removeClass("hidden"),
    t("button#toTags").addClass("hidden"),
    t("button#toURLs").removeClass("hidden"),
    t("button#toMembers").removeClass("hidden"),
    w.toggler.hide();
}
function Ys() {
  w.toggler.hide(),
    t("button#toUTubs").addClass("hidden"),
    t("button#toMembers").addClass("hidden"),
    t("button#toTags").addClass("hidden"),
    t("button#toURLs").addClass("hidden"),
    t(".panel#centerPanel").removeClass("hidden"),
    t(".panel#leftPanel").removeClass("hidden"),
    t(".deck#UTubDeck").removeClass("hidden"),
    t(".deck#MemberDeck").removeClass("hidden"),
    t(".deck#TagDeck").removeClass("hidden");
}
function Wt(e, n) {
  e.find(".urlString").hideClass();
  const a = e.find(".updateUrlStringWrap");
  ue(a),
    a.showClassFlex(),
    R() && a.find("input").focus(),
    setTimeout(function () {
      q(a.find("input"));
    }, 100),
    e.find(".urlBtnAccess").hideClass(),
    e.find(".urlTagBtnCreate").hideClass(),
    e.find(".urlBtnDelete").hideClass(),
    e.find(".urlBtnCopy").hideClass(),
    e.find(".goToUrlIcon").removeClass("visible-flex").addClass("hidden"),
    e.find(".tagBadge").removeClass("tagBadgeHoverable");
  const s = S.Tooltip.getInstance(n);
  s && (s.hide(), s.disable()),
    n
      .removeClass("urlStringBtnUpdate fourty-p-width")
      .addClass("urlStringCancelBigBtnUpdate")
      .text("Cancel")
      .offAndOnExact("click", function (o) {
        N(e), s && s.enable();
      }),
    wt(e),
    ge(e);
}
function N(e) {
  const n = e.find(".updateUrlStringWrap");
  n.hideClass(), Re(n);
  const a = e.find(".urlString");
  a.showClassNormal(), e.find(".urlStringUpdate").val(a.attr("href"));
  const s = e.find(".urlStringCancelBigBtnUpdate");
  s
    .removeClass("urlStringCancelBigBtnUpdate")
    .addClass("urlStringBtnUpdate")
    .offAndOnExact("click", function (i) {
      Wt(e, s);
    })
    .text("")
    .append(Dt()),
    s.addClass("fourty-p-width"),
    e.find(".urlBtnAccess").showClassFlex(),
    e.find(".urlTagBtnCreate").showClassFlex(),
    e.find(".urlBtnDelete").showClassFlex(),
    e.find(".urlBtnCopy").showClassFlex();
  const o = e.attr("urlSelected");
  typeof o == "string" &&
    o.toLowerCase() === "true" &&
    e.find(".goToUrlIcon").removeClass("hidden").addClass("visible-flex"),
    e.find(".tagBadge").addClass("tagBadgeHoverable"),
    $t(e),
    Rt(e),
    me(e);
}
function Ks(e, n, a) {
  const s = c.routes.updateURL(n, a),
    i = { urlString: e.val().trim() };
  return [s, i];
}
async function Gt(e, n, a) {
  const s = parseInt(n.attr("utuburlid"));
  let o;
  try {
    o = de(n);
    const i = await ee(a, s, n);
    let r, l;
    if (
      (([r, l] = Ks(e, a, s)),
      l.urlString === n.find(".urlString").attr("href"))
    ) {
      N(n), U(o, n);
      return;
    }
    if (!it(l.urlString) && !rt(l.urlString)) {
      W("urlString", c.strings.INVALID_URL, n), U(o, n);
      return;
    }
    const u = T("patch", r, l, 35e3);
    u.done(function (d, f, D) {
      D.status === 200 && Qs(d, n);
    }),
      u.fail(function (d, f, D) {
        $t(n), Zs(d, n, a);
      }),
      u.always(function () {
        U(o, n);
      });
  } catch (i) {
    U(o, n),
      te(i, n, { showError: !0, message: "Another user has deleted this URL" });
  }
}
function Qs(e, n) {
  const a = e.URL.urlString;
  m({
    urls: p().urls.map((s) =>
      s.utubUrlID === e.URL.utubUrlID
        ? {
            ...s,
            urlString: e.URL.urlString,
            urlTitle: e.URL.urlTitle,
            utubUrlTagIDs: e.URL.urlTags.map((o) => o.tagID),
          }
        : s,
    ),
  }),
    n.find(".urlString").attr({ href: a }).text(a),
    n.find(".urlBtnAccess").offAndOnExact("click", function (s) {
      B(a);
    }),
    n.find(".goToUrlIcon").offAndOnExact("click", function (s) {
      B(a);
    }),
    n.find(".urlBtnCopy").offAndOnExact("click", function (s) {
      lt(a, this);
    }),
    N(n);
}
function Zs(e, n, a) {
  if (e._429Handled) return;
  if (!e.hasOwnProperty("responseJSON")) {
    if (
      e.status === 403 &&
      e.getResponseHeader("Content-Type") === "text/html; charset=utf-8"
    ) {
      t("body").html(e.responseText);
      return;
    }
    W("urlString", "Server timed out while validating URL. Try again later.");
    return;
  }
  const s = e.responseJSON,
    o = s.hasOwnProperty("errors"),
    i = s.hasOwnProperty("message");
  switch (e.status) {
    case 400:
      if (o) {
        eo(s.errors, n);
        break;
      }
      if (i) {
        W("urlString", s.message, n);
        break;
      }
    case 409:
      s.hasOwnProperty("urlString") && (bt(s.urlString) || Bt(a)),
        W("urlString", s.message, n);
      break;
    default:
      window.location.assign(c.routes.errorPage);
  }
}
function eo(e, n) {
  for (let a in e)
    if (a === "urlString") {
      let s = e[a][0];
      W(a, s, n);
      return;
    }
}
function W(e, n, a) {
  a
    .find("." + e + "Update-error")
    .addClass("visible")
    .text(n),
    a.find("." + e + "Update").addClass("invalid-field");
}
function $t(e) {
  ["urlString"].forEach((a) => {
    e.find("." + a + "Update").removeClass("invalid-field"),
      e.find("." + a + "Update-error").removeClass("visible");
  });
}
function zt(e) {
  const n = Vt(e);
  return t(document.createElement("a"))
    .addClass("urlString long-text-ellipsis tabbable")
    .attr({ href: e, target: "_blank" })
    .text(n)
    .offAndOn("click.defaultlinkbehavior", function (a) {
      a.preventDefault(),
        t(a.target).closest(".urlRow").attr("urlSelected") === "true" && B(e);
    });
}
function to(e, n, a) {
  const s = t(document.createElement("div")).addClass(
    "flex-row ninetyfive-width",
  );
  return s.append(zt(e)).append(no(e, n, a)), s;
}
function no(e, n, a) {
  const s = Ke("urlString", De.UPDATE.description, st.URL.description).addClass(
    "updateUrlStringWrap hidden gap-5p",
  );
  s.find("label").text("URL");
  const o = s
    .find("input")
    .prop("minLength", c.constants.URLS_MIN_LENGTH)
    .prop("maxLength", c.constants.URLS_MAX_LENGTH)
    .val(e);
  ao(o, n, a);
  const i = Xe(30).addClass("urlStringSubmitBtnUpdate");
  i.onExact("click.updateUrlString", function () {
    Gt(o, n, a);
  });
  const r = Ye(30).addClass("urlStringCancelBtnUpdate");
  return (
    r.onExact("click.updateUrlString", function (l) {
      N(n);
    }),
    s.append(i).append(r),
    s
  );
}
function ao(e, n, a) {
  e.offAndOn("focus.updateURLStringFocus", function () {
    t(document).offAndOn("keyup.updateURLStringFocus", function (s) {
      switch (s.key) {
        case b.ENTER:
          Gt(e, n, a);
          break;
        case b.ESCAPE:
          N(n);
          break;
      }
    });
  }),
    e.offAndOn("blur.updateURLStringFocus", function () {
      t(document).off("keyup.updateURLStringFocus");
    });
}
function Vt(e) {
  return e.replace(/^(?:https?:\/\/)?(?:www\.)?/, "");
}
async function ee(e, n, a) {
  return new Promise((s, o) => {
    t.ajax({
      url: c.routes.getURL(e, n),
      type: "GET",
      dataType: "json",
      success: (i, r, l) => {
        l.status === 200 && i.hasOwnProperty("URL") && (so(i.URL, a, e), s()),
          s(l);
      },
      error: (i, r, l) => {
        o(i);
      },
    });
  });
}
function so(e, n, a) {
  const s = n.find(".urlTitle"),
    o = n.find(".urlString"),
    i = n.find(".tagBadge");
  if (
    (s !== e.urlTitle && s.text(e.urlTitle), o.attr("href") !== e.urlString)
  ) {
    const r = Vt(e.urlString);
    o.attr({ href: e.urlString }).text(r);
  }
  oo(i, e.urlTags, n, a);
}
function oo(e, n, a, s) {
  const o = n.map((d) => d.utubTagID);
  let i = [];
  e.each(function () {
    const d = parseInt(t(this).attr("data-utub-tag-id"));
    o.includes(d) || (t(this).remove(), i.push(d));
  });
  for (let d = 0; d < i.length; d++) Se(i[d]) || Ea(i[d]);
  let r, l, u;
  for (let d = 0; d < n.length; d++) {
    (r = !1), (l = n[d]);
    for (
      let f = 0;
      f < e.length &&
      ((u = e[f]),
      (r = parseInt(t(u).attr("data-utub-tag-id")) === l.utubTagID),
      !r);
      f++
    );
    r ||
      (a.find(".urlTagsContainer").append(be(l.utubTagID, l.tagString, a, s)),
      Se(l.utubTagID) || t("#listTags").append(Y(s, l.utubTagID, l.tagString)));
  }
}
function te(e, n, a) {
  switch (e.status) {
    case 429:
      let s = e.getResponseHeader("Content-Type");
      s && s.includes("text/html") && Ee(e.responseText);
      break;
    case 403:
      window.location.assign(c.routes.errorPage);
      break;
    case 404:
      if (e.getResponseHeader("content-type").indexOf("text/html") >= 0) {
        window.location.assign(c.routes.errorPage);
        break;
      }
      a.showError && gs(a.message), io(n);
      break;
    default:
      window.location.assign(c.routes.errorPage);
      break;
  }
}
function io(e) {
  t("#confirmModal").modal("hide"),
    e.fadeOut("slow", function () {
      e.remove(),
        t("#listURLs .urlRow").length === 0
          ? t("#accessAllURLsBtn").hide()
          : fe();
    });
}
function ro(e, n) {
  e.hideClass();
  const a = e.siblings(".updateUrlTitleWrap");
  a.showClassFlex(),
    a.find("input").trigger("focus"),
    n.find(".tagBadge").removeClass("tagBadgeHoverable"),
    ge(n);
}
function V(e) {
  e.find(".updateUrlTitleWrap").hideClass(),
    e.find(".urlTitleAndUpdateIconWrap").showClassFlex(),
    e.find(".urlTitleUpdate").val(e.find(".urlTitle").text()),
    e.find(".tagBadge").addClass("tagBadgeHoverable"),
    Jt(e),
    me(e);
}
function lo(e, n, a) {
  const s = c.routes.updateURLTitle(n, a),
    i = { urlTitle: e.val() };
  return [s, i];
}
async function nt(e, n, a) {
  const s = parseInt(n.attr("utuburlid"));
  let o;
  try {
    if (
      ((o = de(n)), await ee(a, s, n), e.val() === n.find(".urlTitle").text())
    ) {
      V(n), U(o, n);
      return;
    }
    let i, r;
    [i, r] = lo(e, a, s);
    const l = T("patch", i, r);
    l.done(function (u, d, f) {
      f.status === 200 &&
        (Jt(n),
        u.hasOwnProperty("URL") &&
          u.URL.hasOwnProperty("urlTitle") &&
          co(u, n));
    }),
      l.fail(function (u, d, f) {
        uo(u, n);
      }),
      l.always(function () {
        U(o, n);
      });
  } catch (i) {
    U(o, n),
      te(i, n, { showError: !0, message: "Another user has deleted this URL" });
  }
}
function co(e, n) {
  const a = e.URL.urlTitle;
  m({
    urls: p().urls.map((s) =>
      s.utubUrlID === e.URL.utubUrlID
        ? {
            ...s,
            urlString: e.URL.urlString,
            urlTitle: e.URL.urlTitle,
            utubUrlTagIDs: e.URL.urlTags.map((o) => o.tagID),
          }
        : s,
    ),
  }),
    n.find(".urlTitle").text(a),
    V(n);
}
function uo(e, n) {
  if (!e._429Handled) {
    if (!e.hasOwnProperty("responseJSON")) {
      if (
        e.status === 403 &&
        e.getResponseHeader("Content-Type") === "text/html; charset=utf-8"
      ) {
        t("body").html(e.responseText);
        return;
      }
      window.location.assign(c.routes.errorPage);
      return;
    }
    switch (e.status) {
      case 400:
        const a = e.responseJSON;
        if (a.hasOwnProperty("errors")) {
          fo(a.errors, n);
          break;
        }
      default:
        window.location.assign(c.routes.errorPage);
    }
  }
}
function fo(e, n) {
  for (let a in e)
    if (a === "urlTitle") {
      let s = e[a][0];
      bo(a, s, n);
      return;
    }
}
function bo(e, n, a) {
  a
    .find("." + e + "Update-error")
    .addClass("visible")
    .text(n),
    a.find("." + e + "Update").addClass("invalid-field");
}
function Jt(e) {
  ["urlTitle"].forEach((a) => {
    e.find("." + a + "Update").removeClass("invalid-field"),
      e.find("." + a + "Update-error").removeClass("visible");
  });
}
function jt() {
  const e = p().selectedURLCardID;
  return e !== null ? t(`.urlRow[utuburlid=${e}]`) : null;
}
function v(e) {
  ne(),
    m({ selectedURLCardID: parseInt(e.attr("utuburlid")) }),
    e.attr({ urlSelected: !0 }),
    e.find(".goToUrlIcon").addClass("visible-flex"),
    me(e),
    An(e);
}
function me(e) {
  e.on("click.deselectURL", (n) => {
    const a = [
      ".urlTagBtnCreate",
      ".urlStringBtnUpdate",
      ".urlStringCancelBtnUpdate",
      ".urlTagCancelBtnCreate",
      ".urlTitleCancelBtnUpdate",
      ".urlTagBtnDelete",
      ".urlBtnCopy",
      ".goToUrlIcon",
      ".urlBtnAccess",
      ".urlBtnDelete",
    ];
    for (let s = 0; s < a.length; s++)
      if (t(n.target).closest(a[s]).length) return;
    qt(e);
  });
}
function ge(e) {
  e.off("click.deselectURL");
}
function qt(e) {
  ge(e),
    m({ selectedURLCardID: null }),
    e.attr({ urlSelected: !1 }),
    e.find(".urlString").off("click.goToURL"),
    e.find(".goToUrlIcon").removeClass("visible-flex hidden visible-on-focus"),
    V(e),
    N(e),
    Q(e),
    Bn(e),
    Xt(e),
    kt(e),
    e.blur();
}
function ne() {
  const e = jt();
  e !== null && qt(e);
}
function Xt(e) {
  e.offAndOn("click.urlSelected", function (n) {
    t(n.target).parents(".urlRow").length &&
      t(n.target).closest(".urlRow").attr("urlSelected") !== "true" &&
      v(e);
  });
}
function Yt(e, n) {
  ln().includes(e) ? mo(n) : Qt(n);
}
function po(e) {
  t("#utubNameBtnUpdate").offAndOn("click", function (s) {
    ne(), E(e), To(e), t(s.target).is(this);
  });
  const n = t("#utubNameSubmitBtnUpdate"),
    a = t("#utubNameCancelBtnUpdate");
  n.offAndOnExact("click.updateUTubname", function (s) {
    if (t("#URLDeckHeader").text() === t("#utubNameUpdate").val()) {
      C();
      return;
    }
    Yt(t("#utubNameUpdate").val(), e);
  }),
    a.offAndOnExact("click.updateUTubname", function (s) {
      C();
    });
}
function Le(e) {
  t("#utubNameUpdate")
    .offAndOn("focus.updateUTubname", function () {
      t("#utubNameUpdate").on("keydown.updateUTubname", function (n) {
        if (!n.originalEvent.repeat)
          switch (n.key) {
            case b.ENTER:
              if (t("#URLDeckHeader").text() === t("#utubNameUpdate").val()) {
                C();
                return;
              }
              Yt(t("#utubNameUpdate").val(), e);
              break;
            case b.ESCAPE:
              C();
              break;
          }
      });
    })
    .offAndOn("blur.updateUTubname", function () {
      t("#utubNameUpdate").off("keyup.updateUTubname");
    }),
    t(window).offAndOn("click.updateUTubname", function (n) {
      t(n.target).closest("#utubNameBtnUpdate").length ||
        t(n.target).is(t("#utubNameUpdate")) ||
        t(n.target).closest(t("#utubNameSubmitBtnUpdate").length) ||
        t(n.target).closest(t("#utubNameCancelBtnUpdate").length) ||
        C();
    });
}
function Kt() {
  t(window).off(".updateUTubname"), t("#utubNameUpdate").off(".updateUTubname");
}
function mo(e) {
  const n = "Continue with this UTub name?",
    a = `${c.strings.UTUB_UPDATE_SAME_NAME}`,
    s = "Go Back to Editing",
    o = "Edit Name";
  let i = !1;
  Kt(),
    t("#confirmModalTitle").text(n),
    t("#confirmModalBody").text(a),
    t("#modalDismiss")
      .addClass("btn btn-secondary")
      .text(s)
      .offAndOnExact("click", function (r) {
        r.preventDefault(),
          cn(),
          Le(e),
          setTimeout(function () {
            q(t("#utubNameUpdate"));
          }, 300);
      }),
    t("#modalRedirect").hideClass(),
    t("#modalRedirect").hide(),
    t("#modalSubmit")
      .removeClass()
      .addClass("btn btn-success")
      .text(o)
      .offAndOnExact("click", function (r) {
        (i = !0), Qt(e);
      }),
    t("#confirmModal").modal("show"),
    t("#confirmModal").offAndOn("hidden.bs.modal", function (r) {
      r.stopPropagation(), Le(e), i || q(t("#utubNameUpdate"));
    });
}
function go(e) {
  const n = t("#URLDeckSubheaderCreateDescription");
  n.showClassNormal(),
    n.offAndOnExact("click.createUTubdescription", function (a) {
      n.removeClass("opa-1 height-2rem").addClass("opa-0 height-0"),
        C(),
        Je(e),
        n.off("click.createUTubdescription");
    });
}
function To(e) {
  Le(e);
  const n = t("#utubNameUpdate");
  n.closest(".titleElement").addClass("m-top-bot-0-5rem"),
    n.val(Yo()),
    mn("#utubNameUpdate"),
    n.trigger("focus"),
    t("#URLDeckHeader").hideClass(),
    t("#utubNameBtnUpdate").hideClass(),
    t("#urlBtnCreate").hideClass(),
    t("#utubNameBtnUpdate").removeClass("visibleBtn"),
    t("#URLDeckSubheader").text().length === 0 && go(e);
}
function C() {
  gn("#utubNameUpdate"),
    t("#utubNameUpdate")
      .closest(".titleElement")
      .removeClass("m-top-bot-0-5rem"),
    t("#URLDeckHeader").showClassNormal(),
    t("#utubNameBtnUpdate").showClassNormal(),
    t("#urlBtnCreate").showClassNormal(),
    Kt(),
    t("#utubNameBtnUpdate").addClass("visibleBtn"),
    t("#URLDeckSubheader").text().length === 0 &&
      t("#URLDeckSubheaderCreateDescription")
        .removeClass("opa-1 height-2rem")
        .addClass("opa-0 height-0"),
    Lo(),
    t("#utubNameUpdate").val(t("#URLDeckHeader").text());
}
function Qt(e) {
  if (t("#URLDeckHeader").text() === t("#utubNameUpdate").val()) {
    C();
    return;
  }
  let n, a;
  [n, a] = Uo(e);
  let s = T("patch", n, a);
  s.done(function (o, i, r) {
    r.status === 200 && ho(o);
  }),
    s.fail(function (o, i, r) {
      Co(o);
    });
}
function Uo(e) {
  const n = c.routes.updateUTubName(e);
  let s = { utubName: t("#utubNameUpdate").val() };
  return [n, s];
}
function ho(e) {
  const n = e.utubName;
  m({
    activeUTubName: e.utubName,
    utubs: p().utubs.map((s) =>
      s.id === e.utubID ? { ...s, name: e.utubName } : s,
    ),
  }),
    t("#confirmModal").modal("hide"),
    t("#listUTubs").find(".active").find(".UTubName").text(n),
    Zt(n);
}
function Co(e) {
  if (!e._429Handled) {
    if (!e.hasOwnProperty("responseJSON")) {
      if (
        e.status === 403 &&
        e.getResponseHeader("Content-Type") === "text/html; charset=utf-8"
      ) {
        t("body").html(e.responseText);
        return;
      }
      window.location.assign(c.routes.errorPage);
      return;
    }
    switch (e.status) {
      case 400:
        const n = e.responseJSON;
        if (n.hasOwnProperty("message")) {
          n.hasOwnProperty("errors") && So(n.errors);
          break;
        }
      default:
        window.location.assign(c.routes.errorPage);
    }
  }
}
function So(e) {
  for (let n in e)
    if (n === "utubName") {
      let a = e[n][0];
      vo(n, a);
      return;
    }
}
function vo(e, n) {
  t("#" + e + "Update-error")
    .addClass("visible")
    .text(n),
    t("#" + e + "Update").addClass("invalid-field");
}
function Lo() {
  ["utubName"].forEach((n) => {
    t("#" + n + "Update-error").removeClass("visible"),
      t("#" + n + "Update").removeClass("invalid-field");
  });
}
function Zt(e) {
  t("#URLDeckHeader").text(e), t("#utubNameUpdate").val(e), C();
}
function Eo(e) {
  const n = t("#utubDescriptionSubmitBtnUpdate"),
    a = t("#utubDescriptionCancelBtnUpdate");
  t("#updateUTubDescriptionBtn").offAndOnExact("click", function (s) {
    ne(), C(), Je(e);
  }),
    n.offAndOnExact("click", function (s) {
      en(e);
    }),
    a.onExact("click", function (s) {
      E(e);
    });
}
function wo(e) {
  t("#utubDescriptionUpdate")
    .offAndOn("focus.updateUTubDescription", function () {
      t("#utubDescriptionUpdate").on(
        "keyup.updateUTubDescription",
        function (n) {
          if (!n.originalEvent.repeat)
            switch (n.key) {
              case b.ENTER:
                en(e);
                break;
              case b.ESCAPE:
                E(e);
                break;
            }
        },
      );
    })
    .on("blur.updateUTubDescription", function () {
      t("#utubDescriptionUpdate").off("keyup.updateUTubDescription");
    }),
    t(window).offAndOn("click.updateUTubDescription", function (n) {
      t(n.target).closest("#updateUTubDescriptionBtn").length ||
        t(n.target).is(t("#utubDescriptionUpdate")) ||
        t(n.target).is(t("#URLDeckSubheaderCreateDescription")) ||
        t(n.target).closest(t("#utubDescriptionSubmitBtnUpdate").length) ||
        t(n.target).closest(t("#utubDescriptionCancelBtnUpdate").length) ||
        E(e);
    });
}
function Ro() {
  t(window).off(".updateUTubDescription"),
    t(document).off(".updateUTubDescription");
}
function Ve(e) {
  const n = t("#URLDeckHeader"),
    a = t("#URLDeckSubheaderCreateDescription");
  a.enableTab(),
    n.offAndOn("mouseenter.createUTubdescription", function (s) {
      a.removeClass("opa-0 height-0").addClass("opa-1 height-2rem"),
        a.offAndOnExact("click.createUTubdescription", function (o) {
          a.removeClass("opa-1 height-2rem").addClass("opa-0 height-0 width-0"),
            Je(e),
            a.off("click.createUTubdescription");
        }),
        Do();
    });
}
function Do() {
  const e = t("#URLDeckHeaderWrap"),
    n = t("#URLDeckSubheaderCreateDescription");
  e.offAndOn("mouseleave.createUTubdescription", function (a) {
    M(t(n)) ||
      (n.removeClass("opa-1 height-2rem").addClass("opa-0 height-0"),
      n.off("click.createUTubdescription"),
      e.off("mouseleave.createUTubdescription"));
  });
}
function Te() {
  t("#URLDeckHeader").off("mouseenter.createUTubdescription"),
    t("#URLDeckHeaderWrap").off("mouseleave.createUTubdescription");
}
function Je(e) {
  wo(e);
  const n = t("#utubDescriptionUpdate");
  n.val(t("#URLDeckSubheader").text()),
    mn("#utubDescriptionUpdate"),
    n.trigger("focus"),
    t("#utubDescriptionSubmitBtnUpdate").showClassNormal(),
    t("#updateUTubDescriptionBtn").removeClass("visibleBtn"),
    t("#UTubDescription").hideClass(),
    t("#updateUTubDescriptionBtn").hideClass(),
    t("#URLDeckSubheader").hideClass(),
    t("#URLDeckSubheaderCreateDescription").addClass("width-0"),
    Te();
}
function E(e = null) {
  gn("#utubDescriptionUpdate"),
    t("#utubDescriptionSubmitBtnUpdate").hideClass(),
    t("#updateUTubDescriptionBtn").addClass("visibleBtn"),
    Ro(),
    t("#URLDeckSubheader").showClassNormal(),
    t("#updateUTubDescriptionBtn").showClassNormal(),
    Oo(),
    t("#URLDeckSubheaderCreateDescription").removeClass("width-0"),
    !t("#URLDeckSubheader").text().length && e != null && Ve(e);
}
function en(e) {
  if (t("#URLDeckSubheader").text() === t("#utubDescriptionUpdate").val()) {
    E(e);
    return;
  }
  let n, a;
  [n, a] = ko(e);
  const s = T("patch", n, a);
  s.done(function (o, i, r) {
    r.status === 200 && Ao(o, e);
  }),
    s.fail(function (o, i, r) {
      Bo(o);
    });
}
function ko(e) {
  const n = c.routes.updateUTubDescription(e);
  let s = { utubDescription: t("#utubDescriptionUpdate").val() };
  return [n, s];
}
function Ao(e, n) {
  const a = e.utubDescription;
  m({ activeUTubDescription: e.utubDescription });
  const o = t("#URLDeckSubheader").text().length;
  t("#URLDeckSubheader").text(a),
    t("#utubDescriptionUpdate").val(a),
    a.length === 0
      ? (Ve(n),
        t("#UTubDescriptionSubheaderOuterWrap").removeClass("height-2rem"),
        t("#UTubDescriptionSubheaderWrap").hideClass(),
        t("#URLDeckSubheaderCreateDescription").enableTab())
      : o === 0 &&
        (Te(),
        t("#UTubDescriptionSubheaderOuterWrap").removeClass("height-2rem"),
        t("#UTubDescriptionSubheaderWrap").showClassFlex(),
        t("#URLDeckSubheaderCreateDescription").disableTab()),
    E();
}
function Bo(e) {
  if (!e._429Handled) {
    if (!e.hasOwnProperty("responseJSON")) {
      if (
        e.status === 403 &&
        e.getResponseHeader("Content-Type") === "text/html; charset=utf-8"
      ) {
        t("body").html(e.responseText);
        return;
      }
      window.location.assign(c.routes.errorPage);
      return;
    }
    switch (e.status) {
      case 400:
        const n = e.responseJSON;
        if (n.hasOwnProperty("message")) {
          n.hasOwnProperty("errors") && Io(n.errors);
          break;
        }
      default:
        window.location.assign(c.routes.errorPage);
    }
  }
}
function Io(e) {
  for (let n in e)
    if (n === "utubDescription") {
      let a = e[n][0];
      xo(n, a);
    }
}
function xo(e, n) {
  t("#" + e + "Update-error")
    .addClass("visible")
    .text(n),
    t("#" + e + "Update").addClass("invalid-field");
}
function Oo() {
  ["utubDescription"].forEach((n) => {
    t("#" + n + "Update-error").removeClass("visible"),
      t("#" + n + "Update").removeClass("invalid-field");
  });
}
function J(e) {
  const n = an(),
    a = t.Deferred();
  return (
    t
      .getJSON(c.routes.getUTub(e))
      .done(function (s) {
        a.resolve(s);
      })
      .fail(function (s) {
        if (s.status === 429) {
          Ee(s.responseText), a.resolve(null);
          return;
        } else window.history.replaceState(null, null, "/home"), a.reject(s);
      })
      .always(function () {
        sn(n);
      }),
    a.promise()
  );
}
function ce(e) {
  const n = e.description,
    a = e.isCreator;
  if (
    (m({
      activeUTubID: e.id,
      activeUTubName: e.name,
      activeUTubDescription: e.description,
      isCurrentUserOwner: e.isCreator,
      currentUserID: e.currentUser,
      utubOwnerID: e.createdByUserID,
      urls: e.urls,
      tags: e.tags,
      members: e.members,
      selectedTagIDs: [],
      selectedURLCardID: null,
    }),
    window.history.state === null ||
      JSON.stringify(window.history.state.UTubID) !== JSON.stringify(e.id))
  ) {
    const i = c.strings.UTUB_QUERY_PARAM;
    window.history.pushState({ UTubID: e.id }, "", `/home?${i}=${e.id}`),
      sessionStorage.setItem("fullyLoaded", "true");
  }
  X(g.UTUB_SELECTED, {
    utubID: e.id,
    utubName: e.name,
    urls: e.urls,
    tags: e.tags,
    members: e.members,
    utubOwnerID: e.createdByUserID,
    isCurrentUserOwner: e.isCreator,
    currentUserID: e.currentUser,
  }),
    jo(e.id, a);
  const o = t("#URLDeckSubheader");
  Te(),
    n
      ? (o.text(n),
        t("#UTubDescriptionSubheaderWrap").showClassFlex(),
        t("#URLDeckSubheaderCreateDescription").disableTab())
      : (a && Ve(e.id),
        o.text(null),
        t("#UTubDescriptionSubheaderWrap").hideClass()),
    a
      ? (t("#utubNameBtnUpdate")
          .removeClass("hiddenBtn")
          .addClass("visibleBtn"),
        t("#updateUTubDescriptionBtn")
          .removeClass("hiddenBtn")
          .addClass("visibleBtn"),
        t("#utubDescriptionUpdate").val(t("#URLDeckSubheader").text()))
      : (t("#utubNameBtnUpdate")
          .addClass("hiddenBtn")
          .removeClass("visibleBtn"),
        t("#updateUTubDescriptionBtn")
          .addClass("hiddenBtn")
          .removeClass("visibleBtn"));
}
function j(e, n) {
  const a = t(".UTubSelector.active");
  a.is(t(n)) || (a.removeClass("active"), n.addClass("active"), tn(e));
}
function tn(e) {
  J(e).then(
    (n) => {
      n && ce(n);
    },
    () => {
      window.location.assign(c.routes.errorPage);
    },
  );
}
function nn(e, n, a, s) {
  const o = t(document.createElement("span")),
    i = t(document.createElement("b"));
  return (
    i.addClass("UTubName").text(e),
    o
      .addClass("UTubSelector flex-row jc-sb align-center")
      .attr({ utubid: n, position: s, tabindex: 0 })
      .onExact("click.selectUTub", function (r) {
        j(n, o);
      })
      .offAndOnExact("focus.selectUTub", function (r) {
        o.on("keyup.selectUTub", function (l) {
          l.key === b.ENTER && j(n, o);
        });
      })
      .offAndOnExact("blur.selectUTub", function (r) {
        o.off("keyup.selectUTub");
      })
      .append(i)
      .append(No(a)),
    o
  );
}
function yo(e) {
  const n = t(e),
    a = n.attr("utubid");
  n.onExact("click.selectUTub", function (s) {
    j(a, n);
  })
    .offAndOnExact("focus.selectUTub", function (s) {
      n.on("keyup.selectUTub", function (o) {
        o.key === b.ENTER && j(a, n);
      });
    })
    .offAndOnExact("blur.selectUTub", function (s) {
      n.off("keyup.selectUTub");
    });
}
function No(e) {
  let n = "";
  switch (e) {
    case `${c.constants.MEMBER_ROLES.CREATOR}`:
      (n +=
        '<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" fill="currentColor" class="bi bi-diamond-fill memberRole" viewBox="0 0 16 16">'),
        (n +=
          '<path fill-rule="evenodd" d="M6.95.435c.58-.58 1.52-.58 2.1 0l6.515 6.516c.58.58.58 1.519 0 2.098L9.05 15.565c-.58.58-1.519.58-2.098 0L.435 9.05a1.48 1.48 0 0 1 0-2.098z"/>');
      break;
    case `${c.constants.MEMBER_ROLES.CO_CREATOR}`:
      (n +=
        '<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" fill="currentColor" class="bi bi-diamond-half memberRole" viewBox="0 0 16 16">'),
        (n +=
          '<path d="M9.05.435c-.58-.58-1.52-.58-2.1 0L.436 6.95c-.58.58-.58 1.519 0 2.098l6.516 6.516c.58.58 1.519.58 2.098 0l6.516-6.516c.58-.58.58-1.519 0-2.098zM8 .989c.127 0 .253.049.35.145l6.516 6.516a.495.495 0 0 1 0 .7L8.35 14.866a.5.5 0 0 1-.35.145z"/>');
      break;
    default:
      (n +=
        '<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" fill="currentColor" class="bi bi-people-fill memberRole" viewBox="0 0 16 16">'),
        (n +=
          '<path d="M7 14s-1 0-1-1 1-4 5-4 5 3 5 4-1 1-1 1zm4-6a3 3 0 1 0 0-6 3 3 0 0 0 0 6m-5.784 6A2.24 2.24 0 0 1 5 13c0-1.355.68-2.75 1.936-3.72A6.3 6.3 0 0 0 5 9c-4 0-5 3-5 4s1 1 1 1zM4.5 8a2.5 2.5 0 1 0 0-5 2.5 2.5 0 0 0 0 5"/>');
  }
  return (n += "</svg>"), n;
}
function Mo(e) {
  t(e).offAndOnExact("click.selectUTubMobile", function (n) {
    tn(t(this).attr("utubid")), t(this).off("click.selectUTubMobile");
  });
}
function _o(e) {
  const n = t("#utubBtnDelete");
  n.offAndOn("click.deleteUTub", function () {
    Ho(e);
  }),
    n.offAndOn("blur.deleteUTub", function () {
      n.off("keydown.deleteUTub");
    });
}
function Fo() {
  t("#confirmModal").modal("hide");
}
function Ho(e) {
  const n = "Are you sure you want to delete this UTub?",
    a = `${c.strings.UTUB_DELETE_WARNING}`,
    s = "Nevermind...",
    o = "Delete this sucka!";
  t("#confirmModalTitle").text(n),
    t("#confirmModalBody").text(a),
    t("#modalDismiss")
      .removeClass()
      .addClass("btn btn-secondary")
      .offAndOn("click", function (i) {
        i.preventDefault(), Fo();
      })
      .text(s),
    t("#modalSubmit")
      .removeClass()
      .addClass("btn btn-danger")
      .text(o)
      .offAndOn("click", function (i) {
        i.preventDefault(), Po(e), G();
      }),
    t("#confirmModal").modal("show"),
    t("#modalRedirect").hide();
}
function Po(e) {
  let n = Wo(e);
  const a = T("delete", n, []);
  a.done(function (s, o, i) {
    i.status === 200 && Go(e);
  }),
    a.fail(function (s, o, i) {
      $o(s);
    });
}
function Wo(e) {
  return c.routes.deleteUTub(e);
}
function Go(e) {
  se(), t("#confirmModal").modal("hide"), t("#utubBtnDelete").hideClass();
  const n = t(".UTubSelector[utubid=" + e + "]");
  setTimeout(function () {
    window.history.pushState(null, null, "/home"),
      window.history.replaceState(null, null, "/home");
  }, 0),
    n.fadeOut("slow", () => {
      n.remove(),
        m({
          utubs: p().utubs.filter((a) => a.id !== e),
          activeUTubID: null,
          activeUTubName: null,
          activeUTubDescription: null,
          isCurrentUserOwner: !1,
          urls: [],
          tags: [],
          members: [],
          selectedTagIDs: [],
          selectedURLCardID: null,
        }),
        pe(),
        Ue(),
        X(g.UTUB_DELETED, { utubID: e }),
        he() === 0 && (je(), t("#utubTagBtnCreate").hideClass()),
        R() && Pt();
    });
}
function $o(e) {
  if (!e._429Handled) {
    if (
      e.status === 403 &&
      e.getResponseHeader("Content-Type") === "text/html; charset=utf-8"
    ) {
      t("body").html(e.responseText);
      return;
    }
    window.location.assign(c.routes.errorPage);
  }
}
function an() {
  return setTimeout(function () {
    t("#UTubSelectDualLoadingRing").addClass("dual-loading-ring");
  }, we);
}
function sn(e) {
  clearTimeout(e),
    t("#UTubSelectDualLoadingRing").removeClass("dual-loading-ring");
}
function zo() {
  t(document).off(".createUTub");
}
function Vo() {
  t("#listUTubs").empty(), t("#utubBtnDelete").hideClass();
}
function Jo(e, n) {
  m({ utubs: e }), Vo();
  const a = t("#listUTubs"),
    s = e.length;
  if (s !== 0) {
    for (let o = 0; o < s; o++)
      a.append(nn(e[o].name, e[o].id, e[o].memberRole, o));
    Ue();
  } else je();
}
function on() {
  const e = t(".UTubSelector");
  for (let n = 0; n < e.length; n++) yo(e[n]);
  Wn();
}
function je() {
  t("#UTubDeckSubheader").text(`${c.strings.UTUB_CREATE_MSG}`),
    t("#utubBtnDelete").hideClass();
}
function Ue() {
  se();
  const e = he(),
    n = e > 1 ? e + " UTubs" : e + " UTub";
  t("#UTubDeckSubheader").text(n);
}
function jo(e, n) {
  Ue(),
    n
      ? (t("#utubBtnDelete").showClassNormal(), _o(e))
      : t("#utubBtnDelete").hideClass();
  const a = t(`.UTubSelector[utubid="${e}"]`);
  a.hasClass("active") ||
    (t(".UTubSelector.active").removeClass("active").removeClass("focus"),
    t(".UTubSelector:focus").blur(),
    a.addClass("active"));
}
function qo(e) {
  const n = parseInt(e),
    a = !isNaN(n),
    s = n > 0,
    o = String(n) === e;
  return a && s && o;
}
function Xo(e) {
  return rn(e);
}
function rn(e) {
  return t(`.UTubSelector[utubid='${e}']`).length === 1;
}
function he() {
  return t("#listUTubs > .UTubSelector").length;
}
function k() {
  return p().activeUTubID !== null;
}
function Yo() {
  return p().activeUTubName;
}
function ln() {
  return p().utubs.map((e) => e.name);
}
function Ko() {
  const e = an();
  return t.getJSON(c.routes.getUTubs).always(function () {
    sn(e);
  });
}
function cn() {
  t("#confirmModal").modal("hide");
}
function un(e) {
  ln().includes(e) ? ei() : dn();
}
function qe() {
  t("#utubBtnCreate").offAndOnExact("click.createUTub", function (n) {
    ti(), G();
  });
}
function Qo() {
  const e = t("#utubSubmitBtnCreate"),
    n = t("#utubCancelBtnCreate");
  e.offAndOnExact("click.createUTub", function (o) {
    un(t("#utubNameCreate").val());
  }),
    n.offAndOnExact("click.createUTub", function (o) {
      ae();
    });
  const a = t("#utubNameCreate"),
    s = t("#utubDescriptionCreate");
  a.on("focus.createUTub", function (o) {
    a.on("keydown.createUTubName", function (i) {
      i.originalEvent.repeat || at(i);
    });
  }),
    a.on("blur.createUTub", function () {
      a.off(".createUTubName");
    }),
    s.on("focus.createUTub", function () {
      s.on("keydown.createUTubDescription", function (o) {
        at(o);
      });
    }),
    s.on("blur.createUTub", function () {
      s.off(".createUTubDescription");
    });
}
function Zo() {
  t("#utubNameCreate").off("keydown.createUTubName"),
    t("#utubDescriptionCreate").off("keydown.createUTubDescription"),
    t("#utubNameCreate").off(".createUTub"),
    t("#utubDescriptionCreate").off(".createUTub"),
    t("#utubSubmitBtnCreate").off(".createUTub"),
    t("#utubCancelBtnCreate").off(".createUTub");
}
function at(e) {
  switch (e.key) {
    case b.ENTER:
      un(t("#utubNameCreate").val());
      break;
    case b.ESCAPE:
      t("#utubNameCreate").trigger("blur"),
        t("#utubDescriptionCreate").trigger("blur"),
        ae();
      break;
  }
}
function ei() {
  const e = "Create a new UTub with this name?",
    n = `${c.strings.UTUB_CREATE_SAME_NAME}`,
    a = "Go Back to Editing",
    s = "Create";
  t("#confirmModalTitle").text(e),
    t("#confirmModalBody").text(n),
    t("#modalDismiss")
      .addClass("btn btn-secondary")
      .text(a)
      .offAndOnExact("click", function (o) {
        o.preventDefault(), cn(), q(t("#utubNameCreate"));
      }),
    t("#modalRedirect").hideClass(),
    t("#modalRedirect").hide(),
    t("#modalSubmit")
      .removeClass()
      .addClass("btn btn-success")
      .text(s)
      .offAndOnExact("click", function (o) {
        o.preventDefault(),
          dn(),
          t("#utubNameCreate").val(null),
          t("#utubDescriptionCreate").val(null);
      }),
    t("#confirmModal").modal("show"),
    t("#confirmModal").on("hidden.bs.modal", function (o) {
      q(t("#utubNameCreate"));
    });
}
function ti() {
  t("#createUTubWrap").showClassFlex(),
    Qo(),
    t("#utubNameCreate").trigger("focus"),
    t("#listUTubs").hideClass(),
    t("#UTubDeck").find(".button-container").hideClass(),
    zo();
}
function ae() {
  t("#createUTubWrap").hideClass(),
    t("#listUTubs").showClassFlex(),
    t("#utubNameCreate").val(null),
    t("#utubDescriptionCreate").val(null),
    Zo(),
    fn(),
    t("#UTubDeck").find(".button-container").showClassFlex(),
    qe();
}
function ni() {
  const e = c.routes.createUTub,
    n = t("#utubNameCreate").val(),
    a = t("#utubDescriptionCreate").val();
  return [e, { utubName: n, utubDescription: a }];
}
function dn() {
  let e, n;
  ([e, n] = ni()), fn();
  let a = T("post", e, n);
  a.done(function (s, o, i) {
    i.status === 200 && (ai(s), t("#listUTubs").showClassNormal());
  }),
    a.fail(function (s, o, i) {
      si(s);
    });
}
function ai(e) {
  const n = e.utubID;
  m({
    utubs: [
      ...p().utubs,
      {
        id: e.utubID,
        name: e.utubName,
        memberRole: c.constants.MEMBER_ROLES.CREATOR,
      },
    ],
  }),
    t("#confirmModal").modal("hide"),
    ae();
  const a = parseInt(t(".UTubSelector").first().attr("position")),
    s = nn(e.utubName, n, c.constants.MEMBER_ROLES.CREATOR, a - 1);
  t("#listUTubs").prepend(s), j(n, s);
}
function si(e) {
  if (!e._429Handled) {
    if (!e.hasOwnProperty("responseJSON")) {
      if (
        e.status === 403 &&
        e.getResponseHeader("Content-Type") === "text/html; charset=utf-8"
      ) {
        t("body").html(e.responseText);
        return;
      }
      window.location.assign(c.routes.errorPage);
      return;
    }
    switch (e.status) {
      case 400:
        const n = e.responseJSON;
        if (n.hasOwnProperty("message")) {
          n.hasOwnProperty("errors") && oi(n.errors);
          break;
        }
      default:
        window.location.assign(c.routes.errorPage);
    }
  }
}
function oi(e) {
  for (let n in e)
    switch (n) {
      case "utubName":
      case "utubDescription":
        let a = e[n][0];
        ii(n, a);
    }
}
function ii(e, n) {
  t("#" + e + "Create-error")
    .addClass("visible")
    .text(n),
    t("#" + e + "Create").addClass("invalid-field");
}
function fn() {
  ["utubName", "utubDescription"].forEach((n) => {
    t("#" + n + "Create").removeClass("invalid-field"),
      t("#" + n + "Create-error").removeClass("visible");
  });
}
function bn(e) {
  const n = e.target.nextElementSibling;
  (n.style.top = "0px"), (n.style.left = "10px"), (n.style.fontSize = "14px");
}
function pn(e) {
  if (e.target.value === "") {
    const n = e.target.nextElementSibling;
    (n.style.top = "50%"), (n.style.left = "10px"), (n.style.fontSize = "16px");
  }
}
function ri(e) {
  const n = e.target.nextElementSibling;
  e.target.value === "" ? t(n).show() : t(n).hide();
}
function mn(e) {
  const a = t(e).closest(".createDiv");
  t(a).showClassFlex();
}
function q(e) {
  t(e).trigger("focus"),
    t(e).focus(),
    e[0].value && e[0].setSelectionRange(0, e[0].value.length);
}
function se() {
  M(t("#createUTubWrap")) || ae(),
    M(t("#URLDeckHeader")) && C(),
    M(t("#URLDeckSubheader")) &&
      t("#URLDeckSubheader").text().length !== 0 &&
      E(),
    M(t("#displayMemberWrap")) && Z();
}
function gn(e) {
  const a = t(e).closest(".createDiv");
  t(a).hideClass();
}
function li(e) {
  const n = t(document.createElement("button")),
    a =
      '<svg xmlns="http://www.w3.org/2000/svg" fill="currentColor" class="bi bi-pencil-square updateIcon" viewBox="0 0 16 16" width="' +
      e +
      '" height="' +
      e +
      '"><path d="M15.502 1.94a.5.5 0 0 1 0 .706L14.459 3.69l-2-2L13.502.646a.5.5 0 0 1 .707 0l1.293 1.293zm-1.75 2.456-2-2L4.939 9.21a.5.5 0 0 0-.121.196l-.805 2.414a.25.25 0 0 0 .316.316l2.414-.805a.5.5 0 0 0 .196-.12l6.813-6.814z"/><path fill-rule="evenodd" d="M1 13.5A1.5 1.5 0 0 0 2.5 15h11a1.5 1.5 0 0 0 1.5-1.5v-6a.5.5 0 0 0-1 0v6a.5.5 0 0 1-.5.5h-11a.5.5 0 0 1-.5-.5v-11a.5.5 0 0 1 .5-.5H9a.5.5 0 0 0 0-1H2.5A1.5 1.5 0 0 0 1 2.5z"/></svg>';
  return (
    n
      .addClass("mx-1 flex-row align-center")
      .attr({ style: "color: #545454" })
      .html(a),
    n
  );
}
function Xe(e) {
  const n = t(document.createElement("button")),
    a =
      '<svg xmlns="http://www.w3.org/2000/svg" fill="currentColor" class="bi bi-check-square-fill" viewBox="0 0 16 16" width="' +
      e +
      '" height="' +
      e +
      '"><path d="M2 0a2 2 0 0 0-2 2v12a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V2a2 2 0 0 0-2-2zm10.03 4.97a.75.75 0 0 1 .011 1.05l-3.992 4.99a.75.75 0 0 1-1.08.02L4.324 8.384a.75.75 0 1 1 1.06-1.06l2.094 2.093 3.473-4.425a.75.75 0 0 1 1.08-.022z"/></svg>';
  return n.addClass("px-1 my-2 green-clickable").html(a).enableTab(), n;
}
function Ye(e) {
  const n = t(document.createElement("button")),
    a =
      '<svg xmlns="http://www.w3.org/2000/svg" fill="currentColor" class="bi bi-x-square-fill cancelButton" viewBox="0 0 16 16" width="' +
      e +
      '" height="' +
      e +
      '"><path d="M2 0a2 2 0 0 0-2 2v12a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V2a2 2 0 0 0-2-2zm3.354 4.646L8 7.293l2.646-2.647a.5.5 0 0 1 .708.708L8.707 8l2.647 2.646a.5.5 0 0 1-.708.708L8 8.707l-2.646 2.647a.5.5 0 0 1-.708-.708L7.293 8 4.646 5.354a.5.5 0 1 1 .708-.708"/></svg>';
  return n.addClass("my-2 px-1").html(a).enableTab(), n;
}
function Ke(e, n, a = st.TEXT.description) {
  const s = t(document.createElement("div")).addClass(
      "createDiv flex-row full-width pad-top-5p",
    ),
    o = t(document.createElement("div")).addClass("text-input-container"),
    i = t(document.createElement("div")).addClass("text-input-inner-container"),
    r = t(document.createElement("input"))
      .addClass("text-input")
      .prop("required", !0),
    l = t(document.createElement("label")).addClass("text-input-label"),
    u = t(document.createElement("span")).addClass("text-input-error-message");
  return (
    r.attr({ type: a, name: e }).addClass(e + n),
    l.attr({ for: e }),
    u.addClass(e + n + "-error"),
    i.append(r).append(l),
    o.append(i).append(u),
    r.on("focus", bn).on("blur", pn),
    s.append(o),
    s
  );
}
function ci() {
  t("form").on("submit", function () {
    return !1;
  });
  const e = t(".text-input");
  let n;
  for (let a = 0; a < e.length; a++) {
    if (((n = t(e[a])), n.val(""), n.hasClass("search-input"))) {
      n.on("blur", ri);
      continue;
    }
    n.on("focus", bn), n.on("blur", pn);
  }
}
function ui() {
  window.addEventListener("popstate", di),
    window.addEventListener("pageshow", fi);
}
function di(e) {
  if (e.state && e.state.hasOwnProperty("UTubID")) {
    if (!rn(e.state.UTubID)) {
      window.history.replaceState(null, null, "/home"), Ce();
      return;
    }
    J(e.state.UTubID).then(
      (n) => {
        ce(n), t(window).width() < A && y();
      },
      () => {
        Ce();
      },
    );
  } else Ce();
}
function fi(e) {
  if ((on(), qe(), history.state && history.state.UTubID)) {
    J(history.state.UTubID).then(
      (s) => {
        ce(s), t(window).width() < A && y();
      },
      () => {},
    );
    return;
  }
  const n = new URLSearchParams(window.location.search);
  if (n.size === 0) {
    pe(), Ie(), _e();
    return;
  }
  const a = n.get(c.strings.UTUB_QUERY_PARAM);
  (n.size > 1 || a === null) && window.location.assign(c.routes.errorPage),
    qo(a) || window.location.assign(c.routes.errorPage),
    Xo(parseInt(a)) ||
      (window.history.replaceState(null, null, "/home"),
      window.location.assign(c.routes.errorPage)),
    J(parseInt(a)).then(
      (s) => {
        ce(s), t(window).width() < A && y();
      },
      () => {
        window.location.assign(c.routes.errorPage);
      },
    );
}
function bi() {
  t("#confirmModal").removeClass("accessAllUrlModal");
}
function pi() {
  const e = "Are you sure you want to open all " + Fe() + " URLs in this UTub?",
    n = "Performance issues may occur.",
    a = "Cancel";
  t("#confirmModalTitle").text(e),
    t("#confirmModalBody").text(n),
    t("#modalDismiss")
      .on("click", function (s) {
        s.preventDefault(), t("#confirmModal").modal("hide");
      })
      .removeClass()
      .addClass("btn btn-danger")
      .text(a),
    t("#modalSubmit")
      .removeClass()
      .addClass("btn btn-success")
      .on("click", function (s) {
        s.preventDefault(), Tn(), t("#confirmModal").modal("hide");
      })
      .text("Open all URLs"),
    t("#confirmModal")
      .modal("show")
      .addClass("accessAllUrlModal")
      .on("hidden.bs.modal", bi),
    t("#modalRedirect").hide(),
    t("#modalRedirect").hideClass();
}
function Tn() {
  const n = t(".urlRow[filterable=true] .urlString");
  if (n.length === 0) return;
  const a = t.map(n, (s) => t(s).attr("href"));
  for (let s = 0; s < a.length; s++) B(a[s]);
}
function mi() {
  t("#accessAllURLsBtn").on("click", function (e) {
    const n = c.constants.MAX_NUM_OF_URLS_TO_ACCESS;
    Ut() > n ? pi() : Tn();
  });
}
hn();
Cn();
t(document).ready(() => {
  const e = document.getElementById("utubs-data");
  e && m({ utubs: JSON.parse(e.textContent) }),
    ci(),
    Ln(),
    Mn(),
    Js(),
    Hs(),
    qe(),
    on(),
    sa(),
    Yn(),
    Cs(),
    mi(),
    Sn();
});
ui();
//# sourceMappingURL=main-Cg8HuBDd.js.map
