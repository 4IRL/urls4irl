import "bootstrap/dist/css/bootstrap.min.css";
import "./styles/base.css";
import "./styles/settings/settings-page.css";
import "./lib/security-check.js";
import { $ } from "./lib/globals.js";
import { AppEvents, on } from "./lib/event-bus.js";
import { registerJQueryPlugins } from "./lib/jquery-plugins.js";
import { setupCSRF } from "./lib/csrf.js";
import { initCookieBanner } from "./lib/cookie-banner.js";
import { initNavbarBackdrop, initNavbarRouting } from "./lib/navbar-shared.js";
import { initSettingsPage } from "./settings/settings-page.js";
import { initConnectedAccounts } from "./settings/connected-accounts.js";
import { initChangeUsername } from "./settings/change-username.js";
import { initChangePassword } from "./settings/change-password.js";
import { initChangeEmail } from "./settings/change-email.js";
import { initAccountRemoval } from "./settings/account-removal.js";
import { initLogoutEverywhere } from "./settings/logout-everywhere.js";
import { initDataExport } from "./settings/data-export.js";

registerJQueryPlugins();
setupCSRF();

$(document).ready(() => {
  initCookieBanner();
  initNavbarRouting();
  initNavbarBackdrop();
  initSettingsPage();
  initConnectedAccounts();
  initChangeUsername();
  initChangePassword();
  initChangeEmail();
  initAccountRemoval();
  initLogoutEverywhere();
  initDataExport();

  // Cross-tab export-status toast (DD-6). A single global subscription mirrors
  // the export controller's in-panel status updates into the always-mounted
  // #SettingsGlobalStatusToast aria-live region, but only when the Privacy &
  // Data panel is NOT the visible one (DD-16) — otherwise a screen-reader user
  // on that panel would hear each status announced twice (once from the in-panel
  // #SettingsExportStatus alert, once from the global toast). The optional chain
  // also makes this a safe no-op in a test DOM that omits the panel entirely.
  on(AppEvents.DATA_EXPORT_STATUS_CHANGED, ({ message }) => {
    const privacyPanel = document.getElementById("SettingsPanelPrivacyData");
    if (privacyPanel?.hasAttribute("hidden")) {
      $("#SettingsGlobalStatusToast").text(message);
    }
  });
});
