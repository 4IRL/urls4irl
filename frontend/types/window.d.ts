declare namespace Bootstrap {
  class Modal {
    constructor(element: Element);
    static getInstance(element: Element): Modal | null;
    static getOrCreateInstance(element: Element): Modal;
    show(): void;
    hide(): void;
    dispose(): void;
    toggle(): void;
  }
  class Tooltip {
    constructor(element: Element);
    static getInstance(element: Element): Tooltip | null;
    static getOrCreateInstance(element: Element): Tooltip;
    show(): void;
    hide(): void;
    dispose(): void;
    toggle(): void;
  }
  class Toast {
    constructor(element: Element);
    static getInstance(element: Element): Toast | null;
    static getOrCreateInstance(element: Element): Toast;
    show(): void;
    hide(): void;
    dispose(): void;
    // Note: Bootstrap 5 Toast has no toggle() method — unlike Modal, Tooltip, and Collapse.
    // The test-setup.js mock also does not implement toggle() on Toast.
  }
  class Collapse {
    constructor(element: Element, options?: { toggle?: boolean });
    static getInstance(element: Element): Collapse | null;
    static getOrCreateInstance(element: Element): Collapse;
    show(): void;
    hide(): void;
    dispose(): void;
    toggle(): void;
  }
}

declare global {
  interface Window {
    bootstrap: typeof Bootstrap;
  }
}

// Required to make this file a module — enables 'declare global { }' augmentation syntax.
export {};
