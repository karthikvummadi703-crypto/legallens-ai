import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

const { authStub } = vi.hoisted(() => ({
  authStub: { currentUser: null } as {
    currentUser: { getIdToken: () => Promise<string> } | null;
  },
}));
vi.mock('../firebase', () => ({ auth: authStub }));

import { apiFetch } from '../http';

const API_BASE = 'http://localhost:8000/api';
const fetchMock = vi.fn();

describe('apiFetch', () => {
  beforeEach(() => {
    fetchMock.mockReset();
    authStub.currentUser = null;
    vi.stubGlobal('fetch', fetchMock);
    fetchMock.mockResolvedValue(new Response('{}', { status: 200 }));
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it('resolves the /api base URL', async () => {
    await apiFetch('/documents');
    expect(fetchMock.mock.calls[0][0]).toBe(`${API_BASE}/documents`);
  });

  it('passes query strings through', async () => {
    await apiFetch('/documents/5/conversations?conversation_id=c-1');
    expect(fetchMock.mock.calls[0][0]).toBe(`${API_BASE}/documents/5/conversations?conversation_id=c-1`);
  });

  it('attaches no Authorization header when signed out', async () => {
    await apiFetch('/documents');
    const headers = fetchMock.mock.calls[0][1].headers as Headers;
    expect(headers.get('Authorization')).toBeNull();
  });

  it('attaches Bearer token when a user (with getIdToken) is present', async () => {
    authStub.currentUser = { getIdToken: vi.fn(async () => 'TOK') };
    await apiFetch('/documents');
    const headers = fetchMock.mock.calls[0][1].headers as Headers;
    expect(headers.get('Authorization')).toBe('Bearer TOK');
  });

  it('preserves caller-provided headers', async () => {
    await apiFetch('/chat', { method: 'POST', headers: { 'Content-Type': 'application/json' } });
    const headers = fetchMock.mock.calls[0][1].headers as Headers;
    expect(headers.get('Content-Type')).toBe('application/json');
  });

  it('does not throw on non-2xx responses (callers keep res.ok handling)', async () => {
    fetchMock.mockResolvedValue(new Response('nope', { status: 500 }));
    const res = await apiFetch('/documents');
    expect(res.ok).toBe(false);
    expect(res.status).toBe(500);
  });
});