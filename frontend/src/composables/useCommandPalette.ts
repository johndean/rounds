/**
 * Global toggle for the command palette. Synthesizes a ⌘K keyboard event
 * so we don't have to thread refs through every consumer.
 */
export const commandPalette = {
  open(): void {
    if (typeof window === 'undefined') return;
    // The palette component listens for Cmd/Ctrl+K — fire the event ourselves
    const ev = new KeyboardEvent('keydown', { key: 'k', metaKey: true, bubbles: true });
    window.dispatchEvent(ev);
  },
};

export function useCommandPalette() {
  return commandPalette;
}
