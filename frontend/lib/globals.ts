/**
 * Global library re-exports
 * Makes jQuery and Bootstrap available to ES6 modules
 */

export const $: JQueryStatic = window.jQuery;
export const jQuery: JQueryStatic = window.jQuery;
export const bootstrap: typeof window.bootstrap = window.bootstrap;

export function getInputValue(input: string | JQuery): string {
  const element = typeof input === "string" ? $(input) : input;
  return (element.val() as string) ?? "";
}
