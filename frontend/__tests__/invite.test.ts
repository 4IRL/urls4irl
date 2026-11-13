vi.mock("../lib/security-check.js", () => ({}));

vi.mock("../lib/globals.js", () => ({
  $: window.jQuery,
  jQuery: window.jQuery,
  bootstrap: window.bootstrap,
}));

const { initNavbarRouting, initNavbarBackdrop, initCookieBanner } =
  await vi.hoisted(async () => ({
    initNavbarRouting: vi.fn(),
    initNavbarBackdrop: vi.fn(),
    initCookieBanner: vi.fn(),
  }));

vi.mock("../lib/navbar-shared.js", () => ({
  initNavbarRouting,
  initNavbarBackdrop,
}));

vi.mock("../lib/cookie-banner.js", () => ({ initCookieBanner }));

const JOINING = "Joining...";
const ORIGINAL = "Join UTub";
const TIMEOUT_MS = 15000;

function renderForm(): void {
  document.body.innerHTML = `
    <form id="inviteJoinForm" method="post" action="/invite/tok/join">
      <button type="submit" id="inviteJoinBtn" data-joining-label="${JOINING}">${ORIGINAL}</button>
      <span id="inviteJoinStatus" role="status"></span>
    </form>`;
}

function getEls(): {
  form: HTMLFormElement;
  btn: HTMLButtonElement;
  status: HTMLElement;
} {
  return {
    form: document.getElementById("inviteJoinForm") as HTMLFormElement,
    btn: document.getElementById("inviteJoinBtn") as HTMLButtonElement,
    status: document.getElementById("inviteJoinStatus") as HTMLElement,
  };
}

function submit(form: HTMLFormElement): Event {
  const event = new Event("submit", { bubbles: true, cancelable: true });
  form.dispatchEvent(event);
  return event;
}

async function load(): Promise<void> {
  await import("../invite.js");
  await new Promise<void>((resolve) => setTimeout(resolve, 0));
}

function expectRestored(): void {
  const { form, btn, status } = getEls();
  expect(btn.hasAttribute("aria-disabled")).toBe(false);
  expect(btn.textContent).toBe(ORIGINAL);
  expect(form.hasAttribute("aria-busy")).toBe(false);
  expect(status.textContent).toBe("");
}

describe("invite page entry point", () => {
  afterEach(() => {
    vi.useRealTimers();
    vi.resetModules();
    vi.clearAllMocks();
    document.body.innerHTML = "";
  });

  it("calls the three shell inits once", async () => {
    renderForm();
    await load();
    expect(initNavbarRouting).toHaveBeenCalledTimes(1);
    expect(initNavbarBackdrop).toHaveBeenCalledTimes(1);
    expect(initCookieBanner).toHaveBeenCalledTimes(1);
  });

  it("marks the button busy on submit without preventing it", async () => {
    renderForm();
    await load();
    const { form, btn, status } = getEls();
    const event = submit(form);
    expect(event.defaultPrevented).toBe(false);
    expect(btn.getAttribute("aria-disabled")).toBe("true");
    expect(btn.hasAttribute("disabled")).toBe(false);
    expect(form.getAttribute("aria-busy")).toBe("true");
    expect(btn.textContent).toBe(JOINING);
    expect(status.textContent).toBe(JOINING);
  });

  it("prevents a second submit while aria-disabled", async () => {
    renderForm();
    await load();
    const { form } = getEls();
    submit(form);
    expect(submit(form).defaultPrevented).toBe(true);
  });

  it.each([
    ["plain", new Event("pageshow")],
    ["persisted", Object.assign(new Event("pageshow"), { persisted: true })],
  ])("restores on %s pageshow", async (_name, event) => {
    renderForm();
    await load();
    submit(getEls().form);
    window.dispatchEvent(event);
    expectRestored();
  });

  it("restores after the timeout, not before", async () => {
    renderForm();
    vi.useFakeTimers();
    await import("../invite.js");
    await vi.advanceTimersByTimeAsync(1);
    const { form, btn } = getEls();
    submit(form);
    vi.advanceTimersByTime(TIMEOUT_MS - 100);
    expect(btn.getAttribute("aria-disabled")).toBe("true");
    vi.advanceTimersByTime(200);
    expectRestored();
    expect(submit(form).defaultPrevented).toBe(false);
  });

  it("pageshow clears the pending timer and a new submit starts a fresh one", async () => {
    renderForm();
    vi.useFakeTimers();
    await import("../invite.js");
    await vi.advanceTimersByTimeAsync(1);
    const { form, btn } = getEls();
    submit(form);
    window.dispatchEvent(new Event("pageshow"));
    expect(vi.getTimerCount()).toBe(0);
    submit(form);
    expect(vi.getTimerCount()).toBe(1);
    vi.advanceTimersByTime(TIMEOUT_MS - 100);
    expect(btn.getAttribute("aria-disabled")).toBe("true");
    vi.advanceTimersByTime(200);
    expectRestored();
  });

  it("a blocked second submit does not arm a second timer", async () => {
    renderForm();
    vi.useFakeTimers();
    await import("../invite.js");
    await vi.advanceTimersByTimeAsync(1);
    const { form } = getEls();
    submit(form);
    submit(form);
    expect(vi.getTimerCount()).toBe(1);
  });

  it("is a no-op without the form", async () => {
    document.body.innerHTML = "<main></main>";
    await load();
    expect(initNavbarRouting).toHaveBeenCalledTimes(1);
    expect(() => window.dispatchEvent(new Event("pageshow"))).not.toThrow();
  });
});

