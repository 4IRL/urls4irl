interface JQuery<TElement = HTMLElement> {
  enableTab(): this;
  disableTab(): this;
  offAndOn(
    eventName: string,
    callback: JQuery.EventHandler<TElement>,
  ): this;
  onExact(
    events: string,
    callback: JQuery.EventHandler<TElement>,
    options?: { except?: string | string[] },
  ): this;
  offAndOnExact(
    eventName: string,
    callback: JQuery.EventHandler<TElement>,
    options?: { except?: string | string[] },
  ): this;
  removeClassStartingWith(filter: string): this;
  showClassNormal(): this;
  showClassFlex(): this;
  hideClass(): this;
  removeHideClass(): this;
}
