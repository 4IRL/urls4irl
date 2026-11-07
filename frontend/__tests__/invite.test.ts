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

export {};
