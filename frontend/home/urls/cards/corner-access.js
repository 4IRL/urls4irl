import { $ } from "../../../lib/globals.js";
import { accessLink } from "./access.js";

// Icon to visit URL, situated in top right corner of URL card
export function createGoToURLIcon(urlString) {
  const WIDTH_HEIGHT_PX = "20px";
  const SVG_NS = "http://www.w3.org/2000/svg";
  const goToUrlOuterIconSvg = $(document.createElementNS(SVG_NS, "svg"));
  const goToUrlInnerIconPath = $(document.createElementNS(SVG_NS, "path"));
  const path =
    "M14 0a2 2 0 0 1 2 2v12a2 2 0 0 1-2 2H2a2 2 0 0 1-2-2V2a2 2 0 0 1 2-2zM5.904 10.803 10 6.707v2.768a.5.5 0 0 0 1 0V5.5a.5.5 0 0 0-.5-.5H6.525a.5.5 0 1 0 0 1h2.768l-4.096 4.096a.5.5 0 0 0 .707.707";

  goToUrlInnerIconPath.attr({
    d: path,
  });

  goToUrlOuterIconSvg
    .attr({
      xmlns: SVG_NS,
      width: WIDTH_HEIGHT_PX,
      height: WIDTH_HEIGHT_PX,
      fill: "currentColor",
      class: "bi bi-arrow-up-right-square-fill pointerable",
      viewBox: "0 0 16 16",
    })
    .append(goToUrlInnerIconPath);

  const btn = $(document.createElement("button"))
    .append(goToUrlOuterIconSvg)
    .addClass("self-start goToUrlIcon")
    .enableTab()
    .onExact("click", (e) => {
      accessLink(urlString);
    });

  return btn;
}
