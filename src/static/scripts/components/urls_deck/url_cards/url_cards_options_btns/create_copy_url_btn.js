"use strict";

function createCopyURLIcon() {
  const WIDTH_HEIGHT_PX = "16px";
  const SVG_NS = "http://www.w3.org/2000/svg";
  const editURLOuterIconSvg = $(document.createElementNS(SVG_NS, "svg"));
  const editURLInnerIconPath = $(document.createElementNS(SVG_NS, "path"));
  const path =
    "M4 2a2 2 0 0 1 2-2h8a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2zm2-1a1 1 0 0 0-1 1v8a1 1 0 0 0 1 1h8a1 1 0 0 0 1-1V2a1 1 0 0 0-1-1zM2 5a1 1 0 0 0-1 1v8a1 1 0 0 0 1 1h8a1 1 0 0 0 1-1v-1h1v1a2 2 0 0 1-2 2H2a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2h1v1z";

  const strokeSettings = {
    stroke: "#000", // or any specific color like "#000"
    "stroke-width": "1", // thickness, increase as needed (e.g., 2, 3, etc.)
    "fill-rule": "evenodd",
  };

  editURLInnerIconPath.attr({
    d: path,
    ...strokeSettings,
  });

  editURLOuterIconSvg
    .attr({
      xmlns: SVG_NS,
      width: WIDTH_HEIGHT_PX,
      height: WIDTH_HEIGHT_PX,
      fill: "currentColor",
      viewBox: "0 0 16 16",
    })
    .append(editURLInnerIconPath);

  return editURLOuterIconSvg;
}

function createCopyURLBtn(url) {
  const urlBtnCopy = $(document.createElement("button"));

  urlBtnCopy
    .addClass(
      "btn btn-info urlBtnCopy tabbable flex-column flex-center justify-center fourty-p-width fourty-p-height",
    )
    .attr({
      type: "button",
      "data-bs-toggle": "tooltip",
      "data-bs-custom-class": "urlBtnCopy-tooltip",
      "data-bs-placement": "top",
      "data-bs-title": `${APP_CONFIG.strings.COPY_URL_TOOLTIP}`,
    })
    .disableTab()
    .on("click", function (e) {
      e.stopPropagation();
      copyURLString(url.urlString, this);
    })
    .append(createCopyURLIcon())
    .on("blur", function () {
      $(document).off("keyup.copyURL");
    });

  bootstrap.Tooltip.getOrCreateInstance(urlBtnCopy);
  return urlBtnCopy;
}
