import { mockGlobalsWithTooltipInstance } from "./mock-globals.js";

describe("mockGlobalsWithTooltipInstance", () => {
  it("exposes exactly the four lib/globals.js exports on globalsMock", async () => {
    const { globalsMock } = await mockGlobalsWithTooltipInstance();

    expect(Object.keys(globalsMock).sort()).toEqual([
      "$",
      "bootstrap",
      "getInputValue",
      "jQuery",
    ]);
    expect(typeof globalsMock.$).toBe("function");
    expect(globalsMock.jQuery).toBe(globalsMock.$);
    expect(typeof globalsMock.getInputValue).toBe("function");
    expect(vi.isMockFunction(globalsMock.bootstrap.Tooltip.getInstance)).toBe(
      true,
    );
    expect(
      vi.isMockFunction(globalsMock.bootstrap.Tooltip.getOrCreateInstance),
    ).toBe(true);
  });

  it("gives the tooltip instance a distinct Mock fn per lifecycle method", async () => {
    const { tooltipInstance } = await mockGlobalsWithTooltipInstance();

    const fns = [
      tooltipInstance.setContent,
      tooltipInstance.show,
      tooltipInstance.hide,
      tooltipInstance.enable,
      tooltipInstance.disable,
    ];
    fns.forEach((fn) => expect(vi.isMockFunction(fn)).toBe(true));
    expect(new Set(fns).size).toBe(fns.length);
  });

  it("hands back the SAME instance from getInstance and getOrCreateInstance", async () => {
    const { tooltipInstance, globalsMock } =
      await mockGlobalsWithTooltipInstance();
    const element = document.createElement("button");

    expect(globalsMock.bootstrap.Tooltip.getInstance(element)).toBe(
      tooltipInstance,
    );
    expect(globalsMock.bootstrap.Tooltip.getOrCreateInstance(element)).toBe(
      tooltipInstance,
    );
  });

  it("returns a fresh set of mocks on each invocation", async () => {
    const firstInvocation = await mockGlobalsWithTooltipInstance();
    const secondInvocation = await mockGlobalsWithTooltipInstance();

    expect(firstInvocation.tooltipInstance).not.toBe(
      secondInvocation.tooltipInstance,
    );

    firstInvocation.tooltipInstance.hide();
    expect(firstInvocation.tooltipInstance.hide).toHaveBeenCalledTimes(1);
    expect(secondInvocation.tooltipInstance.hide).not.toHaveBeenCalled();
  });

  it("getInputValue reads the value from a selector string or a JQuery object", async () => {
    const { globalsMock } = await mockGlobalsWithTooltipInstance();
    document.body.innerHTML = `<input id="mockGlobalsInput" value="typed value" />`;

    expect(globalsMock.getInputValue("#mockGlobalsInput")).toBe("typed value");
    expect(globalsMock.getInputValue(globalsMock.$("#mockGlobalsInput"))).toBe(
      "typed value",
    );

    document.body.innerHTML = "";
  });
});
