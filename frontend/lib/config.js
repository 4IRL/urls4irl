/**
 * Application configuration
 * Reads config from JSON script element injected by Flask templates
 */

const configScript = document.getElementById("app-config");
if (!configScript) {
  throw new Error("App configuration not found in DOM");
}
const raw = JSON.parse(configScript.textContent);

export const APP_CONFIG = Object.freeze({
  routes: Object.freeze({
    home: raw.routes.home,
    createUTub: raw.routes.createUTub,
    getUTubs: raw.routes.getUTubs,
    login: raw.routes.login,
    register: raw.routes.register,
    confirmEmailAfterRegister: raw.routes.confirmEmailAfterRegister,
    sendValidationEmail: raw.routes.sendValidationEmail,
    forgotPassword: raw.routes.forgotPassword,
    errorPage: raw.routes.errorPage,
    logout: raw.routes.logout,

    getUTub: (id) => raw.routes.getUTub.replace("-1", id),
    deleteUTub: (id) => raw.routes.deleteUTub.replace("-1", id),
    updateUTubName: (id) => raw.routes.updateUTubName.replace("-1", id),
    updateUTubDescription: (id) =>
      raw.routes.updateUTubDescription.replace("-1", id),

    getURL: (utubId, urlId) =>
      raw.routes.getURL.replace("-1", utubId).replace("-2", urlId),
    createURL: (id) => raw.routes.createURL.replace("-1", id),
    deleteURL: (utubId, urlId) =>
      raw.routes.deleteURL.replace("-1", utubId).replace("-2", urlId),
    updateURL: (utubId, urlId) =>
      raw.routes.updateURL.replace("-1", utubId).replace("-2", urlId),
    updateURLTitle: (utubId, urlId) =>
      raw.routes.updateURLTitle.replace("-1", utubId).replace("-2", urlId),

    createURLTag: (utubId, urlId) =>
      raw.routes.createURLTag.replace("-1", utubId).replace("-2", urlId),
    deleteURLTag: (utubId, urlId, tagId) =>
      raw.routes.deleteURLTag
        .replace("-1", utubId)
        .replace("-2", urlId)
        .replace("-3", tagId),

    createUTubTag: (id) => raw.routes.createUTubTag.replace("-1", id),
    deleteUTubTag: (utubId, tagId) =>
      raw.routes.deleteUTubTag.replace("-1", utubId).replace("-2", tagId),

    createMember: (id) => raw.routes.createMember.replace("-1", id),
    removeMember: (utubId, userId) =>
      raw.routes.removeMember.replace("-1", utubId).replace("-4", userId),
  }),
  constants: Object.freeze(raw.constants),
  strings: Object.freeze(raw.strings),
});
