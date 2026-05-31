import { UI_EVENTS } from "../../../types/metrics-events.js";
import { setupShowCreateMemberFormEventListeners } from "../create.js";

const { mockMetricsClient } = await vi.hoisted(
  async () => await import("../../../__tests__/helpers/mock-metrics-client.js"),
);

vi.mock("../../../lib/metrics-client.js", () => mockMetricsClient());

vi.mock("../../../lib/ajax.js", () => ({
  ajaxCall: vi.fn(),
  is429Handled: vi.fn(() => false),
}));

vi.mock("../members.js", () => ({ createMemberBadge: vi.fn() }));
vi.mock("../deck.js", () => ({ setMemberDeckForUTub: vi.fn() }));

vi.mock("../../../store/app-store.js", () => ({
  getState: vi.fn(() => ({ members: [] })),
  setState: vi.fn(),
}));

const $ = window.jQuery;

const CREATE_MEMBER_FORM_HTML = `
  <div>
    <div id="createMemberWrap"></div>
    <div id="displayMemberWrap"></div>
    <button id="memberBtnCreate"></button>
    <input id="memberCreate" type="text" />
    <div id="memberCreate-error"></div>
  </div>
`;

describe("create-metrics — UI_MEMBER_INVITE_OPEN", () => {
  beforeEach(() => {
    document.body.innerHTML = CREATE_MEMBER_FORM_HTML;
    vi.clearAllMocks();
  });

  afterEach(() => {
    document.body.innerHTML = "";
  });

  it("emits ui_member_invite_open when the invite button is clicked", async () => {
    const { emit } = await import("../../../lib/metrics-client.js");

    setupShowCreateMemberFormEventListeners(7);
    $("#memberBtnCreate").trigger("click.createMember");

    expect(emit).toHaveBeenCalledWith({
      event: UI_EVENTS.UI_MEMBER_INVITE_OPEN,
    });
    expect(emit).toHaveBeenCalledTimes(1);
  });

  it("emits ui_member_invite_open on Enter keypress while the button is focused", async () => {
    const { emit } = await import("../../../lib/metrics-client.js");

    setupShowCreateMemberFormEventListeners(7);
    $("#memberBtnCreate").trigger("focus");
    const event = $.Event("keydown.createMember", { key: "Enter" });
    $("#memberBtnCreate").trigger(event);

    expect(emit).toHaveBeenCalledWith({
      event: UI_EVENTS.UI_MEMBER_INVITE_OPEN,
    });
    expect(emit).toHaveBeenCalledTimes(1);
  });

  it("does not emit when listeners are set up but no interaction occurs", async () => {
    const { emit } = await import("../../../lib/metrics-client.js");

    setupShowCreateMemberFormEventListeners(7);

    expect(emit).not.toHaveBeenCalled();
  });
});
