"use strict";

function createAccessLinkIcon() {
  const WIDTH_HEIGHT_PX = "20px";
  const SVG_NS = "http://www.w3.org/2000/svg";
  const accessURLOuterIconSvg = $(document.createElementNS(SVG_NS, "svg"));
  const accessURLInnerIconPathSquare = $(
    document.createElementNS(SVG_NS, "path"),
  ).attr({ "fill-rule": "evenodd" });
  const accessURLInnerIconPathArrow = $(
    document.createElementNS(SVG_NS, "path"),
  ).attr({ "fill-rule": "evenodd" });
  const squarePath =
    "M8.636 3.5a.5.5 0 0 0-.5-.5H1.5A1.5 1.5 0 0 0 0 4.5v10A1.5 1.5 0 0 0 1.5 16h10a1.5 1.5 0 0 0 1.5-1.5V7.864a.5.5 0 0 0-1 0V14.5a.5.5 0 0 1-.5.5h-10a.5.5 0 0 1-.5-.5v-10a.5.5 0 0 1 .5-.5h6.636a.5.5 0 0 0 .5-.5";
  const arrowPath =
    "M16 .5a.5.5 0 0 0-.5-.5h-5a.5.5 0 0 0 0 1h3.793L6.146 9.146a.5.5 0 1 0 .708.708L15 1.707V5.5a.5.5 0 0 0 1 0z";

  const strokeSettings = {
    stroke: "#000", // or any specific color like "#000"
    "stroke-width": "1", // thickness, increase as needed (e.g., 2, 3, etc.)
    "stroke-linecap": "round", // optional, for smoother ends
    "stroke-linejoin": "round", // optional, for smoother joins
  };

  accessURLInnerIconPathSquare.attr({
    d: squarePath,
    ...strokeSettings,
  });

  accessURLInnerIconPathArrow.attr({
    d: arrowPath,
    ...strokeSettings,
  });

  accessURLOuterIconSvg
    .attr({
      xmlns: SVG_NS,
      width: WIDTH_HEIGHT_PX,
      height: WIDTH_HEIGHT_PX,
      fill: "currentColor",
      class: "bi bi-box-arrow-up-right",
      viewBox: "0 0 16 16",
    })
    .append(accessURLInnerIconPathSquare)
    .append(accessURLInnerIconPathArrow);

  return accessURLOuterIconSvg;
}

function createAccessLinkBtn(url) {
  const urlBtnAccess = $(document.createElement("button"));

  urlBtnAccess
    .addClass(
      "btn btn-primary urlBtnAccess tabbable flex-column justify-center sixty-p-width fourty-p-height",
    )
    .attr({
      type: "button",
      "data-bs-toggle": "tooltip",
      "data-bs-custom-class": "urlBtnAccess-tooltip",
      "data-bs-placement": "top",
      "data-bs-offset": "10,0",
      "data-bs-trigger": "hover",
      "data-bs-title": `${STRINGS.ACCESS_URL_TOOLTIP}`,
    })
    .disableTab()
    .on("click", function (e) {
      e.stopPropagation();
      const tooltip = bootstrap.Tooltip.getInstance(this);
      if (tooltip) tooltip.hide();
      accessLink(url.urlString, this);
    });

  urlBtnAccess.append(createAccessLinkIcon());
  bootstrap.Tooltip.getOrCreateInstance(urlBtnAccess);
  return urlBtnAccess;
}
