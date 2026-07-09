// AI Assistant frontend (local Ollama via Flask backend)

(function () {
  const chatMessagesEl = document.getElementById('chatMessages');
  const assistantInputEl = document.getElementById('assistantInput');
  const loadingEl = document.getElementById('loading');
  const assistantErrorEl = document.getElementById('assistantError');

  // Session-level history (in-memory for the page only). Backend is the source of truth.
  const chatHistory = [];

  async function loadHistoryAndRender() {
    try {
      const res = await fetch('/api/assistant/history');
      const data = await res.json();
      if (!res.ok) return;

      chatMessagesEl.innerHTML = '';
      chatHistory.length = 0;

      (data.messages || []).forEach((m) => {
        const role = m.role;
        const content = m.content;
        chatHistory.push({ role, text: content });
        addMessage(role === 'user' ? 'user' : 'assistant', content);
      });
    } catch (e) {
      // non-fatal
    }
  }

  async function clearConversation() {
    try {
      const res = await fetch('/api/clear-chat', { method: 'POST' });
      const data = await res.json();
      if (!res.ok) {
        setError(data && data.error ? data.error : 'Unable to clear conversation');
        return;
      }

      chatMessagesEl.innerHTML = '';
      chatHistory.length = 0;
      setError(null);
    } catch (e) {
      setError(String(e && e.message ? e.message : e));
    }
  }



  function escapeHtml(str) {
    return String(str)
      .replaceAll('&', '&amp;')
      .replaceAll('<', '<')
      .replaceAll('>', '>')
      .replaceAll('"', '"')
      .replaceAll("'", '&#039;');
  }

  function addMessage(role, text) {
    const div = document.createElement('div');
    div.className = 'chat-bubble ' + (role === 'user' ? 'user' : 'ai');

    if (role === 'user') {
      div.innerHTML = `<div class="chat-meta">You</div><div class="chat-text">${escapeHtml(text)}</div>`;
    } else {
      div.innerHTML = `<div class="chat-meta">Assistant</div><div class="chat-text">${escapeHtml(text)}</div>`;
    }

    chatMessagesEl.appendChild(div);
    chatMessagesEl.scrollTop = chatMessagesEl.scrollHeight;
  }

  function setLoading(isLoading) {
    if (!loadingEl) return;
    loadingEl.style.display = isLoading ? 'flex' : 'none';
  }

  function setError(msg) {
    if (!assistantErrorEl) return;
    if (!msg) {
      assistantErrorEl.style.display = 'none';
      assistantErrorEl.textContent = '';
      return;
    }

    assistantErrorEl.style.display = 'block';
    assistantErrorEl.textContent = msg;
  }

  function getPayload(question, mode) {
    return {
      question: question,
      mode: mode || 'chat',
    };
  }

  async function callAskAi(question, mode) {
    setError(null);
    setLoading(true);

    try {
      const res = await fetch('/api/ask-ai', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(getPayload(question, mode)),
      });

      const data = await res.json();
      if (!res.ok) {
        throw new Error(data.error || 'AI request failed');
      }

      if (data.answer) {
        return data.answer;
      }

      throw new Error('AI returned empty answer');
    } finally {
      setLoading(false);
    }
  }

  window.assistantHandleEnter = function (event) {
    const key = event.key || '';
    if (key === 'Enter') {
      assistantSend();
    }
  };

  window.assistantQuickAction = async function (mode, clientId = null) {
    // For buttons: send a generic question so AI can respond naturally.
    let question = '';
    if (mode === 'insights') question = 'Generate business insights for my database.';
    else if (mode === 'daily_summary') question = "Today's Summary";
    else if (mode === 'weekly_report') question = 'Weekly Report';
    else question = 'Give me insights from my database.';

    addMessage('user', question);
    chatHistory.push({ role: 'user', text: question });

    const answer = await callAskAi(question, mode);
    addMessage('assistant', answer);
    chatHistory.push({ role: 'assistant', text: answer });
  };

  window.assistantSend = async function () {
    const question = (assistantInputEl && assistantInputEl.value ? assistantInputEl.value : '').trim();
    if (!question) return;

    if (assistantInputEl) assistantInputEl.value = '';

    addMessage('user', question);
    chatHistory.push({ role: 'user', text: question });

    try {
      const answer = await callAskAi(question, 'chat');
      addMessage('assistant', answer);
      chatHistory.push({ role: 'assistant', text: answer });
    } catch (e) {
      setError(String(e && e.message ? e.message : e));
    }
  };

  // small nicety
  if (assistantInputEl) {
    assistantInputEl.focus();
  }

  // load persisted history on page load
  loadHistoryAndRender();

  // expose clear handler in case inline UI calls it
  window.assistantClearConversation = clearConversation;


})();


