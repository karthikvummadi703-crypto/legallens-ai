export type AttentionLevel = 'high' | 'medium' | 'low' | 'informational';

export type DocumentStatus = 'Needs Review' | 'High Attention' | 'Low Attention' | 'Analyzed' | 'Processing';

export type ClauseCategory = 
  | 'Termination' 
  | 'Payment' 
  | 'Liability' 
  | 'Renewal' 
  | 'Confidentiality' 
  | 'Dispute Resolution' 
  | 'Intellectual Property' 
  | 'Non-Compete'
  | 'General';

export interface SourceReference {
  page: number;
  section: string;
  quote?: string;
  document_id?: string;
  document_name?: string;
}

export interface LegalClause {
  id: string;
  clauseNumber: string;
  title: string;
  section: string;
  page: number;
  category: ClauseCategory;
  attentionLevel: AttentionLevel;
  plainSummary: string;
  originalText: string;
  potentialConcern?: string;
  recommendation?: string;
}

export interface RiskItem {
  id: string;
  title: string;
  attentionLevel: AttentionLevel;
  category: string;
  clauseNumber: string;
  section: string;
  page: number;
  description: string;
  potentialImpact: string;
  suggestedAction: string;
}

export interface ObligationItem {
  id: string;
  party: string;
  obligation: string;
  deadline: string;
  consequence: string;
  isMyObligation: boolean;
  status: 'Pending' | 'Upcoming' | 'Fulfilled' | 'Critical';
  source: SourceReference;
}

export interface ChecklistItem {
  id: string;
  section: 'Payments' | 'Term' | 'Termination' | 'Obligations' | 'Liability' | 'Dispute Resolution';
  title: string;
  explanation: string;
  source: SourceReference;
  attentionLevel: AttentionLevel;
  completed: boolean;
}

export interface LawyerQuestion {
  id: string;
  question: string;
  rationale: string;
  sourceClause: string;
  sourceRef: SourceReference;
  category: string;
  saved?: boolean;
}

export interface KeyDateData {
  event: string;
  date_or_period: string;
  importance: AttentionLevel;
  page: number;
  section: string;
}

export interface PaymentItemData {
  item: string;
  amount: string;
  frequency: string;
  due_date: string;
  late_fees: string;
  deposits?: string;
  refund_conditions?: string;
  additional_charges?: string;
  page: number;
  section: string;
}

export interface TerminationAnalysisData {
  who_can_terminate: string;
  conditions: string;
  notice_period: string;
  early_termination?: string;
  penalties: string;
  consequences?: string;
  cure_period: string;
  summary: string;
  page: number;
  section: string;
}

export interface RenewalAnalysisData {
  has_renewal: boolean;
  automatic_renewal: boolean;
  renewal_period?: string;
  notice_period: string;
  opt_out: string;
  consequences?: string;
  summary: string;
  page: number;
  section: string;
}

export interface ExecutiveSummaryData {
  summary: string;
  key_points: string[];
}

export interface AttentionScoreDetails {
  score: number;
  label: string;
  reasoning: string;
}

export interface FullAnalysisResponse {
  document_id: string;
  user_id: string;
  created_at: string;
  attention_score: AttentionScoreDetails;
  executive_summary: ExecutiveSummaryData;
  important_clauses: Array<{
    clause_id: string;
    title: string;
    summary: string;
    importance: AttentionLevel;
    page: number;
    section: string;
    source_text: string;
  }>;
  potential_risks: Array<{
    title: string;
    category: string;
    severity: AttentionLevel;
    explanation: string;
    why_it_matters: string;
    page: number;
    section: string;
    clause_id?: string;
    source_text?: string;
    suggested_question?: string;
    confidence?: string;
  }>;
  obligations: Array<{
    party: string;
    obligation: string;
    deadline: string;
    consequence: string;
    page: number;
    section: string;
  }>;
  key_dates: KeyDateData[];
  payments: PaymentItemData[];
  termination_analysis: TerminationAnalysisData;
  renewal_analysis: RenewalAnalysisData;
  lawyer_questions: Array<{
    question: string;
    context: string;
    page: number;
    section: string;
  }>;
  disclaimer: string;
}

export interface ComparisonDifference {
  id: string;
  clauseTitle: string;
  contractA: string;
  contractB: string;
  differenceType: 'Added' | 'Removed' | 'Changed' | 'Unchanged';
  attentionLevel: AttentionLevel;
  aiExplanation: string;
  category: string;
}

export interface DocumentComparison {
  documentAId: string;
  documentBId: string;
  documentAName: string;
  documentBName: string;
  summary: {
    totalChanged: number;
    newObligations: number;
    paymentChanges: number;
    wordingChanges: number;
  };
  differences: ComparisonDifference[];
}

export interface ChatMessage {
  id: string;
  sender: 'user' | 'assistant';
  text: string;
  timestamp: string;
  sources?: SourceReference[];
  suggestedFollowUps?: string[];
}

export interface ExtractedPage {
  page_number: number;
  text: string;
  character_count: number;
}


export interface LegalDocument {
  id: string;
  name: string;
  type: 'PDF' | 'DOCX' | 'TXT';
  uploadDate: string;
  size: string;
  analysisStatus: DocumentStatus;
  indexingStatus?: string;
  attentionScore: number; // 0 - 100
  pageCount: number;
  category: 'Employment' | 'Real Estate' | 'Corporate' | 'Vendor & SaaS' | 'Confidentiality';
  summary: string;
  content?: string;
  pages?: ExtractedPage[];
  clausesCount: number;
  risksCount: number;
  obligationsCount: number;
}

export interface DashboardStats {
  documentsAnalyzed: number;
  potentialRisks: number;
  importantClauses: number;
  questionsGenerated: number;
  averageAttentionScore: number;
  pendingObligations: number;
}

export interface UserProfile {
  id?: string;
  name: string;
  email: string;
  role: string;
  avatarUrl?: string;
  company?: string;
  organization?: string;
  plan: 'Pro Hackathon Edition' | 'Enterprise' | 'Enterprise Pro';
  emailVerified?: boolean;
  provider?: string;
}

