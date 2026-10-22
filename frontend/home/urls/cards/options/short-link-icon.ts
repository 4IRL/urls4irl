import { $ } from "../../../../lib/globals.js";

// bootstrap-icons "link-45deg"
const LINK_ICON_PATH_UPPER =
  "M4.715 6.542 3.343 7.914a3 3 0 1 0 4.243 4.243l1.828-1.829A3 3 0 0 0 8.586 5.5L8 6.086a1 1 0 0 0-.154.199 2 2 0 0 1 .861 3.337L6.88 11.45a2 2 0 1 1-2.83-2.83l.793-.792a4 4 0 0 1-.128-1.287z";
const LINK_ICON_PATH_LOWER =
  "M6.586 4.672A3 3 0 0 0 7.414 9.5l.775-.776a2 2 0 0 1-.896-3.346L9.12 3.55a2 2 0 1 1 2.83 2.83l-.793.792c.112.42.155.855.128 1.287l1.372-1.372a3 3 0 1 0-4.243-4.243z";

/** The decorative link glyph shared by the short-link button and status line. */
export function createShortLinkIcon({
  sizePx,
}: {
  sizePx: number;
}): JQuery<SVGSVGElement> {
  const SVG_NS = "http://www.w3.org/2000/svg";
  const iconSvg = $(document.createElementNS(SVG_NS, "svg"));

  iconSvg
    .attr({
      xmlns: SVG_NS,
      width: `${sizePx}px`,
      height: `${sizePx}px`,
      fill: "currentColor",
      viewBox: "0 0 16 16",
      "aria-hidden": "true",
    })
    .append(
      $(document.createElementNS(SVG_NS, "path")).attr({
        d: LINK_ICON_PATH_UPPER,
      }),
      $(document.createElementNS(SVG_NS, "path")).attr({
        d: LINK_ICON_PATH_LOWER,
      }),
    );

  return iconSvg;
}
