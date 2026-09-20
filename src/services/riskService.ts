import { RiskItem } from '../types';
import { apiFetch } from '../lib/http';

export const riskService = {
  async getRisksForDocument(documentId: string): Promise<RiskItem[]> {
    try {
      const res = await apiFetch(`/documents/${encodeURIComponent(documentId)}/analysis`);
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