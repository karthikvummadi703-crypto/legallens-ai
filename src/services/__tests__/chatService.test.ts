import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

const { authStub } = vi.hoisted(() => ({
  authStub: { currentUser: null } as {
    currentUser: { getIdToken: () => Promise<string> } | null;
  },
}));
vi.mock('../../lib/firebase', () => ({ auth: authStub }));

import { chatService } from '../chatService';

const API_BASE = 'http://localhost:8000/api';

const fetchMock = vi.fn();

function jsonResponse(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  });
}

describe('chatService (shared http client)', () => {
  beforeEach(() => {
    fetchMock.mockReset();
    authStub.currentUser = null;
    vi.stubGlobal('fetch', fetchMock);
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it('askFreeform posts to the /api/chat endpoint and maps the payload', async () => {
    fetchMock.mockResolvedValue(
      jsonResponse({
        answer: 'Here is guidance.',
        followup_questions: ['What next?'],
        conversation_id: 'conv-1',
      })
    );

    const result = await chatService.askFreeform('What is a lease?');

    expect(result.response).toBe('Here is guidance.');
    expect(result.followUps).toEqual(['What next?']);
    expect(result.conversationId).toBe('conv-1');

    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toBe(`${API_BASE}/chat`);
    expect(init.method).toBe('POST');
    expect(JSON.parse(init.body)).toEqual({ question: 'What is a lease?' });
    expect(init.headers.get('Content-Type')).toBe('application/json');
  });

  it('attaches the Firebase ID token when a user is signed in', async () => {
    authStub.currentUser = {
      getIdToken: vi.fn(async () => 'ID_TOKEN_123'),
    };
    fetchMock.mockResolvedValue(jsonResponse({ answer: 'ok' }));

    await chatService.askFreeform('hello');

    const init = fetchMock.mock.calls[0][1];
    expect(init.headers.get('Authorization')).toBe('Bearer ID_TOKEN_123');
  });

  it('sends no Authorization header when signed out', async () => {
    fetchMock.mockResolvedValue(jsonResponse({ answer: 'ok' }));
    await chatService.askFreeform('hello');
    const init = fetchMock.mock.calls[0][1];
    expect(init.headers.get('Authorization')).toBeNull();
  });

  it('maps network failures to the friendly backend-offline message', async () => {
    fetchMock.mockRejectedValue(new Error('ECONNREFUSED'));
    await expect(chatService.askFreeform('hi')).rejects.toThrow(
      'Unable to reach LegalLens backend'
    );
  });

  it('listConversations returns the conversations array (empty on non-ok)', async () => {
    fetchMock.mockResolvedValue(
      jsonResponse({ conversations: [{ conversation_id: 'c1', message_count: 2 }] })
    );
    const convs = await chatService.listConversations();
    expect(convs).toEqual([{ conversation_id: 'c1', message_count: 2 }]);
    expect(fetchMock.mock.calls[0][0]).toBe(`${API_BASE}/chat/conversations`);
  });
});