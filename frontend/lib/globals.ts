/**
 * Global library re-exports
 * Makes jQuery and Bootstrap available to ES6 modules
 */

export const $: JQueryStatic = window.jQuery;
export const jQuery: JQueryStatic = window.jQuery;
export const bootstrap: typeof Bootstrap = window.bootstrap;
