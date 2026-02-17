/**
 * jQuery plugin extensions
 * Consolidated from extensions.js and splash.js
 */

import { $ } from "./globals.js";

/**
 * Registers all custom jQuery plugins
 * Must be called once after jQuery is loaded
 */
export function registerJQueryPlugins() {
  $.fn.enableTab = function () {
    this.attr({ tabindex: 0 });
    return this;
  };

  $.fn.disableTab = function () {
    this.attr({ tabindex: -1 });
    return this;
  };

  $.fn.offAndOn = function (eventName, callback) {
    this.off(eventName).on(eventName, callback);
    return this;
  };

  $.fn.onExact = function (events, callback, options = {}) {
    return this.on(events, function (e) {
      // Check if currentTarget matches the bound element
      if (!$(e.currentTarget).is(this)) return;

      // Check for exceptions (elements to ignore)
      if (options.except) {
        const exceptions = Array.isArray(options.except)
          ? options.except
          : [options.except];
        if ($(e.target).closest(exceptions.join(",")).length) return;
      }

      // Call the actual handler
      callback.call(this, e);
    });
  };

  $.fn.offAndOnExact = function (eventName, callback, options = {}) {
    return this.off(eventName).onExact(eventName, callback, options);
  };

  $.fn.removeClassStartingWith = function (filter) {
    $(this).removeClass(function (_, className) {
      return (
        className.match(new RegExp("\\S*" + filter + "\\S*", "g")) || []
      ).join(" ");
    });
    return this;
  };

  $.fn.showClassNormal = function () {
    this.removeClass("hidden").addClass("visible");
    return this;
  };

  $.fn.showClassFlex = function () {
    this.removeClassStartingWith("hidden").addClass("visible-flex");
    return this;
  };

  $.fn.hideClass = function () {
    this.removeClassStartingWith("visible").addClass("hidden");
    return this;
  };

  $.fn.removeHideClass = function () {
    this.removeClass("hidden");
    return this;
  };
}

export function enableTabbableChildElements(parent) {
  $(parent).find(".tabbable").enableTab();
}

export function disableTabbableChildElements(parent) {
  $(parent).find(".tabbable").disableTab();
}
