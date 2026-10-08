import {
  createParamTrimBlock,
  TRIM_FLUSH_KEY,
  TrimMode,
} from "../param-trim-block.js";
import { UI_EVENTS } from "../../../../types/metrics-events.js";
import {
  URL_PARAMS_TRIMMED_ACTION,
  URL_PARAMS_TRIMMED_FORM,
} from "../../../../types/metrics-dim-values.js";

const { mockMetricsClient } = await vi.hoisted(
  async () =>
    await import("../../../../__tests__/helpers/mock-metrics-client.js"),
);

vi.mock("../../../../lib/metrics-client.js", () => mockMetricsClient());

const URL_WITH_PARAMS = "https://a.com/p?ref=1&size=L&color=red";

function mount({ mode }: { mode: TrimMode }): JQuery<HTMLElement> {
  const wrap = createParamTrimBlock({ mode, urlCard: null });
  window.jQuery(document.body).append(wrap);
  (wrap.data(TRIM_FLUSH_KEY) as (rawValue: string) => void)(URL_WITH_PARAMS);
  return wrap;
}

describe("param trim metrics — UI_URL_PARAMS_TRIMMED { form, action }", () => {
  beforeEach(() => {
    document.body.innerHTML = "";
    vi.clearAllMocks();
  });

  it("emits action 'toggle' with form 'url_create' for a chip click in CREATE mode", async () => {
    const { emit } = await import("../../../../lib/metrics-client.js");
    const wrap = mount({ mode: TrimMode.CREATE });

    wrap.find("button.urlParamTrimChip").first().trigger("click");

    expect(emit).toHaveBeenCalledTimes(1);
    expect(emit).toHaveBeenCalledWith({
      event: UI_EVENTS.UI_URL_PARAMS_TRIMMED,
      form: URL_PARAMS_TRIMMED_FORM.URL_CREATE,
      action: URL_PARAMS_TRIMMED_ACTION.TOGGLE,
    });
  });

  it("emits form 'url_string_edit' in URL mode", async () => {
    const { emit } = await import("../../../../lib/metrics-client.js");
    const wrap = mount({ mode: TrimMode.URL });

    wrap.find("button.urlParamTrimChip").first().trigger("click");

    expect(emit).toHaveBeenCalledWith({
      event: UI_EVENTS.UI_URL_PARAMS_TRIMMED,
      form: URL_PARAMS_TRIMMED_FORM.URL_STRING_EDIT,
      action: URL_PARAMS_TRIMMED_ACTION.TOGGLE,
    });
  });

  it("emits 'drop_all' and 'keep_all' for the bulk buttons", async () => {
    const { emit } = await import("../../../../lib/metrics-client.js");
    const wrap = mount({ mode: TrimMode.CREATE });

    wrap.find(".urlParamTrimBtn").eq(0).trigger("click");
    wrap.find(".urlParamTrimBtn").eq(1).trigger("click");

    expect(emit).toHaveBeenNthCalledWith(1, {
      event: UI_EVENTS.UI_URL_PARAMS_TRIMMED,
      form: URL_PARAMS_TRIMMED_FORM.URL_CREATE,
      action: URL_PARAMS_TRIMMED_ACTION.DROP_ALL,
    });
    expect(emit).toHaveBeenNthCalledWith(2, {
      event: UI_EVENTS.UI_URL_PARAMS_TRIMMED,
      form: URL_PARAMS_TRIMMED_FORM.URL_CREATE,
      action: URL_PARAMS_TRIMMED_ACTION.KEEP_ALL,
    });
  });

  it("emits one toggle for Enter and Space keydown, none for a held key", async () => {
    const { emit } = await import("../../../../lib/metrics-client.js");
    const wrap = mount({ mode: TrimMode.CREATE });
    // Each toggle re-renders the chips, so re-query before every keypress.
    const chip = () => wrap.find("button.urlParamTrimChip").first();

    chip().trigger(window.jQuery.Event("keydown", { key: "Enter" }));
    chip().trigger(window.jQuery.Event("keydown", { key: " " }));
    expect(emit).toHaveBeenCalledTimes(2);

    vi.clearAllMocks();
    chip().trigger(
      window.jQuery.Event("keydown", {
        key: "Enter",
        originalEvent: new KeyboardEvent("keydown", {
          key: "Enter",
          repeat: true,
        }),
      }),
    );
    expect(emit).not.toHaveBeenCalled();
  });

  it("does not emit when a re-parse resets the drops", async () => {
    const { emit } = await import("../../../../lib/metrics-client.js");
    const wrap = mount({ mode: TrimMode.CREATE });
    wrap.find("button.urlParamTrimChip").first().trigger("click");
    vi.clearAllMocks();

    (wrap.data(TRIM_FLUSH_KEY) as (rawValue: string) => void)(
      "https://a.com/p?other=1",
    );

    expect(emit).not.toHaveBeenCalled();
  });

  it("does not emit a bulk action that changes nothing", async () => {
    const { emit } = await import("../../../../lib/metrics-client.js");
    const wrap = mount({ mode: TrimMode.CREATE });

    // Nothing is dropped yet, so Keep all is a no-op.
    wrap.find(".urlParamTrimBtn").eq(1).trigger("click");

    expect(emit).not.toHaveBeenCalled();
  });

  it("does not emit on mount, re-parse or header collapse toggle", async () => {
    const { emit } = await import("../../../../lib/metrics-client.js");
    const wrap = mount({ mode: TrimMode.CREATE });

    wrap.find(".urlParamTrimHeader").trigger("click");

    expect(emit).not.toHaveBeenCalled();
  });
});
