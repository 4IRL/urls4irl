/**
 * Tablist ARIA behavior for the user settings page controller.
 *
 * Covers the ARIA Authoring Practices Guide tablist pattern for the
 * isolated, dependency-free settings tab controller:
 *   - Clicking a tab updates `aria-selected` and the roving `tabindex`.
 *   - Arrow keys cycle through tabs (wrap-around at the ends).
 *   - Home / End jump to the first / last tab.
 *   - The `hidden` attribute on each tabpanel toggles in sync with selection.
 *   - Mouse activation focuses the panel; keyboard activation re-focuses the tab.
 *
 * No data-fetch/render modules exist for this controller, so there is nothing
 * to mock — the specs exercise only the tablist state machine.
 */

import { $ } from "../../lib/globals.js";
import {
  _resetSettingsPageForTests,
  initSettingsPage,
} from "../settings-page.js";

type TabId =
  | "SettingsTabAccount"
  | "SettingsTabStats"
  | "SettingsTabPrivacyData"
  | "SettingsTabUiSettings";
type PanelId =
  | "SettingsPanelAccount"
  | "SettingsPanelStats"
  | "SettingsPanelPrivacyData"
  | "SettingsPanelUiSettings";

const SETTINGS_HTML = `
  <main id="SettingsPage">
    <h1>Settings</h1>
    <div id="SettingsTablist" class="tablist" role="tablist" aria-label="Settings sections">
      <button type="button" id="SettingsTabAccount"     role="tab" aria-selected="true"  aria-controls="SettingsPanelAccount"     data-tab="account"      tabindex="0">Account</button>
      <button type="button" id="SettingsTabStats"       role="tab" aria-selected="false" aria-controls="SettingsPanelStats"       data-tab="stats"        tabindex="-1">Stats</button>
      <button type="button" id="SettingsTabPrivacyData" role="tab" aria-selected="false" aria-controls="SettingsPanelPrivacyData" data-tab="privacy_data" tabindex="-1">Privacy &amp; Data</button>
      <button type="button" id="SettingsTabUiSettings"  role="tab" aria-selected="false" aria-controls="SettingsPanelUiSettings"  data-tab="ui_settings"  tabindex="-1">Display</button>
    </div>
    <section role="tabpanel" id="SettingsPanelAccount"     aria-labelledby="SettingsTabAccount"     tabindex="0"><h2>Account</h2><p class="SettingsEmptyState">Coming soon</p></section>
    <section role="tabpanel" id="SettingsPanelStats"       aria-labelledby="SettingsTabStats"       tabindex="0" hidden><h2>Stats</h2><p class="SettingsEmptyState">Coming soon</p></section>
    <section role="tabpanel" id="SettingsPanelPrivacyData" aria-labelledby="SettingsTabPrivacyData" tabindex="0" hidden><h2>Privacy &amp; Data</h2><p class="SettingsEmptyState">Coming soon</p></section>
    <section role="tabpanel" id="SettingsPanelUiSettings"  aria-labelledby="SettingsTabUiSettings"  tabindex="0" hidden><h2>Display</h2><p class="SettingsEmptyState">Coming soon</p></section>
  </main>
`;

function getTab(tabId: TabId): HTMLButtonElement {
  return document.getElementById(tabId) as HTMLButtonElement;
}

function getPanel(panelId: PanelId): HTMLElement {
  return document.getElementById(panelId) as HTMLElement;
}

