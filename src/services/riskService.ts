import { RiskItem } from '../types';
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

export const riskService = {
  async getRisksForDocument(documentId: string): Promise<RiskItem[]> {
    try {
      const headers = await getAuthHeaders();
      const res = await fetch(`${API_BASE_URL}/documents/${documentId}/analysis`, { headers });
      if (res.ok) {
        const data = await res.json();
        if (data.potential_risks && Array.isArray(data.potential_risks)) {
          return data.potential_risks.map((r: any, idx: number) => ({
            id: `risk-${idx}`,
            title: r.title,
            attentionLevel: r.severity,
            category: r.category,
            clauseNumber: r.clause_id || `Sec ${r.page}`,
            section: r.section,
            page: r.page,
            description: r.explanation,
            potentialImpact: r.why_it_matters,
            suggestedAction: r.suggested_question || 'Consider reviewing this provision with legal counsel.',
          }));
        }
      }
    } catch {
      // Backend not running
    }
    return [];
  }
};
