import type {
  AddMemberRequest,
  MemberModifiedResponse,
} from "../../types/member.js";

import { $, getInputValue } from "../../lib/globals.js";
import { APP_CONFIG } from "../../lib/config.js";
import { KEYS } from "../../lib/constants.js";
import { ajaxCall, is429Handled } from "../../lib/ajax.js";
import { createMemberBadge } from "./members.js";
import { setMemberDeckForUTub } from "./deck.js";
import { getState, setState } from "../../store/app-store.js";

const MEMBER_FIELD_NAMES = ["username"] as const;

type MemberFieldName = (typeof MEMBER_FIELD_NAMES)[number];

function isMemberFieldName(key: string): key is MemberFieldName {
  return (MEMBER_FIELD_NAMES as readonly string[]).includes(key);
}

export function setupShowCreateMemberFormEventListeners(utubID: number): void {
  /* Bind click functions */
  const memberBtnCreate = $("#memberBtnCreate");

  // Add member to UTub
  memberBtnCreate.offAndOn("click.createMember", function () {
    createMemberShowInput(utubID);
  });

  memberBtnCreate.offAndOn("focus", function () {
    memberBtnCreate.on(
      "keydown.createMember",
      function (event: JQuery.TriggeredEvent) {
        if (event.key === KEYS.ENTER) createMemberShowInput(utubID);
      },
    );
  });

  memberBtnCreate.offAndOn("blur", function () {
    memberBtnCreate.off(".createMember");
  });
}

function setupCreateMemberEventListeners(utubID: number): void {
  const memberSubmitBtnCreate = $("#memberSubmitBtnCreate");
  const memberCancelBtnCreate = $("#memberCancelBtnCreate");

  memberSubmitBtnCreate.offAndOnExact("click.createMemberSubmit", function () {
    createMember(utubID);
  });

  memberCancelBtnCreate.offAndOnExact("click.createMemberEscape", function () {
    createMemberHideInput();
  });

  const memberInput = $("#memberCreate");
  memberInput.on("focus.createMemberSubmitEscape", function () {
    bindCreateMemberFocusEventListeners(utubID, memberInput);
  });
  memberInput.on("blur.createMemberSubmitSubmitEscape", function () {
    unbindCreateMemberFocusEventListeners();
  });
}

function removeCreateMemberEventListeners(): void {
  $("#memberCreate").off(".createMemberSubmitEscape");
}

function bindCreateMemberFocusEventListeners(
  utubID: number,
  memberInput: JQuery,
): void {
  // Allow closing by pressing escape key
  memberInput.on(
    "keydown.createMemberSubmitEscape",
    function (event: JQuery.TriggeredEvent) {
      if ((event.originalEvent as KeyboardEvent).repeat) return;
      switch (event.key) {
        case KEYS.ENTER:
          // Handle enter key pressed
          createMember(utubID);
          break;
        case KEYS.ESCAPE:
          // Handle escape  key pressed
          createMemberHideInput();
          break;
        default:
        /* no-op */
      }
    },
  );
}

function unbindCreateMemberFocusEventListeners(): void {
  $("#memberCreate").off(".createMemberSubmitEscape");
}

// Clear member creation
function resetNewMemberForm(): void {
  $("#memberCreate").val("");
}

// Shows new Member input fields
function createMemberShowInput(utubID: number): void {
  $("#createMemberWrap").showClassFlex();
  $("#displayMemberWrap").hideClass();
  $("#memberBtnCreate").hideClass();
  setupCreateMemberEventListeners(utubID);
  $("#memberCreate").trigger("focus");
}

// Hides new Member input fields
export function createMemberHideInput(): void {
  $("#createMemberWrap").hideClass();
  $("#displayMemberWrap").showClassFlex();
  $("#memberBtnCreate").showClassNormal();
  removeCreateMemberEventListeners();
  resetCreateMemberFailErrors();
  resetNewMemberForm();
}

// This function will extract the current selection data needed for POST request (member ID)
function createMemberSetup(utubID: number): [string, AddMemberRequest] {
  const postURL = APP_CONFIG.routes.createMember(utubID);

  const username = getInputValue("#memberCreate");
  const data: AddMemberRequest = { username };

  return [postURL, data];
}

function createMember(utubID: number): void {
  // Extract data to submit in POST request
  const [postURL, data] = createMemberSetup(utubID);
  resetCreateMemberFailErrors();

  const request = ajaxCall("post", postURL, data);

  // Handle response
  request.done(function (
    response: MemberModifiedResponse,
    _textStatus: JQuery.Ajax.SuccessTextStatus,
    xhr: JQuery.jqXHR,
  ) {
    if (xhr.status === 200) {
      createMemberSuccess(response, utubID);
    }
  });

  request.fail(function (xhr: JQuery.jqXHR) {
    createMemberFail(xhr);
  });
}

// Perhaps update a scrollable/searchable list of members?
function createMemberSuccess(
  response: MemberModifiedResponse,
  utubID: number,
): void {
  resetNewMemberForm();

  setState({ members: [...getState().members, response.member] });

  // Create and append newly created Member badge - only creators can add members
  $("#listMembers").append(
    createMemberBadge(
      response.member.id,
      response.member.username,
      true,
      utubID,
    ),
  );

  createMemberHideInput();
  setMemberDeckForUTub(true);
}

function createMemberFail(xhr: JQuery.jqXHR): void {
  if (is429Handled(xhr)) return;

  if (!("responseJSON" in xhr)) {
    if (
      xhr.status === 403 &&
      xhr.getResponseHeader("Content-Type") === "text/html; charset=utf-8"
    ) {
      $("body").html(xhr.responseText);
      return;
    }
    window.location.assign(APP_CONFIG.routes.errorPage);
    return;
  }

  switch (xhr.status) {
    case 400: {
      const responseJSON = xhr.responseJSON;
      const hasErrors = !!responseJSON.errors;
      const hasMessage = !!responseJSON.message;
      if (hasErrors) {
        // Show form errors
        createMemberFailErrors(responseJSON.errors);
        break;
      } else if (hasMessage) {
        // Show message
        displayCreateMemberFailErrors(responseJSON.message);
        break;
      }
      // Intentional fall-through: an unexpected 400 body shape (neither
      // `errors` nor `message`) is treated as an unrecoverable error and
      // falls through to the default error-page redirect below.
    }
    case 403:
    case 404:
    default:
      window.location.assign(APP_CONFIG.routes.errorPage);
  }
}

function createMemberFailErrors(errors: Record<string, string[]>): void {
  for (const key in errors) {
    if (!isMemberFieldName(key)) continue;
    const errorMessage = errors[key][0];
    displayCreateMemberFailErrors(errorMessage);
    return;
  }
}

function displayCreateMemberFailErrors(errorMessage: string): void {
  $("#memberCreate-error").addClass("visible").text(errorMessage);
  $("#memberCreate").addClass("invalid-field");
}

function resetCreateMemberFailErrors(): void {
  const createMemberFields = ["member"];
  createMemberFields.forEach((fieldName) => {
    $("#" + fieldName + "Create-error").removeClass("visible");
    $("#" + fieldName + "Create").removeClass("invalid-field");
  });
}
