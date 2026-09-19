import { ChatMessage, SourceReference } from '../types';
import { auth } from '../lib/firebase';

const API_BASE_URL = (((import.meta as any).env?.VITE_API_BASE_URL || '') as string).replace(/\/+$/, '') + '/api';

async function getAuthHeaders(): Promise<Record<string, string>> {
  const headers: Record<string, string> = { 'Content-Type': 'application/json' };
  if (auth.currentUser) {
    try {
      const token = await auth.currentUser.getIdToken();
      headers['Authorization'] = `Bearer ${token}`;
    } catch {
      // Ignore token error in dev
    }
  }
  return headers;
}

export interface ChatResponsePayload {
  response: string;
  sources: SourceReference[];
  followUps: string[];
  conversationId?: string;
}

export interface FreeformChatPayload {
  response: string;
  sources: SourceReference[];
  followUps: string[];
  conversationId?: string;
}

function mapHistoryMessages(messages: any[]): ChatMessage[] {
  return messages.map((m: any, idx: number) => ({
    id: `msg-hist-${idx}`,
    sender: m.role === 'user' ? 'user' : 'assistant',
    text: m.content,
    timestamp: m.created_at || 'Just now',
    sources: (m.sources || []).map((s: any) => ({
      page: s.page || 1,
      section: s.section || 'General',
      quote: s.snippet || s.quote || '',
      document_id: s.document_id,
      document_name: s.document_name,
    })),
  }));
}

export const chatService = {
  async getInitialMessages(documentId: string, conversationId?: string): Promise<ChatMessage[]> {
    try {
      const headers = await getAuthHeaders();
      const url = conversationId
        ? `${API_BASE_URL}/documents/${documentId}/conversations?conversation_id=${encodeURIComponent(conversationId)}`
        : `${API_BASE_URL}/documents/${documentId}/conversations`;
      const res = await fetch(url, { headers });
      if (res.ok) {
        const data = await res.json();
        if (data.messages && Array.isArray(data.messages) && data.messages.length > 0) {
          return mapHistoryMessages(data.messages);
        }
      }
    } catch {
      // Backend not running
    }
    return [];
  },

  async getGeneralHistory(conversationId?: string): Promise<{ conversationId?: string; messages: ChatMessage[] }> {
    try {
      const headers = await getAuthHeaders();
      const url = conversationId
        ? `${API_BASE_URL}/chat/history?conversation_id=${encodeURIComponent(conversationId)}`
        : `${API_BASE_URL}/chat/history`;
      const res = await fetch(url, { headers });
      if (res.ok) {
        const data = await res.json();
        if (data.messages && Array.isArray(data.messages)) {
          return { conversationId: data.conversation_id, messages: mapHistoryMessages(data.messages) };
        }
      }
    } catch {
      // Backend not running
    }
    return { messages: [] };
  },

  async listConversations(): Promise<Array<{ conversation_id: string; document_id?: string | null; preview: string; message_count: number; referenced_document_ids?: string[] }>> {
    try {
      const headers = await getAuthHeaders();
      const res = await fetch(`${API_BASE_URL}/chat/conversations`, { headers });
      if (res.ok) {
        const data = await res.json();
        return data.conversations || [];
      }
    } catch {
      // Backend not running
    }
    return [];
  },

  async askUnified(
    question: string,
    selectedDocumentId?: string | null,
    conversationId?: string,
    chatId?: string
  ): Promise<ChatResponsePayload> {
    const headers = await getAuthHeaders();
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 60000);
    try {
      const res = await fetch(`${API_BASE_URL}/chat/query`, {
        method: 'POST',
        headers,
        signal: controller.signal,
        body: JSON.stringify({
          question,
          conversation_id: conversationId,
          selected_document_id: selectedDocumentId || null,
          chat_id: chatId || null,
        }),
      });
      clearTimeout(timeout);
      if (res.ok) {
        const data = await res.json();
        const sourcesMapped: SourceReference[] = (data.sources || []).map((s: any) => ({
          page: s.page || 1,
          section: s.section || 'General',
          quote: s.snippet || s.quote || '',
          document_id: s.document_id,
          document_name: s.document_name,
        }));
        return {
          response: data.answer,
          sources: sourcesMapped,
          followUps: data.followup_questions || [
            'What are my main obligations?',
            'When can this contract be terminated?',
            'Are there automatic renewal terms?'
          ],
          conversationId: data.conversation_id,
        };
      }
      const errBody = await res.text().catch(() => '');
      let detail = '';
      try { detail = (JSON.parse(errBody)?.detail) || errBody; } catch { detail = errBody; }
      throw new Error(detail || `Request failed (${res.status}). Please try again.`);
    } catch (e: any) {
      clearTimeout(timeout);
      if (e?.name === 'AbortError') throw new Error('Request timed out after 60s — the AI may be busy. Please retry.');
      if (e?.message) throw e;
      throw new Error('Unable to reach LegalLens backend. Please ensure the server is running and try again.');
    }
  },

  async askLegalLens(
    documentId: string, 
    userQuery: string,
    conversationId?: string
  ): Promise<ChatResponsePayload> {
    try {
      const headers = await getAuthHeaders();
      const res = await fetch(`${API_BASE_URL}/documents/${documentId}/chat`, {
        method: 'POST',
        headers,
        body: JSON.stringify({
          question: userQuery,
          conversation_id: conversationId,
        }),
      });

      if (res.ok) {
        const data = await res.json();
        const sourcesMapped: SourceReference[] = (data.sources || []).map((s: any) => ({
          page: s.page || 1,
          section: s.section || 'General',
          quote: s.snippet || '',
          document_id: s.document_id,
          document_name: s.document_name,
        }));

        return {
          response: data.answer,
          sources: sourcesMapped,
          followUps: data.followup_questions || [
            'What are my main obligations?',
            'When can this contract be terminated?',
            'Are there automatic renewal terms?'
          ],
          conversationId: data.conversation_id,
        };
      }
    } catch {
      // Backend not running
    }
    throw new Error('Unable to reach LegalLens backend. Please ensure the server is running and try again.');
  },

  async askFreeform(
    userQuery: string
  ): Promise<FreeformChatPayload> {
    try {
      const headers = await getAuthHeaders();
      const res = await fetch(`${API_BASE_URL}/chat`, {
        method: 'POST',
        headers,
        body: JSON.stringify({ question: userQuery }),
      });

      if (res.ok) {
        const data = await res.json();

        return {
          response: data.answer,
          sources: [],
          followUps: data.followup_questions || [
            'What should I check before signing a contract?',
            'What are common risky clauses?',
            'How do I negotiate better contract terms?'
          ],
          conversationId: data.conversation_id,
        };
      }
    } catch {
      // Backend not running
    }
    throw new Error('Unable to reach LegalLens backend. Please ensure the server is running and try again.');
  }
};

