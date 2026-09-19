import { LegalDocument } from '../types';
import { auth } from '../lib/firebase';

const API_BASE_URL = (((import.meta as any).env?.VITE_API_BASE_URL || '') as string).replace(/\/+$/, '') + '/api';

async function getAuthHeaders(): Promise<Record<string, string>> {
  const headers: Record<string, string> = {};
  if (auth.currentUser) {
    try {
      const token = await auth.currentUser.getIdToken();
      if (token) headers['Authorization'] = `Bearer ${token}`;
    } catch {
      // Ignore token fetch errors in offline dev
    }
  }
  return headers;
}

export const documentService = {
  async getDocuments(): Promise<LegalDocument[]> {
    try {
      const headers = await getAuthHeaders();
      const res = await fetch(`${API_BASE_URL}/documents`, { headers });
      if (res.ok) {
        const data = await res.json();
        if (Array.isArray(data) && data.length > 0) {
          return data.map((item: any) => ({
            id: item.id,
            name: item.name,
            type: item.type as 'PDF' | 'DOCX' | 'TXT',
            uploadDate: item.uploadDate,
            size: item.size,
            analysisStatus: item.analysisStatus,
            indexingStatus: item.indexingStatus || 'indexed',
            attentionScore: item.attentionScore,
            pageCount: item.pageCount,
            category: item.category,
            summary: item.summary,
            content: '',
            clausesCount: item.clausesCount || 0,
            risksCount: item.risksCount || 0,
            obligationsCount: item.obligationsCount || 0,
          }));
        }
      }
    } catch {
      // Backend not running
    }
    return [];
  },

  async getDocumentById(id: string): Promise<LegalDocument | undefined> {
    try {
      const headers = await getAuthHeaders();
      const res = await fetch(`${API_BASE_URL}/documents/${id}`, { headers });
      if (res.ok) {
        const data = await res.json();
        const meta = data.metadata || data;
        const extracted = data.extracted;
        return {
          id: meta.id,
          name: meta.name,
          type: meta.type as 'PDF' | 'DOCX' | 'TXT',
          uploadDate: meta.uploadDate,
          size: meta.size,
          analysisStatus: meta.analysisStatus,
          attentionScore: meta.attentionScore,
          pageCount: meta.pageCount,
          category: meta.category,
          summary: meta.summary,
          content: extracted?.full_text || '',
          pages: extracted?.pages || [],
          clausesCount: meta.clausesCount || 0,
          risksCount: meta.risksCount || 0,
          obligationsCount: meta.obligationsCount || 0,
        };
      }
    } catch {
      // Backend not running
    }
    return undefined;
  },

  async uploadDocument(file: File): Promise<LegalDocument> {
    const headers = await getAuthHeaders();
    const formData = new FormData();
    formData.append('file', file);

    let res: Response;
    try {
      res = await fetch(`${API_BASE_URL}/documents/upload`, {
        method: 'POST',
        headers,
        body: formData,
      });
    } catch {
      throw new Error('Upload failed. Please ensure the backend server is running and try again.');
    }

    if (res.ok) {
      const meta = await res.json();
      return {
        id: meta.id,
        name: meta.name,
        type: meta.type as 'PDF' | 'DOCX' | 'TXT',
        uploadDate: meta.uploadDate,
        size: meta.size,
        analysisStatus: meta.analysisStatus as any,
        attentionScore: meta.attentionScore,
        pageCount: meta.pageCount,
        category: meta.category as any,
        summary: meta.summary,
        content: '',
        clausesCount: meta.clausesCount || 0,
        risksCount: meta.risksCount || 0,
        obligationsCount: meta.obligationsCount || 0,
      };
    }

    // Surface the server's actual reason (unsupported type, too large, auth...)
    // so the UI can show it instead of a generic failure.
    try {
      const body = await res.json();
      if (body && body.detail) throw new Error(body.detail as string);
    } catch (err) {
      if (err instanceof Error && err.message) throw err;
      // Non-JSON error body; fall through to generic message.
    }
    throw new Error(`Upload failed (server responded with status ${res.status}). Please try again.`);
  },

  async deleteDocument(id: string): Promise<boolean> {
    try {
      const headers = await getAuthHeaders();
      const res = await fetch(`${API_BASE_URL}/documents/${id}`, {
        method: 'DELETE',
        headers,
      });
      return res.ok;
    } catch {
      return false;
    }
  },
};

