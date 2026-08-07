import {
  createMockJqXHRChainable,
  createMockXhr,
} from "../../__tests__/helpers/mock-jquery.js";
import { ajaxCall, is429Handled } from "../../lib/ajax.js";
import {
  initDisplayPreferences,
  _resetDisplayPreferencesForTests,
} from "../display-preferences.js";

vi.mock("../../lib/ajax.js", () => ({
  ajaxCall: vi.fn(),
  is429Handled: vi.fn(() => false),
}));

vi.mock("../../lib/globals.js", () => ({
  $: window.jQuery,
  jQuery: window.jQuery,
  bootstrap: window.bootstrap,
}));

const $ = window.jQuery;

const ACTION_URL = "/users/1/preferences";
const SAVED_TOAST = "Preferences saved";
const GENERIC_ERROR = "Unable to process request.";

// The full instant-apply payload for the default fixture (theme=system, all
// selects at their first option) with the theme overridden by the caller.
function expectedPayload(
  theme: "light" | "dark" | "system",
): Record<string, string> {
  return {
    theme,
    defaultView: "list",
    defaultSort: "newest",
    density: "comfortable",
    dateFormat: "iso",
  };
}

function panelHtml(checkedTheme: "light" | "dark" | "system"): string {
  const radio = (value: string): string => {
    const checked = value === checkedTheme;
    return `<button type="button" role="radio" class="SettingsThemeOption" data-theme-value="${value}" aria-checked="${checked}" tabindex="${checked ? "0" : "-1"}">${value}</button>`;
  };
  return `
    <div id="SettingsGlobalStatusToast" class="visually-hidden" role="status" aria-live="polite"></div>
    <section role="tabpanel" id="SettingsPanelUiSettings" data-action-url="${ACTION_URL}">
      <div id="SettingsUiSettingsStatus" class="alert d-none" role="alert" aria-live="polite"></div>
      <div class="SettingsThemeSeg" id="SettingsThemeControl" role="radiogroup" aria-label="Theme">
        ${radio("light")}${radio("dark")}${radio("system")}
      </div>
      <select class="form-control" id="SettingsDefaultViewSelect" aria-label="Default UTub view">
        <option value="list" selected>List</option>
        <option value="compact">View: Compact</option>
        <option value="cards">Cards</option>
      </select>
      <select class="form-control" id="SettingsDefaultSortSelect" aria-label="Default sort">
        <option value="newest" selected>Date added (newest)</option>
        <option value="oldest">Date added (oldest)</option>
        <option value="title_az">Title A–Z</option>
      </select>
      <select class="form-control" id="SettingsDensitySelect" aria-label="Density">
        <option value="comfortable" selected>Comfortable</option>
        <option value="compact">Density: Compact</option>
      </select>
      <select class="form-control" id="SettingsDateFormatSelect" aria-label="Date format">
        <option value="iso" selected>ISO (YYYY-MM-DD)</option>
        <option value="us">US (MM/DD/YYYY)</option>
        <option value="eu">EU (DD/MM/YYYY)</option>
      </select>
    </section>
  `;
}

function mockDone(response: unknown, xhr: JQuery.jqXHR): JQuery.jqXHR {
  return createMockJqXHRChainable({
    done: (callback: unknown) => {
      (
        callback as (
          response: unknown,
          _textStatus: unknown,
          xhr: JQuery.jqXHR,
        ) => void
      )(response, "success", xhr);
    },
  }) as unknown as JQuery.jqXHR;
}

function mockFail(xhr: JQuery.jqXHR): JQuery.jqXHR {
  return createMockJqXHRChainable({
    fail: (callback: unknown) => {
      (callback as (xhr: JQuery.jqXHR) => void)(xhr);
    },
  }) as unknown as JQuery.jqXHR;
}

function getRadio(value: string): HTMLButtonElement {
  return document.querySelector(
    `[data-theme-value="${value}"]`,
  ) as HTMLButtonElement;
}

function successResponse(
  theme: "light" | "dark" | "system",
): Record<string, string> {
  return {
    ...expectedPayload(theme),
    status: "Success",
    message: SAVED_TOAST,
  };
}

