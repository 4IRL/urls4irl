import { bootstrap } from "../../../lib/globals.js";
import { APP_CONFIG } from "../../../lib/config.js";
import { emit } from "../../../lib/metrics-client.js";

export async function copyURLString(
  url: string,
  urlBtnCopy: Element,
): Promise<void> {
  const urlBtnCopyTooltip = bootstrap.Tooltip.getOrCreateInstance(urlBtnCopy);
  try {
    await navigator.clipboard.writeText(url);
    emit("ui_url_copy", { result: "success" });

    urlBtnCopyTooltip.setContent({
      ".tooltip-inner": `${APP_CONFIG.strings.COPIED_URL_TOOLTIP}`,
    });
    urlBtnCopyTooltip.show();

    // Hide after 2 seconds
    setTimeout(() => {
      urlBtnCopyTooltip.hide();
      // Reset content for next use
      setTimeout(() => {
        urlBtnCopyTooltip.setContent({
          ".tooltip-inner": `${APP_CONFIG.strings.COPY_URL_TOOLTIP}`,
        });
      }, 200);
    }, 1500);
  } catch {
    emit("ui_url_copy", { result: "failure" });
    urlBtnCopyTooltip.setContent({
      ".tooltip-inner": `${APP_CONFIG.strings.COPIED_URL_FAILURE_TOOLIP}`,
    });
    urlBtnCopyTooltip.show();

    setTimeout(() => {
      urlBtnCopyTooltip.hide();
      // Reset content for next use
      setTimeout(() => {
        urlBtnCopyTooltip.setContent({
          ".tooltip-inner": `${APP_CONFIG.strings.COPY_URL_TOOLTIP}`,
        });
      }, 200);
    }, 1500);
  }
}
