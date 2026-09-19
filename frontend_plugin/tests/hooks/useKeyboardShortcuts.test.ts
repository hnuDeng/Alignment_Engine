import { renderHook } from '@testing-library/react';
import { useKeyboardShortcuts } from '../../src/hooks/useKeyboardShortcuts';

describe('useKeyboardShortcuts', () => {
  it('calls onClearSelection when "c" is pressed', () => {
    const onClearSelection = jest.fn();
    renderHook(() => useKeyboardShortcuts({ onClearSelection }));

    window.dispatchEvent(new KeyboardEvent('keydown', { key: 'c' }));
    expect(onClearSelection).toHaveBeenCalledTimes(1);
  });

  it('calls onResetPipeline when "r" is pressed', () => {
    const onResetPipeline = jest.fn();
    renderHook(() => useKeyboardShortcuts({ onResetPipeline }));

    window.dispatchEvent(new KeyboardEvent('keydown', { key: 'r' }));
    expect(onResetPipeline).toHaveBeenCalledTimes(1);
  });

  it('calls onAcceptReview when "Enter" is pressed', () => {
    const onAcceptReview = jest.fn();
    renderHook(() => useKeyboardShortcuts({ onAcceptReview }));

    window.dispatchEvent(new KeyboardEvent('keydown', { key: 'Enter' }));
    expect(onAcceptReview).toHaveBeenCalledTimes(1);
  });

  it('ignores input events when focused on input fields', () => {
    const onClearSelection = jest.fn();
    renderHook(() => useKeyboardShortcuts({ onClearSelection }));

    const input = document.createElement('input');
    document.body.appendChild(input);
    input.focus();

    const event = new KeyboardEvent('keydown', { key: 'c' });
    Object.defineProperty(event, 'target', { value: input, enumerable: true });
    
    window.dispatchEvent(event);
    expect(onClearSelection).not.toHaveBeenCalled();

    document.body.removeChild(input);
  });
});
