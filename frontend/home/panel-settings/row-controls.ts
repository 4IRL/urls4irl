// DOM builders shared by the settings sections' rows (label block and switch).

export function buildRowLabel({
  titleId,
  title,
  descId,
  desc,
}: {
  titleId: string;
  title: string;
  descId: string;
  desc?: string;
}): HTMLElement {
  const label = document.createElement("div");
  label.className = "panelSettingsRowLabel";
  const titleElement = document.createElement("div");
  titleElement.className = "panelSettingsRowName";
  titleElement.id = titleId;
  titleElement.textContent = title;
  label.append(titleElement);
  if (desc !== undefined) {
    const descElement = document.createElement("div");
    descElement.className = "panelSettingsRowDesc";
    descElement.id = descId;
    descElement.textContent = desc;
    label.append(descElement);
  }
  return label;
}

export function buildSwitchButton({
  id,
  labelledBy,
}: {
  id: string;
  labelledBy: string;
}): HTMLButtonElement {
  const switchButton = document.createElement("button");
  switchButton.type = "button";
  switchButton.id = id;
  switchButton.className = "urlsSettingsSwitch";
  switchButton.setAttribute("role", "switch");
  switchButton.setAttribute("aria-labelledby", labelledBy);
  const track = document.createElement("span");
  track.className = "urlsSettingsSwitchTrack";
  const thumb = document.createElement("span");
  thumb.className = "urlsSettingsSwitchThumb";
  track.append(thumb);
  switchButton.append(track);
  return switchButton;
}
