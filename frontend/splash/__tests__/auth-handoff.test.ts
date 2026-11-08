import { getForwardableNextQuery } from "../next-param.js";
import {
  applyNextToOAuthLinks,
  openAuthModalFromHint,
} from "../auth-handoff.js";
import { loginModalOpener, registerModalOpener } from "../init.js";

vi.mock("../init.js", () => ({
  loginModalOpener: vi.fn(),
  registerModalOpener: vi.fn(),
}));

const OAUTH_HTML = `
  <div id="LoginModal" class="modal">
    <a id="GoogleOAuthLogin" href="/oauth/google"></a>
    <a id="GitHubOAuthLogin" href="/oauth/github"></a>
  </div>
  <div id="RegisterModal" class="modal">
    <a id="GoogleOAuthRegister" href="/oauth/google"></a>
    <a id="GitHubOAuthRegister" href="/oauth/github"></a>
  </div>
`;

const ANCHOR_IDS = [
  "GoogleOAuthLogin",
  "GitHubOAuthLogin",
  "GoogleOAuthRegister",
  "GitHubOAuthRegister",
];

function setSearch(search: string): void {
  window.history.replaceState({}, "", `/${search}`);
}

describe("getForwardableNextQuery", () => {
  it("returns the value and query for a single next", () => {
    expect(getForwardableNextQuery("?next=/invite/x")).toEqual({
      value: "/invite/x",
      query: "next=%2Finvite%2Fx",
    });
  });

  it.each(["", "?next=a&b=c", "?b=c"])("returns null for %j", (search) => {
    expect(getForwardableNextQuery(search)).toBeNull();
  });
});

describe("applyNextToOAuthLinks", () => {
  beforeEach(() => {
    document.body.innerHTML = OAUTH_HTML;
  });

  afterEach(() => setSearch(""));

  it("appends exactly one next to all four anchors", () => {
    setSearch("?next=/invite/abc");
    applyNextToOAuthLinks();
    for (const id of ANCHOR_IDS) {
      const href = document.getElementById(id)!.getAttribute("href")!;
      expect(href.startsWith("/oauth/")).toBe(true);
      expect(href.endsWith("?next=%2Finvite%2Fabc")).toBe(true);
      expect(href.match(/next=/g)).toHaveLength(1);
    }
  });

  it("appends a single non-invite next as well", () => {
    setSearch(`?next=${encodeURIComponent("/home?UTubID=3")}`);
    applyNextToOAuthLinks();
    for (const id of ANCHOR_IDS) {
      const href = document.getElementById(id)!.getAttribute("href")!;
      expect(new URL(href, "http://x").searchParams.getAll("next")).toEqual([
        "/home?UTubID=3",
      ]);
    }
  });

  it("replaces an existing next rather than duplicating it", () => {
    document
      .getElementById("GoogleOAuthLogin")!
      .setAttribute("href", "/oauth/google?next=old");
    setSearch("?next=/invite/abc");
    applyNextToOAuthLinks();
    const href = document
      .getElementById("GoogleOAuthLogin")!
      .getAttribute("href")!;
    expect(new URL(href, "http://x").searchParams.getAll("next")).toEqual([
      "/invite/abc",
    ]);
  });

  it.each(["", "?next=a&b=c", "?b=c"])(
    "leaves hrefs alone for %j",
    (search) => {
      setSearch(search);
      applyNextToOAuthLinks();
      for (const id of ANCHOR_IDS) {
        expect(document.getElementById(id)!.getAttribute("href")).toMatch(
          /^\/oauth\/(google|github)$/,
        );
      }
    },
  );

  it("keeps an unrelated query param on the anchor", () => {
    document
      .getElementById("GoogleOAuthLogin")!
      .setAttribute("href", "/oauth/google?x=1");
    setSearch("?next=/invite/abc");
    applyNextToOAuthLinks();
    const href = document
      .getElementById("GoogleOAuthLogin")!
      .getAttribute("href")!;
    const params = new URL(href, "http://x").searchParams;
    expect(params.get("x")).toBe("1");
    expect(params.getAll("next")).toEqual(["/invite/abc"]);
  });

  it("does not throw when anchors are absent", () => {
    document.body.innerHTML = "";
    setSearch("?next=/invite/abc");
    expect(() => applyNextToOAuthLinks()).not.toThrow();
  });
});

describe("openAuthModalFromHint", () => {
  function render(hint: string | null, modals = true): void {
    const attr = hint === null ? "" : ` data-auth-modal-hint="${hint}"`;
    document.body.innerHTML = `<div id="splashConfig"${attr}></div>${
      modals ? OAUTH_HTML : ""
    }`;
  }

  beforeEach(() => vi.clearAllMocks());

  it("opens login once for the login hint", () => {
    render("login");
    openAuthModalFromHint();
    expect(loginModalOpener).toHaveBeenCalledTimes(1);
    expect(registerModalOpener).not.toHaveBeenCalled();
  });

  it("opens register once for the register hint", () => {
    render("register");
    openAuthModalFromHint();
    expect(registerModalOpener).toHaveBeenCalledTimes(1);
    expect(loginModalOpener).not.toHaveBeenCalled();
  });

  it.each(["bogus", null])("opens nothing for hint %j", (hint) => {
    render(hint);
    openAuthModalFromHint();
    expect(loginModalOpener).not.toHaveBeenCalled();
    expect(registerModalOpener).not.toHaveBeenCalled();
  });

  it("opens nothing when the target modal is missing", () => {
    render("login", false);
    openAuthModalFromHint();
    expect(loginModalOpener).not.toHaveBeenCalled();
  });

  it("opens nothing when another modal is already shown", () => {
    render("login");
    document.getElementById("RegisterModal")!.classList.add("show");
    openAuthModalFromHint();
    expect(loginModalOpener).not.toHaveBeenCalled();
  });

  it.each([
    `<div id="ConfirmEmailModal" data-resend-token="t"></div>`,
    `<form id="ModalForm" data-modal-type="reset-password"></form>`,
    `<form id="ModalForm" data-modal-context="oauth-reject"></form>`,
  ])("opens nothing when a shell modal is pending: %s", (shellHtml) => {
    render("login");
    document.body.insertAdjacentHTML("beforeend", shellHtml);
    openAuthModalFromHint();
    expect(loginModalOpener).not.toHaveBeenCalled();
  });
});
