import { HTMLAttributes, ReactNode, useEffect, useRef } from 'react';
import { createPortal } from 'react-dom';

interface DialogProps extends HTMLAttributes<HTMLDivElement> {
  title: string;
  onClose: () => void;
  children: ReactNode;
}

const openDialogs: HTMLDivElement[] = [];
const focusable = (root: HTMLElement) => Array.from(root.querySelectorAll<HTMLElement>(
  'button:not(:disabled), input:not(:disabled), select:not(:disabled), textarea:not(:disabled), a[href], [tabindex]:not([tabindex="-1"])',
)).filter((element) => !element.closest('[hidden], [inert]') && getComputedStyle(element).display !== 'none');

export function Dialog({ title, onClose, children, ...attributes }: DialogProps) {
  const ref = useRef<HTMLDivElement>(null);
  const close = useRef(onClose);
  close.current = onClose;
  useEffect(() => {
    const root = ref.current;
    if (!root) return;
    const previous = document.activeElement instanceof HTMLElement ? document.activeElement : null;
    openDialogs.push(root);
    const topmost = () => openDialogs[openDialogs.length - 1] === root;
    const focusFirst = () => (focusable(root)[0] || root).focus();
    focusFirst();
    const focus = (event: FocusEvent) => {
      if (topmost() && event.target instanceof Node && !root.contains(event.target)) focusFirst();
    };
    const keydown = (event: KeyboardEvent) => {
      if (!topmost()) return;
      if (event.key === 'Escape') {
        event.preventDefault();
        event.stopImmediatePropagation();
        close.current();
      } else if (event.key === 'Tab') {
        const controls = focusable(root);
        const first = controls[0] || root;
        const last = controls[controls.length - 1] || root;
        if (event.shiftKey && (document.activeElement === first || document.activeElement === root)) {
          event.preventDefault(); last.focus();
        } else if (!event.shiftKey && (document.activeElement === last || document.activeElement === root)) {
          event.preventDefault(); first.focus();
        }
      }
    };
    document.addEventListener('focusin', focus);
    document.addEventListener('keydown', keydown, true);
    return () => {
      openDialogs.splice(openDialogs.indexOf(root), 1);
      document.removeEventListener('focusin', focus);
      document.removeEventListener('keydown', keydown, true);
      if (previous?.isConnected) previous.focus();
    };
  }, []);

  const content = <div {...attributes} ref={ref} role="dialog" aria-modal="true" aria-label={title} tabIndex={-1}>{children}</div>;
  return typeof document === 'undefined' ? content : createPortal(content, document.body);
}
