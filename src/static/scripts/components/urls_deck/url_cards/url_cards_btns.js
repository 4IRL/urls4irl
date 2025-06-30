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

function createAddTagIcon() {
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
    //"stroke-linecap": "round",  // optional, for smoother ends
    //"stroke-linejoin": "round", // optional, for smoother joins
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

  const strokeSettings = {
    //"stroke": "none",      // thickness, increase as needed (e.g., 2, 3, etc.)
  };

  deleteURLInnerIconPathOuter.attr({
    d: outerPath,
    ...strokeSettings,
  });

  deleteURLInnerIconPathInner.attr({
    d: innerPath,
    ...strokeSettings,
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

// Create all the buttons necessary for a url card
function createURLOptionsButtons(url, urlCard) {
  const urlOptions = $(document.createElement("div")).addClass(
    "urlOptions justify-content-start flex-row gap-15p",
  );
  const urlBtnAccess = $(document.createElement("button"));
  const urlTagBtnCreate = $(document.createElement("button"));

  // Access the URL button
  urlBtnAccess
    .addClass(
      "btn btn-primary urlBtnAccess tabbable flex-column justify-center sixty-p-width fourty-p-height",
    )
    .attr({ type: "button" })
    .disableTab()
    .on("click", function (e) {
      e.stopPropagation();
      accessLink(url.urlString);
    });

  urlBtnAccess.append(createAccessLinkIcon());

  // Add a tag button
  urlTagBtnCreate
    .addClass(
      "btn btn-info urlTagBtnCreate tabbable flex-column justify-center fourty-p-width fourty-p-height",
    )
    .attr({ type: "button" })
    .disableTab()
    .on("click", function (e) {
      e.stopPropagation();
      showCreateURLTagForm(urlCard, urlTagBtnCreate);
    })
    .append(createAddTagIcon())
    .on("focus", function (e) {
      if ($(e.target).hasClass("cancel")) return;
      $(document).on("keyup.showURLTagCreate", function (e) {
        if (e.which === 13) showCreateURLTagForm(urlCard, urlTagBtnCreate);
      });
    })
    .on("blur", function () {
      $(document).off("keyup.showURLTagCreate");
    });

  urlOptions.append(urlBtnAccess).append(urlTagBtnCreate);

  if (url.canDelete) {
    const urlStringBtnUpdate = $(document.createElement("button"));
    const urlBtnDelete = $(document.createElement("button"));
    urlBtnDelete
      .addClass(
        "btn btn-danger urlBtnDelete tabbable flex-column justify-center fourty-p-width fourty-p-height",
      )
      .attr({ type: "button" })
      .disableTab()
      .on("click", function (e) {
        e.stopPropagation();
        deleteURLShowModal(url.utubUrlID, urlCard);
      })
      .append(createDeleteURLIcon());

    urlStringBtnUpdate
      .addClass(
        "btn btn-light urlStringBtnUpdate tabbable flex-column justify-center fourty-p-width fourty-p-height",
      )
      .attr({ type: "button" })
      .disableTab()
      .on("click", function (e) {
        e.stopPropagation();
        showUpdateURLStringForm(urlCard, urlStringBtnUpdate);
      })
      .append(createEditURLIcon());

    urlOptions.append(urlStringBtnUpdate).append(urlBtnDelete);
  }
  const urlCardLoadingIcon = $(document.createElement("div")).addClass(
    "urlCardDualLoadingRing",
  );
  urlOptions.append(urlCardLoadingIcon);

  return urlOptions;
}
