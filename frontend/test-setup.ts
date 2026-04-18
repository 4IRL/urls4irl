import jquery from "jquery";

// Provide jQuery on window before any module imports (mirrors global script tag)
window.jQuery = jquery;
window.$ = jquery;

// Approved exception to top-level-imports rule: window.jQuery must be assigned
// before jquery-plugins evaluates, requiring deferred loading that cannot be
// moved to module scope.
const { registerJQueryPlugins } = await import("./lib/jquery-plugins.js");
registerJQueryPlugins();

// Factory for Bootstrap component mocks — each component shares the same
// constructor/show/hide/dispose/getInstance/getOrCreateInstance shape.
function makeBootstrapClass(
  name: string,
  extra?: Record<string, () => void>,
  // eslint-disable-next-line @typescript-eslint/no-explicit-any -- test mock; full bootstrap typing not needed
): any {
  const ComponentClass = class {
    constructor() {}
    show() {}
    hide() {}
    dispose() {}
    static getInstance() {
      return null;
    }
    static getOrCreateInstance() {
      // eslint-disable-next-line @typescript-eslint/no-explicit-any -- dynamic bootstrap mock access
      return new (window.bootstrap as any)[name]();
    }
  };
  if (extra) {
    for (const [methodName, methodFn] of Object.entries(extra)) {
      Object.defineProperty(ComponentClass.prototype, methodName, {
        value: methodFn,
        writable: true,
      });
    }
  }
  Object.defineProperty(ComponentClass, "name", { value: name });
  return ComponentClass;
}

// Mock Bootstrap (mirrors global script tag)
window.bootstrap = {
  Modal: makeBootstrapClass("Modal"),
  Tooltip: makeBootstrapClass("Tooltip"),
  Toast: makeBootstrapClass("Toast"),
  Collapse: makeBootstrapClass("Collapse", { toggle() {} }),
  // eslint-disable-next-line @typescript-eslint/no-explicit-any -- test mock; full bootstrap typing not needed
} as any;

// Inject app-config script element for lib/config.js
const appConfig = {
  routes: {
    home: "/",
    createUTub: "/utubs",
    getUTubs: "/utubs",
    login: "/login",
    register: "/register",
    confirmEmailAfterRegister: "/confirm-email",
    sendValidationEmail: "/send-validation-email",
    forgotPassword: "/forgot-password",
    errorPage: "/error",
    logout: "/logout",
    getUTub: "/utubs/-1",
    deleteUTub: "/utubs/-1",
    updateUTubName: "/utubs/-1/name",
    updateUTubDescription: "/utubs/-1/description",
    getURL: "/utubs/-1/urls/-2",
    createURL: "/utubs/-1/urls",
    deleteURL: "/utubs/-1/urls/-2",
    updateURL: "/utubs/-1/urls/-2",
    updateURLTitle: "/utubs/-1/urls/-2/title",
    createURLTag: "/utubs/-1/urls/-2/tags",
    deleteURLTag: "/utubs/-1/urls/-2/tags/-3",
    createUTubTag: "/utubs/-1/tags",
    deleteUTubTag: "/utubs/-1/tags/-2",
    createMember: "/utubs/-1/members",
    removeMember: "/utubs/-1/members/-4",
    contactUs: "/contact",
  },
  constants: {
    UTUBS_MIN_NAME_LENGTH: 1,
  },
  strings: {
    COOKIE_BANNER_SEEN: "cookie_banner_seen=true",
    INVALID_URL: "This is not a valid URL.",
    VALIDATE_MY_EMAIL: "Validate My Email",
  },
};

const configScript = document.createElement("script");
configScript.id = "app-config";
configScript.type = "application/json";
configScript.textContent = JSON.stringify(appConfig);
document.head.appendChild(configScript);
