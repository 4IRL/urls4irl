import { $ } from "../../../lib/globals.js";
import { APP_CONFIG } from "../../../lib/config.js";
import { KEYS } from "../../../lib/constants.js";
import { emit } from "../../../lib/metrics-client.js";
import { UI_EVENTS } from "../../../types/metrics-events.js";
import {
  URL_PARAMS_TRIMMED_ACTION,
  URL_PARAMS_TRIMMED_FORM,
} from "../../../types/metrics-dim-values.js";
import {
  buildTrimmedUrl,
  isAutoStrippedParam,
  parseQuerySegments,
  previewStoredUrl,
  type ParsedQuery,
  type QueryParamSegment,
} from "../query-params.js";

/**
 * The two flows the trim block serves. `CREATE` is the single Add-URL form
 * instance; `URL` is one instance per URL card (edit-URL-string flow).
 */
export const TrimMode = Object.freeze({
  CREATE: "create",
  URL: "url",
} as const);
export type TrimMode = (typeof TrimMode)[keyof typeof TrimMode];

// `wrap.data(KEY)` keys, `<widgetCamelCase><Verb><Noun>`, unique per widget.
export const TRIM_GET_KEY = "urlParamTrimGetTrimmed";
export const TRIM_RESET_KEY = "urlParamTrimReset";
export const TRIM_SYNC_KEY = "urlParamTrimSync";
export const TRIM_SUBMISSION_KEY = "urlParamTrimSubmission";
export const TRIM_FLUSH_KEY = "urlParamTrimFlush";

/** What Steps 5-7 capture at submit time for the outcome banner and Undo. */
export interface TrimSubmission {
  originalUrlString: string;
  droppedSegments: string[];
  droppedCount: number;
}

const REPARSE_DEBOUNCE_MS = 200;
const BODY_ID_PREFIX = "urlParamTrimBody";
const CARET_PATH =
  "M7.247 11.14 2.451 5.658C1.885 5.013 2.345 4 3.204 4h9.592a1 1 0 0 1 .753 1.659l-4.796 5.48a1 1 0 0 1-1.506 0z";
const SVG_NS = "http://www.w3.org/2000/svg";
const GLYPH_KEPT = "✓";
const GLYPH_DROPPED = "✕";
const GLYPH_WARNING = "⚠";

let trimIdCounter = 0;

interface TrimRefs {
  parsed: ParsedQuery | null;
  dropped: Set<number>;
  original: string;
  debounceTimer: ReturnType<typeof setTimeout> | null;
  pendingRawValue: string;
}

/** Fills `{key}` placeholders; a function replacer keeps `$&`-style text in values literal. */
export function fillTemplate({
  template,
  values,
}: {
  template: string;
  values: Record<string, string>;
}): string {
  // Single pass: substituted values (user URL text) are never re-scanned.
  return template.replace(
    /\{(\w+)\}/g,
    (placeholder, key: string) => values[key] ?? placeholder,
  );
}

function createCaret(): JQuery<HTMLElement> {
  const svg = document.createElementNS(SVG_NS, "svg");
  svg.setAttribute("width", "16");
  svg.setAttribute("height", "16");
  svg.setAttribute("fill", "currentColor");
  svg.setAttribute("viewBox", "0 0 16 16");
  svg.setAttribute("aria-hidden", "true");
  svg.setAttribute("class", "bi bi-caret-down-fill title-caret closed");
  const path = document.createElementNS(SVG_NS, "path");
  path.setAttribute("d", CARET_PATH);
  svg.appendChild(path);
  return $(svg as unknown as HTMLElement);
}

/**
 * Force-expands a trim block from outside (e.g. a trim-caused 409): the same
 * three-part move as the header toggle, applied directly via the DOM.
 */
export function expandParamTrimBlock({ trimWrap }: { trimWrap: JQuery }): void {
  trimWrap.removeClass("collapsed");
  trimWrap.find(".title-caret").removeClass("closed");
  trimWrap.find(".urlParamTrimHeader").attr("aria-expanded", "true");
}

