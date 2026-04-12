/**
 * Application configuration
 * Reads config from JSON script element injected by Flask templates
 */

export type RouteId =
  | "home"
  | "login"
  | "register"
  | "confirmEmailAfterRegister"
  | "sendValidationEmail"
  | "forgotPassword"
  | "errorPage"
  | "logout"
  | "createUTub"
  | "getUTubs"
  | "contactUs";

export interface AppRoutes {
  // Static routes (string values)
  home: string;
  createUTub: string;
  getUTubs: string;
  login: string;
  register: string;
  confirmEmailAfterRegister: string;
  sendValidationEmail: string;
  forgotPassword: string;
  errorPage: string;
  logout: string;
  contactUs: string;

  // Dynamic single-param routes
  getUTub: (id: number) => string;
  deleteUTub: (id: number) => string;
  updateUTubName: (id: number) => string;
  updateUTubDescription: (id: number) => string;
  createURL: (id: number) => string;
  createUTubTag: (id: number) => string;
  createMember: (id: number) => string;

  // Dynamic two-param routes
  getURL: (utubId: number, urlId: number) => string;
  deleteURL: (utubId: number, urlId: number) => string;
  updateURL: (utubId: number, urlId: number) => string;
  updateURLTitle: (utubId: number, urlId: number) => string;
  createURLTag: (utubId: number, urlId: number) => string;
  deleteUTubTag: (utubId: number, tagId: number) => string;
  removeMember: (utubId: number, userId: number) => string;

  // Dynamic three-param routes
  deleteURLTag: (utubId: number, urlId: number, tagId: number) => string;
}

export interface AppConfig {
  readonly routes: Readonly<AppRoutes>;
  readonly constants: Readonly<Record<string, unknown>>;
  readonly strings: Readonly<Record<string, string>>;
}

const configScript: HTMLElement | null = document.getElementById("app-config");
if (!configScript) {
  throw new Error("App configuration not found in DOM");
}
const rawConfig: {
  routes: Record<string, string>;
  constants: Record<string, unknown>;
  strings: Record<string, string>;
} = (() => {
  if (!configScript.textContent) {
    throw new Error("App configuration script element is empty");
  }
  return JSON.parse(configScript.textContent);
})();

export const APP_CONFIG: AppConfig = Object.freeze({
  routes: Object.freeze({
    home: rawConfig.routes.home,
    createUTub: rawConfig.routes.createUTub,
    getUTubs: rawConfig.routes.getUTubs,
    login: rawConfig.routes.login,
    register: rawConfig.routes.register,
    confirmEmailAfterRegister: rawConfig.routes.confirmEmailAfterRegister,
    sendValidationEmail: rawConfig.routes.sendValidationEmail,
    forgotPassword: rawConfig.routes.forgotPassword,
    errorPage: rawConfig.routes.errorPage,
    logout: rawConfig.routes.logout,

    getUTub: (id: number) => rawConfig.routes.getUTub.replace("-1", String(id)),
    deleteUTub: (id: number) =>
      rawConfig.routes.deleteUTub.replace("-1", String(id)),
    updateUTubName: (id: number) =>
      rawConfig.routes.updateUTubName.replace("-1", String(id)),
    updateUTubDescription: (id: number) =>
      rawConfig.routes.updateUTubDescription.replace("-1", String(id)),

    getURL: (utubId: number, urlId: number) =>
      rawConfig.routes.getURL
        .replace("-1", String(utubId))
        .replace("-2", String(urlId)),
    createURL: (id: number) =>
      rawConfig.routes.createURL.replace("-1", String(id)),
    deleteURL: (utubId: number, urlId: number) =>
      rawConfig.routes.deleteURL
        .replace("-1", String(utubId))
        .replace("-2", String(urlId)),
    updateURL: (utubId: number, urlId: number) =>
      rawConfig.routes.updateURL
        .replace("-1", String(utubId))
        .replace("-2", String(urlId)),
    updateURLTitle: (utubId: number, urlId: number) =>
      rawConfig.routes.updateURLTitle
        .replace("-1", String(utubId))
        .replace("-2", String(urlId)),

    createURLTag: (utubId: number, urlId: number) =>
      rawConfig.routes.createURLTag
        .replace("-1", String(utubId))
        .replace("-2", String(urlId)),
    deleteURLTag: (utubId: number, urlId: number, tagId: number) =>
      rawConfig.routes.deleteURLTag
        .replace("-1", String(utubId))
        .replace("-2", String(urlId))
        .replace("-3", String(tagId)),

    createUTubTag: (id: number) =>
      rawConfig.routes.createUTubTag.replace("-1", String(id)),
    deleteUTubTag: (utubId: number, tagId: number) =>
      rawConfig.routes.deleteUTubTag
        .replace("-1", String(utubId))
        .replace("-2", String(tagId)),

    createMember: (id: number) =>
      rawConfig.routes.createMember.replace("-1", String(id)),
    removeMember: (utubId: number, userId: number) =>
      rawConfig.routes.removeMember
        .replace("-1", String(utubId))
        .replace("-4", String(userId)),

    contactUs: rawConfig.routes.contactUs,
  }),
  constants: Object.freeze(rawConfig.constants),
  strings: Object.freeze(rawConfig.strings),
}) as AppConfig;
