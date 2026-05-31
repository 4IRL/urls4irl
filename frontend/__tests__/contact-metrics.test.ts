import { UI_EVENTS } from "../types/metrics-events.js";
import { createMockJqXHR } from "./helpers/mock-jquery.js";
import { handleContactSubmit } from "../contact.js";

const { mockMetricsClient } = await vi.hoisted(
  async () => await import("./helpers/mock-metrics-client.js"),
);

vi.mock("../lib/metrics-client.js", () => mockMetricsClient());

vi.mock("../lib/page-utils.js", () => ({
  showNewPageOnAJAXHTMLResponse: vi.fn(),
}));

vi.mock("../lib/csrf.js", () => ({
  setupCSRF: vi.fn(),
}));

vi.mock("../lib/security-check.js", () => ({}));

vi.mock("../lib/navbar-shared.js", () => ({
  initNavbarRouting: vi.fn(),
}));

vi.mock("../lib/globals.js", () => ({
  $: window.jQuery,
  jQuery: window.jQuery,
  bootstrap: window.bootstrap,
}));

vi.mock("../lib/config.js", () => {
  const configScript = document.getElementById("app-config");
  const config = JSON.parse(configScript?.textContent ?? "{}");
  return { APP_CONFIG: config };
});

const $ = window.jQuery;

const CONTACT_FORM_HTML = `
  <form id="ContactForm" method="POST" novalidate>
    <div id="Banner" class="alert hidden" role="alert"></div>
    <input id="subject" name="subject" type="text" class="form-control" value="Test Subject" />
    <div id="subject-error" class="invalid-feedback"></div>
    <textarea id="content" name="content" class="form-control">Test content here</textarea>
    <div id="content-error" class="invalid-feedback"></div>
    <input id="submit" type="submit" value="Submit" />
  </form>
`;

describe("contact-form metrics — UI_CONTACT_SUBMIT", () => {
  beforeEach(() => {
    document.body.innerHTML = CONTACT_FORM_HTML;
    vi.clearAllMocks();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("emits ui_contact_submit once on submit", async () => {
    const { emit } = await import("../lib/metrics-client.js");
    const mockDeferred = createMockJqXHR();
    vi.spyOn($, "ajax").mockReturnValue(mockDeferred);

    const $form = $("#ContactForm");
    const fakeEvent = {
      preventDefault: vi.fn(),
    } as unknown as JQuery.TriggeredEvent;
    handleContactSubmit(fakeEvent, $form);

    expect(emit).toHaveBeenCalledWith({ event: UI_EVENTS.UI_CONTACT_SUBMIT });
    expect(emit).toHaveBeenCalledTimes(1);
  });
});