function actionableSegments(parsed: ParsedQuery): QueryParamSegment[] {
  return parsed.segments.filter((segment) => !segment.isAutoStripped);
}

/**
 * Builds the collapsible "Query parameters" trim control, returned hidden and
 * collapsed. Mirrors `createTagComboboxBlock`: state lives in a closure and the
 * imperative callbacks are published on `wrap.data()` under the exported keys.
 */
export function createParamTrimBlock({
  mode,
  urlCard,
  onDroppedChange,
}: {
  mode: TrimMode;
  urlCard: JQuery | null;
  onDroppedChange?: () => void;
}): JQuery {
  const refs: TrimRefs = {
    parsed: null,
    dropped: new Set<number>(),
    original: "",
    debounceTimer: null,
    pendingRawValue: "",
  };

  const urlCardId = urlCard?.attr("utuburlid");
  const bodyId =
    mode === TrimMode.URL
      ? `${BODY_ID_PREFIX}-${urlCardId ?? `n${++trimIdCounter}`}`
      : BODY_ID_PREFIX;

  const wrap = $(document.createElement("div")).addClass(
    "urlParamTrimWrap flex-column hidden collapsed",
  );

  const caret = createCaret();
  const title = $(document.createElement("span")).addClass("urlParamTrimTitle");
  const droppedCount = $(document.createElement("span")).addClass(
    "urlParamTrimDroppedCount hidden",
  );
  const header = $(document.createElement("button"))
    .addClass(
      "urlParamTrimHeader flex-row flex-center gap-2p clickable tabbable",
    )
    .attr({
      type: "button",
      "aria-expanded": "false",
      "aria-controls": bodyId,
    })
    .append(caret)
    .append(title)
    .append(droppedCount);

  const warningIcon = $(document.createElement("i"))
    .addClass("warnIcon")
    .attr("aria-hidden", "true")
    .text(GLYPH_WARNING);
  const warningText = $(document.createElement("span"));
  const message = $(document.createElement("div"))
    .addClass("urlParamTrimMsg warn")
    .append(warningIcon)
    .append(warningText);

  const chips = $(document.createElement("div"))
    .addClass("urlParamTrimChips")
    .attr({
      role: "group",
      "aria-label": APP_CONFIG.strings.URL_TRIM_GROUP_ARIA,
    });

  const dropAllBtn = $(document.createElement("button"))
    .addClass("urlParamTrimBtn tabbable danger")
    .attr("type", "button")
    .text(APP_CONFIG.strings.URL_TRIM_DROP_ALL);
  const keepAllBtn = $(document.createElement("button"))
    .addClass("urlParamTrimBtn tabbable")
    .attr("type", "button")
    .text(APP_CONFIG.strings.URL_TRIM_KEEP_ALL);
  const keptCount = $(document.createElement("span")).addClass(
    "urlParamTrimCount",
  );
  const actions = $(document.createElement("div"))
    .addClass("urlParamTrimActions")
    .append(dropAllBtn)
    .append(keepAllBtn)
    .append(keptCount);

  const previewLabel = $(document.createElement("span"))
    .addClass("urlParamTrimPreviewLabel")
    .text(APP_CONFIG.strings.URL_TRIM_PREVIEW_LABEL);
  const previewValue = $(document.createElement("code")).addClass(
    "urlParamTrimPreviewValue",
  );
  const preview = $(document.createElement("div"))
    .addClass("urlParamTrimPreview")
    .append(previewLabel)
    .append(previewValue);

  const body = $(document.createElement("div"))
    .addClass("urlParamTrimBody")
    .attr("id", bodyId)
    .append(message)
    .append(chips)
    .append(actions)
    .append(preview);

  // A sibling of the body, never inside it: the collapse uses
  // `visibility: hidden`, which would mute a live region.
  const announcer = $(document.createElement("div"))
    .addClass("visually-hidden urlParamTrimAnnouncer")
    .attr({ "aria-live": "polite", "aria-atomic": "true" });

  wrap.append(header).append(body).append(announcer);

  function announce(text: string): void {
    announcer.text(text);
  }

  const metricsForm =
    mode === TrimMode.URL
      ? URL_PARAMS_TRIMMED_FORM.URL_STRING_EDIT
      : URL_PARAMS_TRIMMED_FORM.URL_CREATE;

  function emitTrimAction({
    action,
  }: {
    action: (typeof URL_PARAMS_TRIMMED_ACTION)[keyof typeof URL_PARAMS_TRIMMED_ACTION];
  }): void {
    emit({
      event: UI_EVENTS.UI_URL_PARAMS_TRIMMED,
      form: metricsForm,
      action,
    });
  }

  function keptTotals(): { kept: number; total: number } {
    const total = refs.parsed ? actionableSegments(refs.parsed).length : 0;
    return { kept: total - refs.dropped.size, total };
  }

  function toggleSegment(segment: QueryParamSegment): void {
    const wasDropped = refs.dropped.has(segment.index);
    if (wasDropped) {
      refs.dropped.delete(segment.index);
    } else {
      refs.dropped.add(segment.index);
    }
    renderTrimBlock();
    emitTrimAction({ action: URL_PARAMS_TRIMMED_ACTION.TOGGLE });
    const { kept, total } = keptTotals();
    announce(
      fillTemplate({
        template: APP_CONFIG.strings.URL_TRIM_ANNOUNCE,
        values: {
          verb: wasDropped
            ? APP_CONFIG.strings.URL_TRIM_VERB_KEPT
            : APP_CONFIG.strings.URL_TRIM_VERB_DROPPED,
          param: segment.raw,
          kept: String(kept),
          total: String(total),
        },
      }),
    );
    onDroppedChange?.();
  }

  function createChip(segment: QueryParamSegment): JQuery {
    const text = $(document.createElement("span"))
      .addClass("urlParamTrimChipText")
      .text(segment.raw);

    if (segment.isAutoStripped) {
      const autoTag = $(document.createElement("span"))
        .addClass("urlParamTrimAutoTag")
        .text(APP_CONFIG.strings.URL_TRIM_AUTO_TAG);
      return $(document.createElement("span"))
        .addClass("urlParamTrimChip")
        .attr({
          "data-auto": "true",
          role: "img",
          "aria-label": fillTemplate({
            template: APP_CONFIG.strings.URL_TRIM_CHIP_AUTO_ARIA,
            values: { param: segment.raw },
          }),
        })
        .append(text)
        .append(autoTag);
    }

    const isDropped = refs.dropped.has(segment.index);
    const glyph = $(document.createElement("span"))
      .addClass("urlParamTrimChipGlyph")
      .attr("aria-hidden", "true")
      .text(isDropped ? GLYPH_DROPPED : GLYPH_KEPT);
    const chip = $(document.createElement("button"))
      .addClass("urlParamTrimChip tabbable")
      .attr({
        type: "button",
        "data-index": String(segment.index),
        "aria-pressed": String(!isDropped),
        "aria-label": fillTemplate({
          template: isDropped
            ? APP_CONFIG.strings.URL_TRIM_CHIP_DROP_ARIA
            : APP_CONFIG.strings.URL_TRIM_CHIP_KEEP_ARIA,
          values: { param: segment.raw },
        }),
      })
      .append(glyph)
      .append(text);

    chip.on("click.urlParamTrim", (event: JQuery.TriggeredEvent) => {
      event.stopPropagation();
      toggleSegment(segment);
    });
    // Space/Enter are handled on the chip itself and never reach the form
    // (Escape stays unbound so it still cancels). Arrow keys stay unbound too:
    // the document-level keyup card navigator would move the selected card.
    chip.on("keydown.urlParamTrim", (event: JQuery.TriggeredEvent) => {
      if (event.key === KEYS.ENTER || event.key === KEYS.SPACE) {
        event.preventDefault();
        event.stopPropagation();
        // A held key must not rapid-fire toggles.
        if ((event.originalEvent as KeyboardEvent | undefined)?.repeat) return;
        toggleSegment(segment);
      }
    });
    chip.on("keyup.urlParamTrim", (event: JQuery.TriggeredEvent) => {
      // Firefox synthesizes a click for Space on keyup; swallow it.
      if (event.key === KEYS.SPACE) {
        event.preventDefault();
        event.stopPropagation();
      }
    });
    return chip;
  }

  /** Pure re-render from `refs`; never parses and never touches collapse state. */
  function renderTrimBlock(): void {
    const parsed = refs.parsed;
    wrap.toggleClass(
      "hidden",
      !parsed || !parsed.hadQuery || parsed.segments.length === 0,
    );
    if (!parsed) {
      chips.empty();
      droppedCount.addClass("hidden").text("");
      previewValue.text("");
      return;
    }

    const actionable = actionableSegments(parsed);
    const total = actionable.length;
    const dropped = refs.dropped.size;

    title.text(
      total === 1
        ? APP_CONFIG.strings.URL_TRIM_PARAMS_LABEL_ONE
        : fillTemplate({
            template: APP_CONFIG.strings.URL_TRIM_PARAMS_LABEL,
            values: { n: String(total) },
          }),
    );
    droppedCount.toggleClass("hidden", dropped === 0).text(
      dropped === 0
        ? ""
        : fillTemplate({
            template: APP_CONFIG.strings.URL_TRIM_HEADER_DROPPED,
            values: { n: String(dropped) },
          }),
    );
    warningText.text(
      total === 1
        ? APP_CONFIG.strings.URL_TRIM_WARNING_ONE
        : APP_CONFIG.strings.URL_TRIM_WARNING,
    );

    // Rebuilding the chips destroys the focused one; restore focus by index.
    const focusedIndex = chips
      .find(".urlParamTrimChip:focus")
      .attr("data-index");
    chips.empty();
    parsed.segments.forEach((segment) => chips.append(createChip(segment)));
    if (focusedIndex !== undefined) {
      chips
        .find(`.urlParamTrimChip[data-index="${focusedIndex}"]`)
        .trigger("focus");
    }

    const showBulk = total > 1;
    dropAllBtn.toggleClass("hidden", !showBulk);
    keepAllBtn.toggleClass("hidden", !showBulk);
    keptCount.text(
      fillTemplate({
        template: APP_CONFIG.strings.URL_TRIM_KEPT_COUNT,
        values: { kept: String(total - dropped), total: String(total) },
      }),
    );
    previewValue.text(
      previewStoredUrl({
        original: refs.original,
        parsed,
        droppedIndexes: refs.dropped,
      }),
    );
  }

  /** The actual re-parse; the only place `refs.dropped` is cleared. */
  function applyTrimSync(rawValue: string): void {
    // An unchanged value must keep the user's drop choices: the submit-time
    // flush re-syncs with the current input and would otherwise wipe them.
    if (refs.parsed !== null && refs.original === rawValue) return;
    const parsed = parseQuerySegments(rawValue);
    const hadDropped = refs.dropped.size > 0;
    if (parsed === null) {
      // `original` MUST be the raw text (never ""): TRIM_GET_KEY has to return
      // exactly what should be submitted in every reachable state (DD-23).
      refs.parsed = null;
      refs.dropped.clear();
      refs.original = rawValue;
      renderTrimBlock();
      if (hadDropped) {
        announce(APP_CONFIG.strings.URL_TRIM_DROPS_RESET);
        onDroppedChange?.();
      }
      return;
    }

    parsed.segments.forEach((segment) => {
      segment.isAutoStripped = isAutoStrippedParam({
        name: segment.name,
        scheme: parsed.scheme,
      });
    });
    refs.parsed = parsed;
    refs.original = rawValue;
    refs.dropped.clear();
    renderTrimBlock();
    if (hadDropped) {
      announce(APP_CONFIG.strings.URL_TRIM_DROPS_RESET);
      onDroppedChange?.();
    }
  }

  function cancelPendingReparse(): void {
    if (refs.debounceTimer) clearTimeout(refs.debounceTimer);
    refs.debounceTimer = null;
  }

  function setAllDropped({ shouldDrop }: { shouldDrop: boolean }): void {
    if (!refs.parsed) return;
    const droppedBefore = refs.dropped.size;
    refs.dropped.clear();
    if (shouldDrop) {
      actionableSegments(refs.parsed).forEach((segment) =>
        refs.dropped.add(segment.index),
      );
    }
    renderTrimBlock();
    // Only a bulk action that changed something counts as a use of the control.
    if (refs.dropped.size !== droppedBefore) {
      emitTrimAction({
        action: shouldDrop
          ? URL_PARAMS_TRIMMED_ACTION.DROP_ALL
          : URL_PARAMS_TRIMMED_ACTION.KEEP_ALL,
      });
    }
    const { kept, total } = keptTotals();
    announce(
      fillTemplate({
        template: APP_CONFIG.strings.URL_TRIM_BULK_ANNOUNCE,
        values: { kept: String(kept), total: String(total) },
      }),
    );
    onDroppedChange?.();
  }

  dropAllBtn.on("click.urlParamTrim", (event: JQuery.TriggeredEvent) => {
    event.stopPropagation();
    setAllDropped({ shouldDrop: true });
  });
  keepAllBtn.on("click.urlParamTrim", (event: JQuery.TriggeredEvent) => {
    event.stopPropagation();
    setAllDropped({ shouldDrop: false });
  });

  // The three-part collapse move (wrap `collapsed`, caret `closed`,
  // `aria-expanded`) must never drift apart.
  function setCollapsed({ isCollapsed }: { isCollapsed: boolean }): void {
    wrap.toggleClass("collapsed", isCollapsed);
    caret.toggleClass("closed", isCollapsed);
    header.attr("aria-expanded", String(!isCollapsed));
  }

  header.on("click.urlParamTrim", (event: JQuery.TriggeredEvent) => {
    event.stopPropagation();
    setCollapsed({ isCollapsed: !wrap.hasClass("collapsed") });
  });

  wrap.data(TRIM_GET_KEY, (): string =>
    refs.parsed
      ? buildTrimmedUrl({
          original: refs.original,
          parsed: refs.parsed,
          droppedIndexes: refs.dropped,
        })
      : refs.original,
  );

  wrap.data(TRIM_SUBMISSION_KEY, (): TrimSubmission => {
    const segments = refs.parsed?.segments ?? [];
    return {
      originalUrlString: refs.original,
      droppedSegments: [...refs.dropped]
        .sort((first, second) => first - second)
        .map((droppedIndex) => segments[droppedIndex].raw),
      droppedCount: refs.dropped.size,
    };
  });

  wrap.data(TRIM_SYNC_KEY, (rawValue: string): void => {
    refs.pendingRawValue = rawValue;
    cancelPendingReparse();
    refs.debounceTimer = setTimeout(() => {
      refs.debounceTimer = null;
      applyTrimSync(refs.pendingRawValue);
    }, REPARSE_DEBOUNCE_MS);
  });

  wrap.data(TRIM_FLUSH_KEY, (rawValue: string): void => {
    cancelPendingReparse();
    applyTrimSync(rawValue);
  });

  // Teardown-only exception to "collapse state belongs to the header": a reset
  // re-collapses all three parts so a reused block starts collapsed again.
  wrap.data(TRIM_RESET_KEY, (): void => {
    cancelPendingReparse();
    refs.dropped.clear();
    refs.parsed = null;
    refs.original = "";
    announcer.text("");
    setCollapsed({ isCollapsed: true });
    renderTrimBlock();
  });

  renderTrimBlock();

  return wrap;
}
