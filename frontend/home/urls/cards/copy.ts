import { bootstrap } from "../../../lib/globals.js";
import { APP_CONFIG } from "../../../lib/config.js";
import { emit } from "../../../lib/metrics-client.js";

import { UI_EVENTS } from "../../../types/metrics-events.js";
import { URL_COPY_RESULT } from "../../../types/metrics-dim-values.js";
export async function copyURLString(
  url: string,
  urlBtnCopy: Element,
): Promise<void> {
  const urlBtnCopyTooltip = bootstrap.Tooltip.getOrCreateInstance(urlBtnCopy);
  try {
    await navigator.clipboard.writeText(url);
    emit({ event: UI_EVENTS.UI_URL_COPY, result: URL_COPY_RESULT.SUCCESS });

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
    emit({ event: UI_EVENTS.UI_URL_COPY, result: URL_COPY_RESULT.FAILURE });
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
