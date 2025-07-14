"use strict";

function createEditURLIcon() {
  const WIDTH_HEIGHT_PX = "16px";
  const SVG_NS = "http://www.w3.org/2000/svg";
  const editURLOuterIconSvg = $(document.createElementNS(SVG_NS, "svg"));
  const editURLInnerIconPath = $(document.createElementNS(SVG_NS, "path"));
  const path =
    "M12.854.146a.5.5 0 0 0-.707 0L10.5 1.793 14.207 5.5l1.647-1.646a.5.5 0 0 0 0-.708zm.646 6.061L9.793 2.5 3.293 9H3.5a.5.5 0 0 1 .5.5v.5h.5a.5.5 0 0 1 .5.5v.5h.5a.5.5 0 0 1 .5.5v.5h.5a.5.5 0 0 1 .5.5v.207zm-7.468 7.468A.5.5 0 0 1 6 13.5V13h-.5a.5.5 0 0 1-.5-.5V12h-.5a.5.5 0 0 1-.5-.5V11h-.5a.5.5 0 0 1-.5-.5V10h-.5a.5.5 0 0 1-.175-.032l-.179.178a.5.5 0 0 0-.11.168l-2 5a.5.5 0 0 0 .65.65l5-2a.5.5 0 0 0 .168-.11z";

  const strokeSettings = {
    stroke: "#000", // or any specific color like "#000"
    "stroke-width": "1", // thickness, increase as needed (e.g., 2, 3, etc.)
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

function createEditURLBtn(urlCard) {
  const urlStringBtnUpdate = $(document.createElement("button"));

  urlStringBtnUpdate
    .addClass(
      "btn btn-light urlStringBtnUpdate tabbable flex-column justify-center fourty-p-width fourty-p-height",
    )
    .attr({
      type: "button",
      "data-bs-toggle": "tooltip",
      "data-bs-custom-class": "urlStringBtnUpdate-tooltip",
      "data-bs-placement": "top",
      "data-bs-trigger": "hover",
      "data-bs-title": `${STRINGS.EDIT_URL_TOOLTIP}`,
    })
    .disableTab()
    .on("click", function (e) {
      e.stopPropagation();
      showUpdateURLStringForm(urlCard, urlStringBtnUpdate);
    })
    .append(createEditURLIcon());

  bootstrap.Tooltip.getOrCreateInstance(urlStringBtnUpdate);
  return urlStringBtnUpdate;
}
