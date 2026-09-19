import { useEffect } from 'react';

export interface ShortcutHandlers {
  onClearSelection?: () => void;
  onResetPipeline?: () => void;
  onAcceptReview?: () => void;
}

/**
 * Creative module: useKeyboardShortcuts
 * A React hook that allows advanced users to control the Agent Copilot
 * pipeline via keyboard shortcuts, dramatically improving workflow efficiency.
 */
export function useKeyboardShortcuts(handlers: ShortcutHandlers) {
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      // Ignore if typing in an input field
      if (e.target instanceof HTMLInputElement || e.target instanceof HTMLTextAreaElement) {
        return;
      }

      switch (e.key) {
        case 'c':
        case 'C':
          if (handlers.onClearSelection) handlers.onClearSelection();
          break;
        case 'r':
        case 'R':
          if (handlers.onResetPipeline) handlers.onResetPipeline();
          break;
        case 'Enter':
          if (handlers.onAcceptReview) handlers.onAcceptReview();
          break;
        default:
          break;
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [handlers]);
}
