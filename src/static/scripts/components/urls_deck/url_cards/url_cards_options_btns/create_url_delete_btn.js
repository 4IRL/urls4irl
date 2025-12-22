"use strict";

function createDeleteURLIcon() {
  const WIDTH_HEIGHT_PX = "28px";
  const SVG_NS = "http://www.w3.org/2000/svg";
  const deleteURLOuterIconSvg = $(document.createElementNS(SVG_NS, "svg"));
  const deleteURLInnerIconPathOuter = $(
    document.createElementNS(SVG_NS, "path"),
  ).attr({ fill: "none" });
  const deleteURLInnerIconPathInner = $(
    document.createElementNS(SVG_NS, "path"),
  );
  const outerPath = "M0 0h24v24H0V0z";
  const innerPath =
    "M16 9v10H8V9h8m-1.5-6h-5l-1 1H5v2h14V4h-3.5l-1-1zM18 7H6v12c0 1.1.9 2 2 2h8c1.1 0 2-.9 2-2V7z";

  deleteURLInnerIconPathOuter.attr({
    d: outerPath,
  });

  deleteURLInnerIconPathInner.attr({
    d: innerPath,
  });

  deleteURLOuterIconSvg
    .attr({
      xmlns: SVG_NS,
      width: WIDTH_HEIGHT_PX,
      height: WIDTH_HEIGHT_PX,
      fill: "currentColor",
      class: "bi bi-trash urlDeleteSvgIcon",
      viewBox: "0 0 24 24",
    })
    .append(deleteURLInnerIconPathOuter)
    .append(deleteURLInnerIconPathInner);

  return deleteURLOuterIconSvg;
}

function createDeleteURLBtn(url, urlCard, utubID) {
  const urlBtnDelete = $(document.createElement("button"));
  urlBtnDelete
    .addClass(
      "btn btn-danger urlBtnDelete tabbable flex-column justify-center fourty-p-width fourty-p-height",
    )
    .attr({
      type: "button",
      "data-bs-toggle": "tooltip",
      "data-bs-custom-class": "urlBtnDelete-tooltip",
      "data-bs-placement": "top",
      "data-bs-trigger": "hover",
      "data-bs-title": `${APP_CONFIG.strings.DELETE_URL_TOOLTIP}`,
    })
    .disableTab()
    .on("click", function (e) {
      e.stopPropagation();
      deleteURLShowModal(url.utubUrlID, urlCard, utubID);
    })
    .append(createDeleteURLIcon());

  bootstrap.Tooltip.getOrCreateInstance(urlBtnDelete);
  return urlBtnDelete;
}
