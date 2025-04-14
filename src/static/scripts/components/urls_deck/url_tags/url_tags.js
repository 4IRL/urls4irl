"use strict";

// Hide tag deletion button when needed
function disableTagRemovalInURLCard(urlCard) {
  const allTagsDelBtns = urlCard.find(".urlTagBtnDelete");
  for (let i = 0; i < allTagsDelBtns.length; i++) {
    $(allTagsDelBtns[i]).addClass("hidden");
  }
}

// Show tag deletion when needed
function enableTagRemovalInURLCard(urlCard) {
  const allTagsDelBtns = urlCard.find(".urlTagBtnDelete");
  for (let i = 0; i < allTagsDelBtns.length; i++) {
    $(allTagsDelBtns[i]).removeClass("hidden");
  }
}

function isTagInURL(utubTagID, urlCard) {
  return (
    urlCard.find(
      ".urlTagsContainer > .tagBadge[data-utub-tag-id=" + utubTagID + "]",
    ).length > 0
  );
}

// Create the outer container for the tag badges
function createTagBadgesAndWrap(dictTags, tagArray, urlCard) {
  const tagBadgesWrap = $(document.createElement("div")).addClass(
    "urlTagsContainer flex-row flex-start",
  );

  for (let j in tagArray) {
    // Find applicable tags in dictionary to apply to URL card
    let tag = dictTags.find(function (e) {
      if (e.id === tagArray[j]) {
        return e;
      }
    });

    let tagSpan = createTagBadgeInURL(tag.id, tag.tagString, urlCard);

    $(tagBadgesWrap).append(tagSpan);
  }

  return tagBadgesWrap;
}

function createTagInputBlock(urlCard) {
  const urlTagCreateTextInputContainer = makeTextInput(
    "urlTag",
    METHOD_TYPES.CREATE.description,
  )
    .addClass("createUrlTagWrap")
    .css("display", "none");

  urlTagCreateTextInputContainer.find("label").text("Tag");

  // Customize the input text box for the Url title
  const urlTagTextInput = urlTagCreateTextInputContainer
    .find("input")
    .prop("minLength", CONSTANTS.TAGS_MIN_LENGTH)
    .prop("maxLength", CONSTANTS.TAGS_MAX_LENGTH);

  setFocusEventListenersOnCreateURLTagInput(urlTagTextInput, urlCard);

  // Create Url Title submit button
  const urlTagSubmitBtnCreate = makeSubmitButton(30).addClass(
    "urlTagSubmitBtnCreate",
  );

  urlTagSubmitBtnCreate
    .find(".submitButton")
    .on("click.createURLTag", function () {
      createURLTag(urlTagTextInput, urlCard);
    })
    .on("focus.createURLTag", function () {
      $(document).on("keyup.createURLTag", function (e) {
        if (e.which === 13) createURLTag(urlTagTextInput, urlCard);
      });
    })
    .on("blur.createURLTag", function () {
      $(document).off("keyup.createURLTag");
    });

  // Create Url Title cancel button
  const urlTagCancelBtnCreate = makeCancelButton(30).addClass(
    "urlTagCancelBtnCreate",
  );

  urlTagCancelBtnCreate
    .find(".cancelButton")
    .on("click.createURLTag", function (e) {
      e.stopPropagation();
      hideAndResetCreateURLTagForm(urlCard);
    })
    .offAndOn("focus.createURLTag", function () {
      $(document).on("keyup.createURLTag", function (e) {
        if (e.which === 13) hideAndResetCreateURLTagForm(urlCard);
      });
    })
    .offAndOn("blur.createURLTag", function () {
      $(document).off("keyup.createURLTag");
    });

  urlTagCreateTextInputContainer
    .append(urlTagSubmitBtnCreate)
    .append(urlTagCancelBtnCreate);

  return urlTagCreateTextInputContainer;
}

function setFocusEventListenersOnCreateURLTagInput(urlTagInput, urlCard) {
  urlTagInput.offAndOn("focus.createURLTagFocus", function () {
    $(document).offAndOn("keyup.createURLTagFocus", function (e) {
      switch (e.which) {
        case 13:
          // Handle enter key pressed
          createURLTag(urlTagInput, urlCard);
          break;
        case 27:
          // Handle escape key pressed
          hideAndResetCreateURLTagForm(urlCard);
          break;
        default:
        /* no-op */
      }
    });
  });

  urlTagInput.offAndOn("blur.createURLTagFocus", function () {
    $(document).off("keyup.createURLTagFocus");
  });
}

// Handle URL deck display changes related to creating a new tag
function createTagBadgeInURL(utubTagID, tagString, urlCard) {
  const tagSpan = $(document.createElement("span"));
  const removeButton = $(document.createElement("div"));
  const tagText = $(document.createElement("span"))
    .addClass("tagText")
    .text(tagString);

  tagSpan
    .addClass(
      "tagBadge tagBadgeHoverable flex-row-reverse align-center justify-flex-end",
    )
    .attr({ "data-utub-tag-id": utubTagID });

  removeButton
    .addClass("urlTagBtnDelete flex-row align-center pointerable tabbable")
    .on("click", function (e) {
      e.stopPropagation();
      deleteURLTag(utubTagID, tagSpan, urlCard);
    })
    .offAndOn("focus.removeURLTag", function () {
      $(document).on("keyup.removeURLTag", function (e) {
        if (e.which === 13) deleteURLTag(utubTagID, tagSpan, urlCard);
      });
    })
    .offAndOn("blur.removeURLTag", function () {
      $(document).off("keyup.removeURLTag");
    });

  removeButton.append(createTagDeleteIcon());

  $(tagSpan).append(removeButton).append(tagText);

  return tagSpan;
}

// Dynamically generates the delete URL-Tag icon when needed
function createTagDeleteIcon() {
  const WIDTH_HEIGHT_PX = "15px";
  const SVG_NS = "http://www.w3.org/2000/svg";
  const deleteURLTagOuterIconSvg = $(document.createElementNS(SVG_NS, "svg"));
  const deleteURLTagInnerIconPath = $(document.createElementNS(SVG_NS, "path"));
  const path =
    "M11.46.146A.5.5 0 0 0 11.107 0H4.893a.5.5 0 0 0-.353.146L.146 4.54A.5.5 0 0 0 0 4.893v6.214a.5.5 0 0 0 .146.353l4.394 4.394a.5.5 0 0 0 .353.146h6.214a.5.5 0 0 0 .353-.146l4.394-4.394a.5.5 0 0 0 .146-.353V4.893a.5.5 0 0 0-.146-.353zm-6.106 4.5L8 7.293l2.646-2.647a.5.5 0 0 1 .708.708L8.707 8l2.647 2.646a.5.5 0 0 1-.708.708L8 8.707l-2.646 2.647a.5.5 0 0 1-.708-.708L7.293 8 4.646 5.354a.5.5 0 1 1 .708-.708";

  deleteURLTagInnerIconPath.attr({
    d: path,
  });

  deleteURLTagOuterIconSvg
    .attr({
      xmlns: SVG_NS,
      width: WIDTH_HEIGHT_PX,
      height: WIDTH_HEIGHT_PX,
      fill: "currentColor",
      class: "bi bi-x-octagon-fill",
      viewBox: "0 0 16 16",
    })
    .append(deleteURLTagInnerIconPath);

  return deleteURLTagOuterIconSvg;
}
