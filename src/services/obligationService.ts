import { ObligationItem } from '../types';
import { auth } from '../lib/firebase';

const API_BASE_URL = (((import.meta as any).env?.VITE_API_BASE_URL || '') as string).replace(/\/+$/, '') + '/api';

async function getAuthHeaders(): Promise<Record<string, string>> {
  const headers: Record<string, string> = {};
  if (auth.currentUser) {
    try {
      const token = await auth.currentUser.getIdToken();
      headers['Authorization'] = `Bearer ${token}`;
    } catch {
      // Ignore
    }
  }
  return headers;
}

export const obligationService = {
  async getObligationsForDocument(documentId: string): Promise<ObligationItem[]> {
    try {
      const headers = await getAuthHeaders();
      const res = await fetch(`${API_BASE_URL}/documents/${documentId}/analysis`, { headers });
      if (res.ok) {
        const data = await res.json();
        if (data.obligations && Array.isArray(data.obligations)) {
          return data.obligations.map((ob: any, idx: number) => ({
            id: `ob-${idx}`,
            party: ob.party,
            obligation: ob.obligation,
            deadline: ob.deadline,
            consequence: ob.consequence,
            isMyObligation: ob.party?.toLowerCase().includes('employee') || ob.party?.toLowerCase().includes('executive') || ob.party?.toLowerCase().includes('tenant'),
            status: 'Pending' as const,
            source: { page: ob.page, section: ob.section },
          }));
        }
      }
    } catch {
      // Backend not running
    }
    return [];
  }
};
