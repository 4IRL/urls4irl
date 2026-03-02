const o = window.jQuery,
  c = window.bootstrap,
  a = document.getElementById("app-config");
if (!a) throw new Error("App configuration not found in DOM");
const t = JSON.parse(a.textContent),
  u = Object.freeze({
    routes: Object.freeze({
      home: t.routes.home,
      createUTub: t.routes.createUTub,
      getUTubs: t.routes.getUTubs,
      login: t.routes.login,
      register: t.routes.register,
      confirmEmailAfterRegister: t.routes.confirmEmailAfterRegister,
      sendValidationEmail: t.routes.sendValidationEmail,
      forgotPassword: t.routes.forgotPassword,
      errorPage: t.routes.errorPage,
      logout: t.routes.logout,
      getUTub: (e) => t.routes.getUTub.replace("-1", e),
      deleteUTub: (e) => t.routes.deleteUTub.replace("-1", e),
      updateUTubName: (e) => t.routes.updateUTubName.replace("-1", e),
      updateUTubDescription: (e) =>
        t.routes.updateUTubDescription.replace("-1", e),
      getURL: (e, r) => t.routes.getURL.replace("-1", e).replace("-2", r),
      createURL: (e) => t.routes.createURL.replace("-1", e),
      deleteURL: (e, r) => t.routes.deleteURL.replace("-1", e).replace("-2", r),
      updateURL: (e, r) => t.routes.updateURL.replace("-1", e).replace("-2", r),
      updateURLTitle: (e, r) =>
        t.routes.updateURLTitle.replace("-1", e).replace("-2", r),
      createURLTag: (e, r) =>
        t.routes.createURLTag.replace("-1", e).replace("-2", r),
      deleteURLTag: (e, r, s) =>
        t.routes.deleteURLTag
          .replace("-1", e)
          .replace("-2", r)
          .replace("-3", s),
      createUTubTag: (e) => t.routes.createUTubTag.replace("-1", e),
      deleteUTubTag: (e, r) =>
        t.routes.deleteUTubTag.replace("-1", e).replace("-2", r),
      createMember: (e) => t.routes.createMember.replace("-1", e),
      removeMember: (e, r) =>
        t.routes.removeMember.replace("-1", e).replace("-4", r),
    }),
    constants: Object.freeze(t.constants),
    strings: Object.freeze(t.strings),
  });
function n() {
  o("[data-route]").each(function () {
    const e = o(this),
      r = e.data("route");
    e.on("click", () => {
      window.location.assign(u.routes[r]);
    });
  });
}
export { o as $, u as A, c as b, n as i };
//# sourceMappingURL=navbar-shared-gG1g8UXG.js.map