describe("display-preferences", () => {
  beforeEach(() => {
    vi.useFakeTimers();
    vi.clearAllMocks();
    vi.mocked(is429Handled).mockReturnValue(false);
    _resetDisplayPreferencesForTests();
    document.documentElement.removeAttribute("data-theme");
  });

  afterEach(() => {
    vi.useRealTimers();
    _resetDisplayPreferencesForTests();
    document.body.innerHTML = "";
  });

  it("is a no-op when #SettingsPanelUiSettings is absent", () => {
    document.body.innerHTML = "<div id='Unrelated'></div>";
    initDisplayPreferences();
    $("body").trigger("click");
    vi.advanceTimersByTime(300);
    expect(vi.mocked(ajaxCall)).not.toHaveBeenCalled();
  });

  it("PUTs the full payload after the 300ms debounce when Dark is clicked, flips <html data-theme> and toasts on success", () => {
    document.body.innerHTML = panelHtml("system");
    const successXhr = createMockXhr({ status: 200 });
    vi.mocked(ajaxCall).mockReturnValue(
      mockDone(successResponse("dark"), successXhr),
    );
    initDisplayPreferences();

    $(getRadio("dark")).trigger("click");
    // Nothing fires until the debounce trailing edge.
    expect(vi.mocked(ajaxCall)).not.toHaveBeenCalled();

    vi.advanceTimersByTime(300);

    expect(vi.mocked(ajaxCall)).toHaveBeenCalledWith(
      "put",
      ACTION_URL,
      expectedPayload("dark"),
    );
    expect(document.documentElement.getAttribute("data-theme")).toBe("dark");
    expect($("#SettingsGlobalStatusToast").text()).toBe(SAVED_TOAST);
    // Panel re-enabled after the request settles.
    expect(getRadio("dark").getAttribute("disabled")).toBeNull();
  });

  it("PUTs the changed select value alongside the rest of the panel state", () => {
    document.body.innerHTML = panelHtml("system");
    vi.mocked(ajaxCall).mockReturnValue(
      mockDone(successResponse("system"), createMockXhr({ status: 200 })),
    );
    initDisplayPreferences();

    $("#SettingsDefaultSortSelect").val("title_az").trigger("change");
    vi.advanceTimersByTime(300);

    expect(vi.mocked(ajaxCall)).toHaveBeenCalledWith("put", ACTION_URL, {
      theme: "system",
      defaultView: "list",
      defaultSort: "title_az",
      density: "comfortable",
      dateFormat: "iso",
    });
  });

  it("writes the server error into #SettingsUiSettingsStatus and does NOT flip the theme on failure", () => {
    document.body.innerHTML = panelHtml("system");
    document.documentElement.setAttribute("data-theme", "dark");
    const failedXhr = createMockXhr({
      status: 400,
      responseJSON: {
        status: "Failure",
        message: "Invalid input.",
        errorCode: 1,
        errors: { theme: ["Invalid theme."] },
      },
    });
    vi.mocked(ajaxCall).mockReturnValue(mockFail(failedXhr));
    initDisplayPreferences();

    $(getRadio("light")).trigger("click");
    vi.advanceTimersByTime(300);

    const status = $("#SettingsUiSettingsStatus");
    expect(status.hasClass("d-none")).toBe(false);
    expect(status.hasClass("alert-danger")).toBe(true);
    expect(status.text()).toBe("Invalid theme.");
    // Theme unchanged — the failing PUT must not flip <html>.
    expect(document.documentElement.getAttribute("data-theme")).toBe("dark");
    // Success toast stays empty on the failure path.
    expect($("#SettingsGlobalStatusToast").text()).toBe("");
  });

  it("falls back to a generic error when the failure carries no field/message", () => {
    document.body.innerHTML = panelHtml("system");
    vi.mocked(ajaxCall).mockReturnValue(
      mockFail(createMockXhr({ status: 500 })),
    );
    initDisplayPreferences();

    $(getRadio("dark")).trigger("click");
    vi.advanceTimersByTime(300);

    expect($("#SettingsUiSettingsStatus").text()).toBe(GENERIC_ERROR);
  });

  it("does nothing further when the failure was already handled as a coarse 429", () => {
    document.body.innerHTML = panelHtml("system");
    vi.mocked(is429Handled).mockReturnValue(true);
    vi.mocked(ajaxCall).mockReturnValue(
      mockFail(createMockXhr({ status: 429 })),
    );
    initDisplayPreferences();

    $(getRadio("dark")).trigger("click");
    vi.advanceTimersByTime(300);

    expect($("#SettingsUiSettingsStatus").hasClass("d-none")).toBe(true);
  });

  it("ArrowRight roves aria-checked/tabindex to the next radio WITHOUT firing immediately or disabling controls mid-burst", () => {
    document.body.innerHTML = panelHtml("light");
    vi.mocked(ajaxCall).mockReturnValue(createMockJqXHRChainable());
    initDisplayPreferences();

    getRadio("light").focus();
    $(getRadio("light")).trigger($.Event("keydown", { key: "ArrowRight" }));

    expect(getRadio("dark").getAttribute("aria-checked")).toBe("true");
    expect(getRadio("dark").getAttribute("tabindex")).toBe("0");
    expect(getRadio("light").getAttribute("aria-checked")).toBe("false");
    expect(getRadio("light").getAttribute("tabindex")).toBe("-1");
    // Must not fire synchronously, and controls stay enabled mid-burst.
    expect(vi.mocked(ajaxCall)).not.toHaveBeenCalled();
    expect(getRadio("dark").getAttribute("disabled")).toBeNull();
  });

  it("ArrowRight from the last radio (System) wraps to the first (Light)", () => {
    document.body.innerHTML = panelHtml("system");
    vi.mocked(ajaxCall).mockReturnValue(createMockJqXHRChainable());
    initDisplayPreferences();

    getRadio("system").focus();
    $(getRadio("system")).trigger($.Event("keydown", { key: "ArrowRight" }));

    expect(getRadio("light").getAttribute("aria-checked")).toBe("true");
  });

  it("ArrowLeft from the first radio (Light) wraps to the last (System)", () => {
    document.body.innerHTML = panelHtml("light");
    vi.mocked(ajaxCall).mockReturnValue(createMockJqXHRChainable());
    initDisplayPreferences();

    getRadio("light").focus();
    $(getRadio("light")).trigger($.Event("keydown", { key: "ArrowLeft" }));

    expect(getRadio("system").getAttribute("aria-checked")).toBe("true");
  });

  it.each(["Enter", " "])(
    "%s on a focused radio activates it and fires the PUT after the debounce",
    (key) => {
      document.body.innerHTML = panelHtml("light");
      vi.mocked(ajaxCall).mockReturnValue(
        mockDone(successResponse("dark"), createMockXhr({ status: 200 })),
      );
      initDisplayPreferences();

      getRadio("dark").focus();
      $(getRadio("dark")).trigger($.Event("keydown", { key }));

      expect(getRadio("dark").getAttribute("aria-checked")).toBe("true");
      expect(vi.mocked(ajaxCall)).not.toHaveBeenCalled();

      vi.advanceTimersByTime(300);
      expect(vi.mocked(ajaxCall)).toHaveBeenCalledWith(
        "put",
        ACTION_URL,
        expectedPayload("dark"),
      );
    },
  );

  it("coalesces a rapid ArrowRight burst into a single trailing PUT", () => {
    document.body.innerHTML = panelHtml("light");
    vi.mocked(ajaxCall).mockReturnValue(
      mockDone(successResponse("light"), createMockXhr({ status: 200 })),
    );
    initDisplayPreferences();

    // light -> dark -> system -> light, all within the debounce window.
    getRadio("light").focus();
    $(getRadio("light")).trigger($.Event("keydown", { key: "ArrowRight" }));
    $(getRadio("dark")).trigger($.Event("keydown", { key: "ArrowRight" }));
    $(getRadio("system")).trigger($.Event("keydown", { key: "ArrowRight" }));

    vi.advanceTimersByTime(300);

    expect(vi.mocked(ajaxCall)).toHaveBeenCalledTimes(1);
    expect(vi.mocked(ajaxCall)).toHaveBeenCalledWith(
      "put",
      ACTION_URL,
      expectedPayload("light"),
    );
  });

  it("restores focus to the originating control after the PUT resolves (WCAG 2.4.3)", () => {
    document.body.innerHTML = panelHtml("system");
    vi.mocked(ajaxCall).mockReturnValue(
      mockDone(successResponse("dark"), createMockXhr({ status: 200 })),
    );
    initDisplayPreferences();

    getRadio("dark").focus();
    $(getRadio("dark")).trigger("click");
    vi.advanceTimersByTime(300);

    // The guard disabled+blurred the panel mid-flight; on resolve focus returns
    // to the control the user was on.
    expect(document.activeElement).toBe(getRadio("dark"));
  });

  it("disables every panel control while the PUT is in flight (reentrancy guard engaged only in firePut)", () => {
    document.body.innerHTML = panelHtml("system");
    // Pending promise: neither done nor fail fires, so the guard stays engaged.
    vi.mocked(ajaxCall).mockReturnValue(createMockJqXHRChainable());
    initDisplayPreferences();

    $(getRadio("dark")).trigger("click");
    vi.advanceTimersByTime(300);

    expect(getRadio("light").getAttribute("disabled")).toBe("disabled");
    expect(getRadio("dark").getAttribute("disabled")).toBe("disabled");
    expect(getRadio("system").getAttribute("disabled")).toBe("disabled");
    expect(
      document
        .getElementById("SettingsDefaultViewSelect")
        ?.getAttribute("disabled"),
    ).toBe("disabled");
    expect(
      document
        .getElementById("SettingsDensitySelect")
        ?.getAttribute("disabled"),
    ).toBe("disabled");
  });
});
