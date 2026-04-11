interface JQuery {
  enableTab(): this;
  disableTab(): this;
  offAndOn(
    eventName: string,
    callback: JQuery.EventHandler<HTMLElement>,
  ): this;
  onExact(
    events: string,
    callback: JQuery.EventHandler<HTMLElement>,
    options?: { except?: string | string[] },
  ): this;
  offAndOnExact(
    eventName: string,
    callback: JQuery.EventHandler<HTMLElement>,
    options?: { except?: string | string[] },
  ): this;
  removeClassStartingWith(filter: string): this;
  showClassNormal(): this;
  showClassFlex(): this;
  hideClass(): this;
  removeHideClass(): this;
}
