import {
  clearControllerInFlight,
  isAnyOtherControllerInFlight,
  registerControllerInFlight,
} from "../removal-shared.js";

vi.mock("../../lib/globals.js", () => ({
  $: window.jQuery,
  jQuery: window.jQuery,
  bootstrap: window.bootstrap,
}));

// DD-15: unit-test the cross-controller in-flight registry directly — it is a
// plain module-level Set, so no DOM/jQuery interaction is exercised here.
describe("removal-shared in-flight registry (DD-9/DD-15)", () => {
  afterEach(() => {
    // Clear every id any test could have registered so module-level Set state
    // never leaks between tests.
    clearControllerInFlight("dataExport");
    clearControllerInFlight("accountDelete");
  });

  it("reports nothing in flight before anything registers", () => {
    expect(isAnyOtherControllerInFlight("accountDelete")).toBe(false);
    expect(isAnyOtherControllerInFlight("dataExport")).toBe(false);
  });

  it("detects a different controller in flight but excludes the caller's own id", () => {
    registerControllerInFlight("dataExport");

    // A different id is in flight → true for the account-delete caller.
    expect(isAnyOtherControllerInFlight("accountDelete")).toBe(true);
    // The only in-flight id is the caller's own → false (self-exclusion).
    expect(isAnyOtherControllerInFlight("dataExport")).toBe(false);
  });

  it("clears the registration so nothing is in flight again", () => {
    registerControllerInFlight("dataExport");
    clearControllerInFlight("dataExport");

    expect(isAnyOtherControllerInFlight("accountDelete")).toBe(false);
    expect(isAnyOtherControllerInFlight("dataExport")).toBe(false);
  });
});