const FLUSH_QUERY = "(max-width: 1049px)";
const BANNER_HEIGHT = 120;
const FLOAT_GAP_PX = 1.75 * 16 + 2;

type MediaListener = () => void;

function stubMatchMedia(initialMatches: boolean): {
  setMatches: (matches: boolean) => void;
  queries: string[];
} {
  let matches = initialMatches;
  const listeners = new Set<MediaListener>();
  const queries: string[] = [];
  window.matchMedia = vi.fn((query: string) => {
    queries.push(query);
    return {
      get matches() {
        return matches;
      },
      media: query,
      addEventListener: (_type: string, listener: MediaListener) =>
        listeners.add(listener),
      removeEventListener: (_type: string, listener: MediaListener) =>
        listeners.delete(listener),
    };
  }) as unknown as typeof window.matchMedia;
  return {
    queries,
    setMatches: (next: boolean) => {
      matches = next;
      listeners.forEach((listener) => listener());
    },
  };
}

function setOffsetHeight(el: HTMLElement, height: number): void {
  Object.defineProperty(el, "offsetHeight", {
    configurable: true,
    value: height,
  });
}

function renderPreview({ banner }: { banner: boolean }): {
  bar: HTMLElement;
  banner: HTMLElement | null;
} {
  document.body.innerHTML = `
    <div id="invitePreviewBar"></div>
    ${banner ? '<div id="CookieBanner"></div>' : ""}`;
  const bar = document.getElementById("invitePreviewBar") as HTMLElement;
  const bannerEl = document.getElementById("CookieBanner");
  setOffsetHeight(bar, 90);
  if (bannerEl) {
    setOffsetHeight(bannerEl, BANNER_HEIGHT);
    bannerEl.getBoundingClientRect = () =>
      ({ top: 1, bottom: 2, height: 1 }) as DOMRect;
  }
  return { bar, banner: bannerEl };
}

function rootVar(name: string): string {
  return document.documentElement.style.getPropertyValue(name);
}

async function flushMutations(): Promise<void> {
  await new Promise<void>((resolve) => setTimeout(resolve, 0));
}

