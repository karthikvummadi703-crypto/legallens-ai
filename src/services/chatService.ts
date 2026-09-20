import { ChatMessage, SourceReference } from '../types';
import { apiFetch } from '../lib/http';

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

interface BackendSource {
  page?: number;
  section?: string;
  snippet?: string;
  quote?: string;
  document_id?: string;
  document_name?: string;
}

function mapSources(sources: BackendSource[] | undefined): SourceReference[] {
  return (sources || []).map((s) => ({
    page: s.page || 1,
    section: s.section || 'General',
    quote: s.snippet || s.quote || '',
    document_id: s.document_id,
    document_name: s.document_name,
  }));
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

const DEFAULT_LEGAL_FOLLOW_UPS = [
  'What are my main obligations?',
  'When can this contract be terminated?',
  'Are there automatic renewal terms?',
];

const DEFAULT_FREEFORM_FOLLOW_UPS = [
  'What should I check before signing a contract?',
  'What are common risky clauses?',
  'How do I negotiate better contract terms?',
];

const JSON_HEADERS = { 'Content-Type': 'application/json' };

export const chatService = {
  async getInitialMessages(documentId: string, conversationId?: string): Promise<ChatMessage[]> {
    try {
      const url = conversationId
        ? `/documents/${encodeURIComponent(documentId)}/conversations?conversation_id=${encodeURIComponent(conversationId)}`
        : `/documents/${encodeURIComponent(documentId)}/conversations`;
      const res = await apiFetch(url);
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
      const url = conversationId
        ? `/chat/history?conversation_id=${encodeURIComponent(conversationId)}`
        : '/chat/history';
      const res = await apiFetch(url);
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
      const res = await apiFetch('/chat/conversations');
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
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 60000);
    try {
      const res = await apiFetch('/chat/query', {
        method: 'POST',
        headers: JSON_HEADERS,
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
        return {
          response: data.answer,
          sources: mapSources(data.sources),
          followUps: data.followup_questions || DEFAULT_LEGAL_FOLLOW_UPS,
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
      const res = await apiFetch(`/documents/${encodeURIComponent(documentId)}/chat`, {
        method: 'POST',
        headers: JSON_HEADERS,
        body: JSON.stringify({
          question: userQuery,
          conversation_id: conversationId,
        }),
      });

      if (res.ok) {
        const data = await res.json();
        return {
          response: data.answer,
          sources: mapSources(data.sources),
          followUps: data.followup_questions || DEFAULT_LEGAL_FOLLOW_UPS,
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
      const res = await apiFetch('/chat', {
        method: 'POST',
        headers: JSON_HEADERS,
        body: JSON.stringify({ question: userQuery }),
      });

      if (res.ok) {
        const data = await res.json();
        return {
          response: data.answer,
          sources: [],
          followUps: data.followup_questions || DEFAULT_FREEFORM_FOLLOW_UPS,
          conversationId: data.conversation_id,
        };
      }
    } catch {
      // Backend not running
    }
    throw new Error('Unable to reach LegalLens backend. Please ensure the server is running and try again.');
  }
};