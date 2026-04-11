import { APP_CONFIG } from "../config.js";

describe("APP_CONFIG shape", () => {
  describe("static routes", () => {
    const STATIC_ROUTE_KEYS = [
      "home",
      "login",
      "register",
      "confirmEmailAfterRegister",
      "sendValidationEmail",
      "forgotPassword",
      "errorPage",
      "logout",
      "createUTub",
      "getUTubs",
      "contactUs",
    ] as const;

    it.each(STATIC_ROUTE_KEYS)("routes.%s is a string", (key) => {
      expect(typeof APP_CONFIG.routes[key]).toBe("string");
    });
  });

  describe("single-param dynamic routes", () => {
    const SINGLE_PARAM_ROUTE_KEYS = [
      "getUTub",
      "deleteUTub",
      "updateUTubName",
      "updateUTubDescription",
      "createURL",
      "createUTubTag",
      "createMember",
    ] as const;

    it.each(SINGLE_PARAM_ROUTE_KEYS)("routes.%s is a function", (key) => {
      expect(typeof APP_CONFIG.routes[key]).toBe("function");
    });

    it.each(SINGLE_PARAM_ROUTE_KEYS)(
      "routes.%s returns a string when called with an id",
      (key) => {
        const route = APP_CONFIG.routes[key] as (id: number) => string;
        expect(typeof route(42)).toBe("string");
      },
    );
  });

  describe("two-param dynamic routes", () => {
    const TWO_PARAM_ROUTE_KEYS = [
      "getURL",
      "deleteURL",
      "updateURL",
      "updateURLTitle",
      "createURLTag",
      "deleteUTubTag",
      "removeMember",
    ] as const;

    it.each(TWO_PARAM_ROUTE_KEYS)("routes.%s is a function", (key) => {
      expect(typeof APP_CONFIG.routes[key]).toBe("function");
    });

    it.each(TWO_PARAM_ROUTE_KEYS)(
      "routes.%s returns a string when called with two ids",
      (key) => {
        const route = APP_CONFIG.routes[key] as (
          firstId: number,
          secondId: number,
        ) => string;
        expect(typeof route(1, 2)).toBe("string");
      },
    );
  });

  describe("three-param dynamic routes", () => {
    it("routes.deleteURLTag is a function", () => {
      expect(typeof APP_CONFIG.routes.deleteURLTag).toBe("function");
    });

    it("routes.deleteURLTag returns a string when called with three ids", () => {
      expect(typeof APP_CONFIG.routes.deleteURLTag(1, 2, 3)).toBe("string");
    });
  });

  describe("constants and strings", () => {
    it("constants is a non-null object", () => {
      expect(APP_CONFIG.constants).toBeDefined();
      expect(typeof APP_CONFIG.constants).toBe("object");
      expect(APP_CONFIG.constants).not.toBeNull();
    });

    it("strings is a non-null object", () => {
      expect(APP_CONFIG.strings).toBeDefined();
      expect(typeof APP_CONFIG.strings).toBe("object");
      expect(APP_CONFIG.strings).not.toBeNull();
    });
  });

  describe("immutability", () => {
    it("APP_CONFIG is frozen", () => {
      expect(Object.isFrozen(APP_CONFIG)).toBe(true);
    });

    it("APP_CONFIG.routes is frozen", () => {
      expect(Object.isFrozen(APP_CONFIG.routes)).toBe(true);
    });
  });
});
