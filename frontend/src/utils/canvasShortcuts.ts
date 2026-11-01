export function acceptsCanvasShortcut(target: EventTarget | null): boolean {
  if (!(target instanceof Element)) return true;
  return !target.closest('input, textarea, select, button, summary, a, [contenteditable]:not([contenteditable="false"]), [role="textbox"], [role="dialog"], [role="alertdialog"], [role="combobox"], [role="menu"]');
}