describe("preview bar offsets", () => {
  afterEach(() => {
    vi.resetModules();
    vi.clearAllMocks();
    document.body.innerHTML = "";
    document.documentElement.removeAttribute("style");
  });

  it("writes nothing without the bar", async () => {
    stubMatchMedia(false);
    document.body.innerHTML =
      '<div id="CookieBanner" class="is-visible"></div>';
    await load();
    expect(rootVar("--invite-bar-height")).toBe("");
    expect(rootVar("--invite-banner-offset")).toBe("");
  });

  it("sets the height and a 0px offset when there is no banner", async () => {
    stubMatchMedia(false);
    renderPreview({ banner: false });
    await load();
    expect(rootVar("--invite-bar-height")).toBe("90px");
    expect(rootVar("--invite-banner-offset")).toBe("0px");
  });

  it("uses offsetHeight alone at or below 1049px, ignoring the rect", async () => {
    const media = stubMatchMedia(true);
    const { banner } = renderPreview({ banner: true });
    banner?.classList.add("is-visible");
    await load();
    expect(media.queries).toContain(FLUSH_QUERY);
    expect(rootVar("--invite-banner-offset")).toBe(`${BANNER_HEIGHT}px`);
  });

  it("adds the float gap above 1049px, ignoring the rect", async () => {
    stubMatchMedia(false);
    const { banner } = renderPreview({ banner: true });
    banner?.classList.add("is-visible");
    await load();
    expect(rootVar("--invite-banner-offset")).toBe(
      `${BANNER_HEIGHT + FLOAT_GAP_PX}px`,
    );
  });

  it("returns to 0px when is-visible is removed and back when re-added", async () => {
    stubMatchMedia(true);
    const { banner } = renderPreview({ banner: true });
    banner?.classList.add("is-visible");
    await load();
    banner?.classList.remove("is-visible");
    await flushMutations();
    expect(rootVar("--invite-banner-offset")).toBe("0px");
    banner?.classList.add("is-visible");
    await flushMutations();
    expect(rootVar("--invite-banner-offset")).toBe(`${BANNER_HEIGHT}px`);
  });

  it("recomputes on window resize", async () => {
    stubMatchMedia(true);
    const { bar } = renderPreview({ banner: false });
    await load();
    setOffsetHeight(bar, 150);
    window.dispatchEvent(new Event("resize"));
    expect(rootVar("--invite-bar-height")).toBe("150px");
  });

  it("recomputes when the breakpoint media query changes", async () => {
    const media = stubMatchMedia(true);
    const { banner } = renderPreview({ banner: true });
    banner?.classList.add("is-visible");
    await load();
    expect(rootVar("--invite-banner-offset")).toBe(`${BANNER_HEIGHT}px`);
    media.setMatches(false);
    expect(rootVar("--invite-banner-offset")).toBe(
      `${BANNER_HEIGHT + FLOAT_GAP_PX}px`,
    );
  });

  it("leaves the join button behaviour intact when both exist", async () => {
    stubMatchMedia(true);
    document.body.innerHTML = `
      <div id="invitePreviewBar"></div>
      <form id="inviteJoinForm"><button id="inviteJoinBtn" data-joining-label="${JOINING}">${ORIGINAL}</button>
      <span id="inviteJoinStatus"></span></form>`;
    await load();
    const { form, btn } = getEls();
    submit(form);
    expect(btn.getAttribute("aria-disabled")).toBe("true");
    expect(btn.textContent).toBe(JOINING);
  });
});

describe("preview date localisation", () => {
  beforeEach(() => {
    // UTC+14: 18:00Z on Nov 14 is Nov 15 locally. stubEnv assigns process.env.TZ, which
    // Node re-reads; unstubAllEnvs restores (or deletes) the original in afterEach.
    vi.stubEnv("TZ", "Pacific/Kiritimati");
  });

  afterEach(() => {
    vi.unstubAllEnvs();
    vi.resetModules();
    vi.clearAllMocks();
    document.body.innerHTML = "";
  });

  function renderBadge(datetime: string | null): HTMLTimeElement {
    const attr = datetime === null ? "" : ` datetime="${datetime}"`;
    document.body.innerHTML = `<span id="invitePreviewBadge"><time${attr}>Nov 14, 2026</time></span>`;
    return document.querySelector("time") as HTMLTimeElement;
  }

  it("rewrites the text to the local date and keeps datetime", async () => {
    const iso = "2026-11-14T18:00:00+00:00";
    const time = renderBadge(iso);
    await load();
    expect(time.textContent).toBe("Nov 15, 2026");
    expect(time.getAttribute("datetime")).toBe(iso);
  });

  it("leaves the text when datetime is invalid", async () => {
    const time = renderBadge("not-a-date");
    await load();
    expect(time.textContent).toBe("Nov 14, 2026");
  });

  it("leaves the text when datetime is absent", async () => {
    const time = renderBadge(null);
    await load();
    expect(time.textContent).toBe("Nov 14, 2026");
  });

  it("is a no-op without the badge", async () => {
    document.body.innerHTML = "<main></main>";
    await expect(load()).resolves.toBeUndefined();
  });
});

export {};
