import { LegalClause, ChecklistItem, LawyerQuestion, FullAnalysisResponse, RiskItem } from '../types';
import { auth } from '../lib/firebase';

const API_BASE_URL = (((import.meta as any).env?.VITE_API_BASE_URL || '') as string).replace(/\/+$/, '') + '/api';

async function getAuthHeaders(): Promise<Record<string, string>> {
  const headers: Record<string, string> = {};
  if (auth.currentUser) {
    try {
      const token = await auth.currentUser.getIdToken();
      headers['Authorization'] = `Bearer ${token}`;
    } catch {
      // Ignore token error in offline dev
    }
  }
  return headers;
}

export const analysisService = {
  async analyzeDocument(documentId: string): Promise<FullAnalysisResponse | null> {
    try {
      const headers = await getAuthHeaders();
      const res = await fetch(`${API_BASE_URL}/documents/${documentId}/analyze`, {
        method: 'POST',
        headers,
      });
      if (res.ok) {
        const data: FullAnalysisResponse = await res.json();
        return data;
      }
    } catch {
      // Backend not running
    }
    return null;
  },

  async getAnalysis(documentId: string): Promise<FullAnalysisResponse | null> {
    try {
      const headers = await getAuthHeaders();
      const res = await fetch(`${API_BASE_URL}/documents/${documentId}/analysis`, { headers });
      if (res.ok) {
        const data: FullAnalysisResponse = await res.json();
        return data;
      }
    } catch {
      // Backend not running
    }
    return null;
  },

  async getClausesForDocument(documentId: string): Promise<LegalClause[]> {
    const analysis = await this.getAnalysis(documentId);
    if (analysis && analysis.important_clauses && analysis.important_clauses.length > 0) {
      return analysis.important_clauses.map((c, idx) => ({
        id: `cl-${idx}-${c.clause_id || 'general'}`,
        clauseNumber: c.clause_id || `Section ${idx + 1}`,
        title: c.title,
        section: c.section,
        page: c.page,
        category: (c.section.includes('Termination') ? 'Termination' : c.section.includes('Payment') ? 'Payment' : c.section.includes('Renewal') ? 'Renewal' : 'General') as any,
        attentionLevel: c.importance,
        plainSummary: c.summary,
        originalText: c.source_text || c.summary,
        potentialConcern: c.importance === 'high' ? 'High attention clause flagged for careful review prior to signing.' : undefined,
      }));
    }
    return [];
  },

  async getRisksForDocument(documentId: string): Promise<RiskItem[]> {
    const analysis = await this.getAnalysis(documentId);
    if (analysis && analysis.potential_risks && analysis.potential_risks.length > 0) {
      return analysis.potential_risks.map((r, idx) => ({
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
    return [];
  },

  async getChecklistForDocument(documentId: string): Promise<ChecklistItem[]> {
    // No backend endpoint for checklist items; built from analysis data
    const analysis = await this.getAnalysis(documentId);
    if (!analysis) return [];
    const checklist: ChecklistItem[] = [];
    const items = [
      ...(analysis.obligations || []).map((ob, idx) => ({
        section: 'Obligations' as const,
        title: `Review obligation: ${ob.obligation}`,
        explanation: `This document requires: ${ob.obligation}. Deadline: ${ob.deadline}. Consequence of non-compliance: ${ob.consequence}.`,
        source: { page: ob.page, section: ob.section },
      })),
      ...(analysis.payments || []).map((p, idx) => ({
        section: 'Payments' as const,
        title: `Verify payment: ${p.item}`,
        explanation: `This document requires ${p.amount} (${p.frequency}). Due: ${p.due_date}. Late fees: ${p.late_fees}.`,
        source: { page: p.page, section: p.section },
      })),
    ];
    items.forEach((item, idx) => {
      checklist.push({ id: `chk-${idx}`, ...item, attentionLevel: 'medium', completed: false });
    });
    return checklist;
  },

  async getLawyerQuestions(documentId: string): Promise<LawyerQuestion[]> {
    const analysis = await this.getAnalysis(documentId);
    if (analysis && analysis.lawyer_questions && analysis.lawyer_questions.length > 0) {
      return analysis.lawyer_questions.map((q, idx) => ({
        id: `q-${idx}`,
        question: q.question,
        rationale: q.context,
        sourceClause: q.section,
        sourceRef: { page: q.page, section: q.section },
        category: q.section,
        saved: false,
      }));
    }
    return [];
  },
};

