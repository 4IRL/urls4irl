import { $, bootstrap } from "../../../../lib/globals.js";
import { APP_CONFIG } from "../../../../lib/config.js";
import { showCreateURLTagForm } from "../../tags/create.js";

export function createAddTagIcon() {
  const WIDTH_HEIGHT_PX = "24px";
  const SVG_NS = "http://www.w3.org/2000/svg";
  const addTagOuterIconSvg = $(document.createElementNS(SVG_NS, "svg"));
  const addTagInnerIconPath = $(document.createElementNS(SVG_NS, "path"));
  const addTagInnerIconRect = $(document.createElementNS(SVG_NS, "rect"));
  const path =
    "M21,12l-4.37,6.16C16.26,18.68,15.65,19,15,19h-3l0-2h3l3.55-5L15,7H5v3H3V7c0-1.1,0.9-2,2-2h10c0.65,0,1.26,0.31,1.63,0.84 L21,12z M10,15H7v-3H5v3H2v2h3v3h2v-3h3V15z";

  const strokeSettings = {
    stroke: "#000", // or any specific color like "#000"
    "stroke-width": "1", // thickness, increase as needed (e.g., 2, 3, etc.)
  };

  addTagInnerIconPath.attr({
    d: path,
    ...strokeSettings,
  });

  addTagInnerIconRect.attr({
    fill: "none",
    height: 16,
    width: 16,
  });

  addTagOuterIconSvg
    .attr({
      xmlns: SVG_NS,
      width: WIDTH_HEIGHT_PX,
      height: WIDTH_HEIGHT_PX,
      fill: "currentColor",
      viewBox: "0 0 24 24",
    })
    .append(addTagInnerIconRect)
    .append(addTagInnerIconPath);

  return addTagOuterIconSvg;
}

export function createAddTagBtn(urlCard) {
  const urlTagBtnCreate = $(document.createElement("button"));

  // Add a tag button
  urlTagBtnCreate
    .addClass(
      "btn btn-info urlTagBtnCreate tabbable flex-column justify-center fourty-p-width fourty-p-height",
    )
    .attr({
      type: "button",
      "data-bs-toggle": "tooltip",
      "data-bs-custom-class": "urlTagBtnCreate-tooltip",
      "data-bs-placement": "top",
      "data-bs-trigger": "hover",
      "data-bs-title": `${APP_CONFIG.strings.ADD_URL_TAG_TOOLTIP}`,
    })
    .disableTab()
    .onExact("click", function (e) {
      showCreateURLTagForm(urlCard, urlTagBtnCreate);
    })
    .append(createAddTagIcon());

  bootstrap.Tooltip.getOrCreateInstance(urlTagBtnCreate);
  return urlTagBtnCreate;
}
