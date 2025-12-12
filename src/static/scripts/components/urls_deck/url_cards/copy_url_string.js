"use strict";

async function copyURLString(url, urlBtnCopy) {
  const urlBtnCopyTooltip = bootstrap.Tooltip.getOrCreateInstance(urlBtnCopy);
  try {
    await navigator.clipboard.writeText(url);

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
  } catch (err) {
    urlBtnCopyTooltip.setContent({
      ".tooltip-inner": `${APP_CONFIG.strings.COPIED_URL_FAILURE_TOOLIP}`,
    });
    urlBtnCopyTooltip.show();
    console.log("Couldn't copy url", err);

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
