import { afterEach, beforeEach, describe, expect, it } from "vitest";

import {
  applyInert,
  hideBackdrop,
  restoreInert,
  showBackdrop,
} from "../modal-chrome.js";

function el(id: string): HTMLElement {
  const found = document.getElementById(id);
  if (found === null) throw new Error(`missing #${id}`);
  return found;
}

function inertIds(): string[] {
  return Array.from(document.body.children)
    .filter((child) => child.hasAttribute("inert"))
    .map((child) => child.id);
}

describe("modal-chrome", () => {
  beforeEach(() => {
    document.body.innerHTML = `
      <div id="someModal"></div>
      <div id="panelSettingsRoot"><div id="panelSettingsBackdrop" class="hidden"></div></div>
      <main id="mainPanel"></main>
      <footer id="pageFooter"></footer>
      <script id="inlineScript"></script>
      <style id="inlineStyle"></style>
      <template id="inlineTemplate"></template>
    `;
  });

  afterEach(() => {
    restoreInert();
    document.body.innerHTML = "";
  });

  it("inerts every body child except the root, script, style and template", () => {
    applyInert();

    expect(inertIds()).toEqual(["someModal", "mainPanel", "pageFooter"]);
    expect(el("panelSettingsRoot").hasAttribute("inert")).toBe(false);
    for (const id of ["inlineScript", "inlineStyle", "inlineTemplate"]) {
      expect(el(id).hasAttribute("inert")).toBe(false);
    }
  });

  it("keeps an already-inert element inert after restore", () => {
    el("pageFooter").setAttribute("inert", "");
    applyInert();
    restoreInert();

    expect(inertIds()).toEqual(["pageFooter"]);
  });

  it("restores cleanly after applyInert is called twice", () => {
    el("pageFooter").setAttribute("inert", "");
    applyInert();
    applyInert();
    restoreInert();

    expect(inertIds()).toEqual(["pageFooter"]);
  });

  it("toggles the backdrop classes", () => {
    const backdrop = el("panelSettingsBackdrop");
    showBackdrop();
    expect(backdrop.classList.contains("hidden")).toBe(false);
    expect(backdrop.classList.contains("panelSettingsBackdrop--show")).toBe(
      true,
    );

    hideBackdrop();
    expect(backdrop.classList.contains("hidden")).toBe(true);
    expect(backdrop.classList.contains("panelSettingsBackdrop--show")).toBe(
      false,
    );
  });
});
