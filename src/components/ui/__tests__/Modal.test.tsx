import { render, screen, fireEvent } from '@testing-library/react';
import { act } from 'react';
import { describe, expect, it, vi } from 'vitest';
import { Modal } from '../Modal';

describe('Modal accessibility', () => {
  it('links the dialog title via aria-labelledby', () => {
    render(
      <Modal isOpen onClose={vi.fn()} title="Analysis Summary">
        content
      </Modal>
    );
    const dialog = screen.getByRole('dialog', { name: 'Analysis Summary' });
    expect(dialog).toHaveAttribute('aria-modal', 'true');
    const title = screen.getByRole('heading', { name: 'Analysis Summary' });
    expect(dialog.getAttribute('aria-labelledby')).toBe(title.id);
  });

  it('moves focus into the dialog on open', () => {
    render(<Modal isOpen onClose={vi.fn()} title="Focus" />);
    const dialog = screen.getByRole('dialog');
    expect(dialog).toHaveFocus();
  });

  it('closes on Escape', () => {
    const onClose = vi.fn();
    render(
      <Modal isOpen onClose={onClose} title="Esc">
        content
      </Modal>
    );
    fireEvent.keyDown(document, { key: 'Escape' });
    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it('traps Tab focus inside the dialog', () => {
    render(
      <Modal isOpen onClose={vi.fn()} title="Trap">
        <button type="button">First</button>
        <button type="button">Second</button>
      </Modal>
    );
    const dialog = screen.getByRole('dialog');
    const focusables = Array.from(dialog.querySelectorAll<HTMLElement>('button'));
    const closeBtn = focusables[0];
    const secondBtn = focusables[focusables.length - 1];

    // Wrap backward from the first focusable (close) to the last one.
    act(() => closeBtn.focus());
    fireEvent.keyDown(document, { key: 'Tab', shiftKey: true });
    expect(secondBtn).toHaveFocus();

    // Wrap forward from the last focusable back to the first one.
    act(() => secondBtn.focus());
    fireEvent.keyDown(document, { key: 'Tab' });
    expect(closeBtn).toHaveFocus();
  });

  it('restores focus to the opener when it closes', () => {
    const onClose = vi.fn();
    const { rerender } = render(
      <>
        <button type="button">Open</button>
        <Modal isOpen={false} onClose={onClose} title="Restore" />
      </>
    );
    const opener = screen.getByRole('button', { name: 'Open' });
    act(() => opener.focus());

    rerender(
      <>
        <button type="button">Open</button>
        <Modal isOpen={true} onClose={onClose} title="Restore" />
      </>
    );
    expect(screen.getByRole('dialog')).toHaveFocus();

    rerender(
      <>
        <button type="button">Open</button>
        <Modal isOpen={false} onClose={onClose} title="Restore" />
      </>
    );
    expect(opener).toHaveFocus();
  });
});