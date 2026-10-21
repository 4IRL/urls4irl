import { AppEvents, on } from "../event-bus.js";
import { clearOpenForm, getOpenForm, setOpenForm } from "../modal-tracking.js";
import type { OpenFormId } from "../modal-tracking.js";

describe("modal-tracking", () => {
  let received: Array<OpenFormId | null>;
  let unsubscribe: () => void;

  beforeEach(() => {
    clearOpenForm();
    received = [];
    unsubscribe = on(AppEvents.FORM_MODE_CHANGED, ({ openForm }) => {
      received.push(openForm);
    });
  });

  afterEach(() => {
    unsubscribe();
    clearOpenForm();
  });

  it("emits FORM_MODE_CHANGED with the form id when a form opens", () => {
    setOpenForm("login");

    expect(getOpenForm()).toBe("login");
    expect(received).toEqual(["login"]);
  });

  it("emits FORM_MODE_CHANGED with null when the form clears", () => {
    setOpenForm("register");
    clearOpenForm();

    expect(getOpenForm()).toBeNull();
    expect(received).toEqual(["register", null]);
  });

  it("emits again when a different form replaces the open one", () => {
    setOpenForm("login");
    setOpenForm("register");

    expect(received).toEqual(["login", "register"]);
  });
});
