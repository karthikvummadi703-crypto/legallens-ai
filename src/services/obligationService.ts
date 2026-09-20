import { ObligationItem } from '../types';
import { apiFetch } from '../lib/http';

export const obligationService = {
  async getObligationsForDocument(documentId: string): Promise<ObligationItem[]> {
    try {
      const res = await apiFetch(`/documents/${encodeURIComponent(documentId)}/analysis`);
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