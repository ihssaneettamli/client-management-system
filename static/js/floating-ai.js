(function () {
  function $(id) {
    return document.getElementById(id);
  }

  const OVERLAY_ID = 'floatingAiOverlay';
  const MESSAGES_ID = 'floatingAiMessages';
  const INPUT_ID = 'floatingAiInput';
  const SEND_BTN_SELECTOR = '[data-floating-ai-send]';
  const CLEAR_BTN_SELECTOR = '[data-floating-ai-clear]';

  const EMPTY_HINT_ID = 'floatingAiMessagesEmptyHint';

  function escapeHtml(str) {
    return String(str)
      .replaceAll('&', '&amp;')
      .replaceAll('<', '<')
      .replaceAll('>', '>')
      .replaceAll('"', '"')
      .replaceAll("'", '&#039;');
  }

  function addMessageBubble({ role, content }) {
    const container = $(MESSAGES_ID);
    if (!container) return;

    const isUser = role === 'user';
    const div = document.createElement('div');
    div.className = 'floating-ai-msg ' + (isUser ? 'floating-ai-msg--user' : 'floating-ai-msg--ai');

    const meta = isUser ? 'You' : 'Assistant';
    div.innerHTML = `
      <div class="floating-ai-msg__meta">${escapeHtml(meta)}</div>
      <div class="floating-ai-msg__text">${escapeHtml(content || '')}</div>
    `;

    container.appendChild(div);
    // keep newest at bottom
    container.scrollTop = container.scrollHeight;
  }

  function renderMessages(messages) {
    const container = $(MESSAGES_ID);
    if (!container) return;

    container.innerHTML = '';

    (messages || []).forEach((m) => {
      addMessageBubble({ role: m.role, content: m.content });
    });
  }

  function getInputValue() {
    const overlay = $(OVERLAY_ID);
    if (!overlay) return '';
    const input = overlay.querySelector('#' + INPUT_ID);
    return input && input.value ? input.value.trim() : '';
  }

  function clearInput() {
    const overlay = $(OVERLAY_ID);
    if (!overlay) return;
    const input = overlay.querySelector('#' + INPUT_ID);
    if (input) input.value = '';
  }

  function setSendDisabled(disabled) {
    const overlay = $(OVERLAY_ID);
    if (!overlay) return;
    const sendBtn = overlay.querySelector(SEND_BTN_SELECTOR);
    if (!sendBtn) return;
    sendBtn.disabled = !!disabled;
    sendBtn.style.opacity = disabled ? '0.7' : '1';
    sendBtn.style.cursor = disabled ? 'not-allowed' : 'pointer';
  }

  async function loadHistory() {
    const overlay = $(OVERLAY_ID);
    if (!overlay) return;

    try {
      const res = await fetch('/api/assistant/history');
      if (!res.ok) return;
      const data = await res.json();
      renderMessages(data.messages || []);
    } catch (e) {
      // non-fatal
    }
  }

  async function openPopup() {
    const overlay = $(OVERLAY_ID);
    if (!overlay) return;
    overlay.classList.add('is-open');

    // Load previous conversation when popup opens
    await loadHistory();

    // Focus input without scrolling
    const input = overlay.querySelector('#' + INPUT_ID);
    if (input) {
      input.focus();
    }
  }

  async function askAi(question) {
    const res = await fetch('/api/ask-ai', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ question: question, mode: 'chat' }),
    });

    const data = await res.json().catch(() => ({}));
    if (!res.ok) {
      throw new Error(data && data.error ? data.error : 'AI request failed');
    }
    if (!data || !data.answer) {
      throw new Error('AI returned empty answer');
    }
    return data.answer;
  }

  async function sendMessage() {
    const overlay = $(OVERLAY_ID);
    if (!overlay) return;

    const question = getInputValue();
    if (!question) return;

    clearInput();

    // Append user message immediately
    addMessageBubble({ role: 'user', content: question });

    // Loading indicator (temporary assistant bubble)
    const loadingBubble = { role: 'assistant', content: 'Thinking...' };
    addMessageBubble(loadingBubble);

    setSendDisabled(true);
    try {
      const answer = await askAi(question);

      // Replace last loading bubble with actual assistant response
      const container = $(MESSAGES_ID);
      if (container) {
        const bubbles = container.querySelectorAll('.floating-ai-msg');
        // last bubble is the loading assistant bubble
        if (bubbles && bubbles.length > 0) {
          const last = bubbles[bubbles.length - 1];
          const textEl = last.querySelector('.floating-ai-msg__text');
          if (textEl) textEl.textContent = answer;
        } else {
          addMessageBubble({ role: 'assistant', content: answer });
        }
      } else {
        addMessageBubble({ role: 'assistant', content: answer });
      }
    } catch (e) {
      const errMsg = String(e && e.message ? e.message : e);
      const container = $(MESSAGES_ID);
      if (container) {
        const bubbles = container.querySelectorAll('.floating-ai-msg');
        if (bubbles && bubbles.length > 0) {
          const last = bubbles[bubbles.length - 1];
          const textEl = last.querySelector('.floating-ai-msg__text');
          if (textEl) textEl.textContent = 'Error: ' + errMsg;
        }
      }
    } finally {
      setSendDisabled(false);

      // Ensure scroll to newest
      const container = $(MESSAGES_ID);
      if (container) container.scrollTop = container.scrollHeight;
    }
  }

  async function clearConversation() {
    const overlay = $(OVERLAY_ID);
    if (!overlay) return;

    const ok = window.confirm('Clear chat history? This cannot be undone.');
    if (!ok) return;

    // Clear UI immediately, then call backend to delete persisted history.
    const container = $(MESSAGES_ID);
    if (container) container.innerHTML = '';

    setSendDisabled(true);
    try {
      const res = await fetch('/api/assistant/clear', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({}),
      });

      if (!res.ok) {
        // Re-load to avoid UI/back-end mismatch.
        await loadHistory();
        return;
      }

      // Keep popup open; do not reload page.
      const hint = $(EMPTY_HINT_ID);
      if (hint) {
        hint.textContent = '';
        hint.style.display = 'none';
      }
    } catch (e) {
      await loadHistory();
    } finally {
      setSendDisabled(false);
    }
  }



  function closePopup() {
    const overlay = $(OVERLAY_ID);
    if (!overlay) return;
    overlay.classList.remove('is-open');
  }

  document.addEventListener('DOMContentLoaded', function () {
    const fabBtn = document.querySelector('.floating-ai-btn');
    const overlay = $(OVERLAY_ID);
    if (!fabBtn || !overlay) return;

    // Click FAB -> open
    fabBtn.addEventListener('click', function () {
      openPopup();
    });

    // Close button
    const closeBtn = overlay.querySelector('[data-floating-ai-close]');
    if (closeBtn) {
      closeBtn.addEventListener('click', function () {
        closePopup();
      });
    }

    // Clicking outside the popup hides it
    overlay.addEventListener('click', function (e) {
      if (e.target === overlay) {
        closePopup();
      }
    });

    // Prevent form reloads (if any)
    const footerForm = overlay.querySelector('form');
    if (footerForm) {
      footerForm.addEventListener('submit', function (e) {
        e.preventDefault();
      });
    }

    // Send button -> call backend /api/ask-ai
    const sendBtn = overlay.querySelector(SEND_BTN_SELECTOR);
    if (sendBtn) {
      sendBtn.addEventListener('click', function () {
        sendMessage();
      });
    }

    // Clear button -> call backend /api/assistant/clear
    const clearBtn = overlay.querySelector(CLEAR_BTN_SELECTOR);
    if (clearBtn) {
      clearBtn.addEventListener('click', function () {
        clearConversation();
      });
    }

    // Enter to send, Shift+Enter = new line (uses textarea-like behavior)
    const inputEl = overlay.querySelector('#' + INPUT_ID);
    if (inputEl) {
      inputEl.addEventListener('keydown', function (e) {
        if (e.key === 'Enter') {
          if (e.shiftKey) {
            // Allow newline if input supports it
            return;
          }
          e.preventDefault();
          sendMessage();
        }
      });
    }

    // Open full assistant by navigating to /assistant.
    // Persistent history is loaded by `assistant.js` from the same backend source.
    const fullLink = overlay.querySelector('[data-floating-ai-full-assistant]');
    if (fullLink) {
      // no preventDefault() -> allow normal navigation
    }
  });
})();



