import { withMemberControlFocusFallback } from "../focus-fallback.js";

const $ = window.jQuery;

function setLayout({ visible }: { visible: boolean }) {
  // jsdom has no layout: offsetParent is always null unless mocked.
  Object.defineProperty(HTMLElement.prototype, "offsetParent", {
    configurable: true,
    get() {
      return visible ? document.body : null;
    },
  });
}

describe("withMemberControlFocusFallback", () => {
  beforeEach(() => {
    document.body.innerHTML = `
      <button id="MemberDeckHeaderAndCaret">Members</button>
      <button id="memberBtnCreate">Add</button>
      <div id="createMemberWrap"><input id="inner" /></div>
      <div id="listMembers">
        <span class="member" memberid="3"><button class="memberRowKebab memberRowKebab--coOwner" id="k3">k</button></span>
        <span class="member" memberid="4"><button class="memberRowKebab" id="k4">k</button></span>
      </div>
    `;
    setLayout({ visible: true });
  });

  afterEach(() => {
    // Restore the prototype getter so other suites see the default.
    delete (HTMLElement.prototype as unknown as Record<string, unknown>)
      .offsetParent;
  });

  it("moves focus from a hidden add button to the deck header", () => {
    $("#memberBtnCreate")[0].focus();

    withMemberControlFocusFallback({
      write: () => {
        setLayout({ visible: false });
        // the header stays reachable
        Object.defineProperty(
          $("#MemberDeckHeaderAndCaret")[0],
          "offsetParent",
          {
            configurable: true,
            get: () => document.body,
          },
        );
      },
    });

    expect(document.activeElement?.id).toBe("MemberDeckHeaderAndCaret");
  });

  it("falls back to the surviving row when a kebab is hidden", () => {
    $("#k3")[0].focus();

    withMemberControlFocusFallback({
      write: () => {
        Object.defineProperty($("#k3")[0], "offsetParent", {
          configurable: true,
          get: () => null,
        });
      },
    });

    expect(document.activeElement?.classList.contains("member")).toBe(true);
  });

  it("guards only the co-owner kebab outside a rebuild; the owner kebab is left to coverList", () => {
    $("#k4")[0].focus();

    withMemberControlFocusFallback({
      write: () => {
        Object.defineProperty($("#k4")[0], "offsetParent", {
          configurable: true,
          get: () => null,
        });
      },
    });

    // Outside the `.memberRowKebab--coOwner` match set: nothing moves it.
    expect(document.activeElement?.id).toBe("k4");
  });

  it("covers a destroyed list control only with coverList", () => {
    $("#k3")[0].focus();
    withMemberControlFocusFallback({
      coverList: true,
      write: () => $("#listMembers").empty(),
    });
    expect(document.activeElement?.id).toBe("MemberDeckHeaderAndCaret");
  });

  it("leaves focus alone elsewhere", () => {
    $("#MemberDeckHeaderAndCaret")[0].focus();
    withMemberControlFocusFallback({ write: () => $("#listMembers").empty() });
    expect(document.activeElement?.id).toBe("MemberDeckHeaderAndCaret");
  });
});
