import jquery from "jquery";

// Provide jQuery on window before any module imports (mirrors global script tag)
window.jQuery = jquery;
window.$ = jquery;

// Register jQuery plugins via dynamic import so window.jQuery is already set.
// Static `import` statements are hoisted and evaluated before any module-body
// code runs, so lib/globals.js (`export const $ = window.jQuery`) would see
// undefined if we used a static import here.  A dynamic import runs after the
// lines above, so window.jQuery is guaranteed to be set first.
const { registerJQueryPlugins } = await import("./lib/jquery-plugins.js");
registerJQueryPlugins();

// Mock Bootstrap (mirrors global script tag)
window.bootstrap = {
  Modal: class Modal {
    constructor() {}
    show() {}
    hide() {}
    dispose() {}
    static getInstance() {
      return null;
    }
    static getOrCreateInstance() {
      return new window.bootstrap.Modal();
    }
  },
  Tooltip: class Tooltip {
    constructor() {}
    show() {}
    hide() {}
    dispose() {}
    static getInstance() {
      return null;
    }
    static getOrCreateInstance() {
      return new window.bootstrap.Tooltip();
    }
  },
  Toast: class Toast {
    constructor() {}
    show() {}
    hide() {}
    dispose() {}
    static getInstance() {
      return null;
    }
    static getOrCreateInstance() {
      return new window.bootstrap.Toast();
    }
  },
  Collapse: class Collapse {
    constructor() {}
    show() {}
    hide() {}
    toggle() {}
    dispose() {}
    static getInstance() {
      return null;
    }
    static getOrCreateInstance() {
      return new window.bootstrap.Collapse();
    }
  },
};

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