describe("settings-page tablist a11y", () => {
  beforeEach(() => {
    document.body.innerHTML = SETTINGS_HTML;
    initSettingsPage();
  });

  afterEach(() => {
    _resetSettingsPageForTests();
    document.body.innerHTML = "";
  });

  it("clicking the Stats tab updates aria-selected, roving tabindex, and panel visibility", () => {
    getTab("SettingsTabStats").click();

    expect(getTab("SettingsTabStats").getAttribute("aria-selected")).toBe(
      "true",
    );
    expect(getTab("SettingsTabStats").getAttribute("tabindex")).toBe("0");
    expect(getTab("SettingsTabAccount").getAttribute("aria-selected")).toBe(
      "false",
    );
    expect(getTab("SettingsTabAccount").getAttribute("tabindex")).toBe("-1");

    expect(getPanel("SettingsPanelStats").hasAttribute("hidden")).toBe(false);
    expect(getPanel("SettingsPanelAccount").hasAttribute("hidden")).toBe(true);
    expect(getPanel("SettingsPanelPrivacyData").hasAttribute("hidden")).toBe(
      true,
    );
    expect(getPanel("SettingsPanelUiSettings").hasAttribute("hidden")).toBe(
      true,
    );
  });

  it("ArrowRight from the focused Account tab activates Stats and keeps focus on the tab", () => {
    getTab("SettingsTabAccount").focus();
    $("#SettingsTabAccount").trigger($.Event("keydown", { key: "ArrowRight" }));

    expect(getTab("SettingsTabStats").getAttribute("aria-selected")).toBe(
      "true",
    );
    expect(getPanel("SettingsPanelStats").hasAttribute("hidden")).toBe(false);
    expect(document.activeElement).toBe(getTab("SettingsTabStats"));
  });

  it("ArrowLeft from the first tab (Account) wraps to the last (Display)", () => {
    getTab("SettingsTabAccount").focus();
    $("#SettingsTabAccount").trigger($.Event("keydown", { key: "ArrowLeft" }));

    expect(getTab("SettingsTabUiSettings").getAttribute("aria-selected")).toBe(
      "true",
    );
    expect(getPanel("SettingsPanelUiSettings").hasAttribute("hidden")).toBe(
      false,
    );
    expect(document.activeElement).toBe(getTab("SettingsTabUiSettings"));
  });

  it("ArrowRight from the last tab (Display) wraps to the first (Account)", () => {
    getTab("SettingsTabUiSettings").click();
    getTab("SettingsTabUiSettings").focus();
    $("#SettingsTabUiSettings").trigger(
      $.Event("keydown", { key: "ArrowRight" }),
    );

    expect(getTab("SettingsTabAccount").getAttribute("aria-selected")).toBe(
      "true",
    );
    expect(getPanel("SettingsPanelAccount").hasAttribute("hidden")).toBe(false);
    expect(document.activeElement).toBe(getTab("SettingsTabAccount"));
  });

  it("Home key jumps to the first tab (Account)", () => {
    getTab("SettingsTabUiSettings").click();
    getTab("SettingsTabUiSettings").focus();
    $("#SettingsTabUiSettings").trigger($.Event("keydown", { key: "Home" }));

    expect(getTab("SettingsTabAccount").getAttribute("aria-selected")).toBe(
      "true",
    );
    expect(getPanel("SettingsPanelAccount").hasAttribute("hidden")).toBe(false);
    expect(document.activeElement).toBe(getTab("SettingsTabAccount"));
  });

  it("End key jumps to the last tab (Display)", () => {
    getTab("SettingsTabAccount").focus();
    $("#SettingsTabAccount").trigger($.Event("keydown", { key: "End" }));

    expect(getTab("SettingsTabUiSettings").getAttribute("aria-selected")).toBe(
      "true",
    );
    expect(getPanel("SettingsPanelUiSettings").hasAttribute("hidden")).toBe(
      false,
    );
    expect(document.activeElement).toBe(getTab("SettingsTabUiSettings"));
  });

  it("an unrecognized key (Enter) on a tab leaves all tab state unchanged", () => {
    getTab("SettingsTabAccount").focus();
    $("#SettingsTabAccount").trigger($.Event("keydown", { key: "Enter" }));

    expect(getTab("SettingsTabAccount").getAttribute("aria-selected")).toBe(
      "true",
    );
    expect(getTab("SettingsTabAccount").getAttribute("tabindex")).toBe("0");
    expect(getTab("SettingsTabStats").getAttribute("aria-selected")).toBe(
      "false",
    );
    expect(getTab("SettingsTabStats").getAttribute("tabindex")).toBe("-1");

    expect(getPanel("SettingsPanelAccount").hasAttribute("hidden")).toBe(false);
    expect(getPanel("SettingsPanelStats").hasAttribute("hidden")).toBe(true);
    expect(getPanel("SettingsPanelPrivacyData").hasAttribute("hidden")).toBe(
      true,
    );
    expect(getPanel("SettingsPanelUiSettings").hasAttribute("hidden")).toBe(
      true,
    );
  });

  it("clicking a tab moves focus to that tab's panel (mouse activation)", () => {
    getTab("SettingsTabStats").click();

    expect(document.activeElement).toBe(getPanel("SettingsPanelStats"));
  });

  it("clicking the already-active tab leaves exactly one selected tab and one visible panel (idempotent)", () => {
    getTab("SettingsTabAccount").click();

    const selectedTabs = document.querySelectorAll(
      '#SettingsTablist [role="tab"][aria-selected="true"]',
    );
    expect(selectedTabs.length).toBe(1);
    expect(selectedTabs[0].id).toBe("SettingsTabAccount");

    const visiblePanels = Array.from(
      document.querySelectorAll('#SettingsPage [role="tabpanel"]'),
    ).filter((panel) => !panel.hasAttribute("hidden"));
    expect(visiblePanels.length).toBe(1);
    expect(visiblePanels[0].id).toBe("SettingsPanelAccount");
  });

  it("initSettingsPage with no #SettingsPage in the DOM is a no-op that binds no handlers", () => {
    document.body.innerHTML = "";
    initSettingsPage();

    const orphanTab = document.createElement("button");
    orphanTab.type = "button";
    orphanTab.setAttribute("role", "tab");
    orphanTab.id = "SettingsTabAccount";
    document.body.appendChild(orphanTab);

    expect(() => orphanTab.click()).not.toThrow();
  });

  it("a tab button with an unknown id is ignored without throwing", () => {
    const orphanTab = document.createElement("button");
    orphanTab.type = "button";
    orphanTab.setAttribute("role", "tab");
    orphanTab.id = "SettingsTabOrphan";
    document.getElementById("SettingsTablist")?.appendChild(orphanTab);

    initSettingsPage();

    expect(() => orphanTab.click()).not.toThrow();
    // The original Account tab is untouched: still the only selected tab.
    expect(getTab("SettingsTabAccount").getAttribute("aria-selected")).toBe(
      "true",
    );
  });
});
