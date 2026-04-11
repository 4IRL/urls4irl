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

  // Index signature for dynamic key access (navbar-shared uses APP_CONFIG.routes[route])
  [key: string]: string | ((...args: number[]) => string);
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
const raw: {
  routes: Record<string, string>;
  constants: Record<string, unknown>;
  strings: Record<string, string>;
} = JSON.parse(configScript.textContent!);

export const APP_CONFIG: AppConfig = Object.freeze({
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

    getUTub: (id: number) => raw.routes.getUTub.replace("-1", String(id)),
    deleteUTub: (id: number) =>
      raw.routes.deleteUTub.replace("-1", String(id)),
    updateUTubName: (id: number) =>
      raw.routes.updateUTubName.replace("-1", String(id)),
    updateUTubDescription: (id: number) =>
      raw.routes.updateUTubDescription.replace("-1", String(id)),

    getURL: (utubId: number, urlId: number) =>
      raw.routes.getURL
        .replace("-1", String(utubId))
        .replace("-2", String(urlId)),
    createURL: (id: number) =>
      raw.routes.createURL.replace("-1", String(id)),
    deleteURL: (utubId: number, urlId: number) =>
      raw.routes.deleteURL
        .replace("-1", String(utubId))
        .replace("-2", String(urlId)),
    updateURL: (utubId: number, urlId: number) =>
      raw.routes.updateURL
        .replace("-1", String(utubId))
        .replace("-2", String(urlId)),
    updateURLTitle: (utubId: number, urlId: number) =>
      raw.routes.updateURLTitle
        .replace("-1", String(utubId))
        .replace("-2", String(urlId)),

    createURLTag: (utubId: number, urlId: number) =>
      raw.routes.createURLTag
        .replace("-1", String(utubId))
        .replace("-2", String(urlId)),
    deleteURLTag: (utubId: number, urlId: number, tagId: number) =>
      raw.routes.deleteURLTag
        .replace("-1", String(utubId))
        .replace("-2", String(urlId))
        .replace("-3", String(tagId)),

    createUTubTag: (id: number) =>
      raw.routes.createUTubTag.replace("-1", String(id)),
    deleteUTubTag: (utubId: number, tagId: number) =>
      raw.routes.deleteUTubTag
        .replace("-1", String(utubId))
        .replace("-2", String(tagId)),

    createMember: (id: number) =>
      raw.routes.createMember.replace("-1", String(id)),
    removeMember: (utubId: number, userId: number) =>
      raw.routes.removeMember
        .replace("-1", String(utubId))
        .replace("-4", String(userId)),

    contactUs: raw.routes.contactUs,
  }),
  constants: Object.freeze(raw.constants),
  strings: Object.freeze(raw.strings),
}) as AppConfig;
