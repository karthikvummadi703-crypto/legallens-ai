from pydantic import BaseModel, Field
from typing import List, Optional, Literal

class ExecutiveSummary(BaseModel):
    summary: str = Field(..., description="Simple-language summary understandable to a non-lawyer without unnecessary legal jargon.")
    key_points: List[str] = Field(default_factory=list, description="3 to 5 key takeaway bullet points supported by the document.")

class ImportantClause(BaseModel):
    clause_id: str = Field(default="", description="Clause identifier e.g. 8.2 or Section 4 present in extracted document")
    title: str = Field(..., description="Short title of the clause")
    summary: str = Field(..., description="Plain language summary of clause")
    importance: Literal['high', 'medium', 'low'] = Field(default='medium')
    page: int = Field(default=1, description="Exact source page number from extracted document")
    section: str = Field(default="General", description="Section header from extracted document")
    source_text: str = Field(default="", description="Quote or excerpt from document")

class PotentialRisk(BaseModel):
    title: str = Field(..., description="Brief risk title")
    category: str = Field(..., description="Risk category: Financial, Termination, Liability, Renewal, Obligations, Privacy, Confidentiality, Dispute Resolution, Restrictive clauses, Ambiguity, or Unusual terms")
    severity: Literal['high', 'medium', 'low', 'informational'] = Field(default='medium')
    explanation: str = Field(..., description="Cautious explanation of the potential risk (e.g. 'This clause may create financial risk...')")
    why_it_matters: str = Field(..., description="Practical business or personal impact for the user")
    page: int = Field(default=1, description="Exact source page number")
    section: str = Field(default="General", description="Source section heading")
    clause_id: Optional[str] = Field(default="", description="Referenced clause ID")
    source_text: str = Field(default="", description="Quoted text from document")
    suggested_question: str = Field(default="", description="Suggested question to clarify this risk")
    confidence: Literal['high', 'medium', 'low'] = Field(default='high')

class ObligationItem(BaseModel):
    party: str = Field(..., description="Party bound by obligation (e.g. Tenant, Employee, Company, Service Provider)")
    obligation: str = Field(..., description="Explicit required action or duty explicitly present in document")
    deadline: str = Field(default="As specified in document", description="Timeframe or deadline")
    consequence: str = Field(default="Standard default terms", description="Explicit consequence of failure to perform")
    page: int = Field(default=1, description="Source page number")
    section: str = Field(default="General", description="Source section heading")

class KeyDateItem(BaseModel):
    event: str = Field(..., description="Event name (e.g. Start date, End date, Renewal date, Notice period, Payment deadline, Termination notice, Delivery deadline)")
    date_or_period: str = Field(..., description="Specific date or time period mentioned in document")
    importance: Literal['high', 'medium', 'low'] = Field(default='medium')
    page: int = Field(default=1)
    section: str = Field(default="General")

class PaymentDetails(BaseModel):
    item: str = Field(..., description="Payment item name e.g. Base Rent, Monthly Retainer, Security Deposit, Late Fee")
    amount: str = Field(..., description="Amount preserving original currency and wording")
    frequency: str = Field(default="One-time", description="Payment frequency (e.g. Monthly, Annually, Lump-sum)")
    due_date: str = Field(default="Not specified", description="Due date or payment schedule")
    late_fees: str = Field(default="None specified", description="Late fees or penalties")
    deposits: Optional[str] = Field(default="None specified", description="Deposit terms")
    refund_conditions: Optional[str] = Field(default="None specified", description="Conditions for refunds")
    additional_charges: Optional[str] = Field(default="None specified", description="Additional fees or charges")
    page: int = Field(default=1)
    section: str = Field(default="General")

class TerminationAnalysis(BaseModel):
    who_can_terminate: str = Field(..., description="Parties entitled to terminate agreement")
    conditions: str = Field(..., description="Conditions required for termination")
    notice_period: str = Field(default="Not specified", description="Required notice period")
    early_termination: Optional[str] = Field(default="Not specified", description="Early termination rights")
    penalties: str = Field(default="None specified", description="Early termination penalties or fees")
    consequences: Optional[str] = Field(default="Standard terms", description="Consequences of termination")
    cure_period: str = Field(default="None specified", description="Grace or cure period")
    summary: str = Field(..., description="Simple-language explanation referencing source location")
    page: int = Field(default=1)
    section: str = Field(default="Termination")

class RenewalAnalysis(BaseModel):
    has_renewal: bool = Field(default=False)
    automatic_renewal: bool = Field(default=False)
    renewal_period: Optional[str] = Field(default="N/A", description="Duration of renewal term")
    notice_period: str = Field(default="N/A", description="Notice required for non-renewal")
    opt_out: str = Field(default="N/A", description="Opt-out requirements")
    consequences: Optional[str] = Field(default="N/A", description="Consequences of renewal")
    summary: str = Field(default="No renewal provision was identified in the document.", description="Explanation of renewal terms or 'No renewal provision was identified in the document.'")
    page: int = Field(default=1)
    section: str = Field(default="Renewal")

class LawyerQuestionItem(BaseModel):
    question: str = Field(..., description="Specific question for a lawyer referencing document content")
    context: str = Field(..., description="Rationale for asking this question based on document text")
    page: int = Field(default=1)
    section: str = Field(default="General")

class AttentionScoreDetails(BaseModel):
    score: int = Field(..., description="Derived document attention indicator score (0-100)")
    label: str = Field(..., description="'Requires Immediate Attention' | 'Requires Review' | 'Standard Terms'")
    reasoning: str = Field(..., description="Transparent breakdown of derived score based on risk count & severity")

class FullDocumentAnalysis(BaseModel):
    document_id: str
    user_id: str
    created_at: str
    attention_score: AttentionScoreDetails
    executive_summary: ExecutiveSummary
    important_clauses: List[ImportantClause] = Field(default_factory=list)
    potential_risks: List[PotentialRisk] = Field(default_factory=list)
    obligations: List[ObligationItem] = Field(default_factory=list)
    key_dates: List[KeyDateItem] = Field(default_factory=list)
    payments: List[PaymentDetails] = Field(default_factory=list)
    termination_analysis: TerminationAnalysis
    renewal_analysis: RenewalAnalysis
    lawyer_questions: List[LawyerQuestionItem] = Field(default_factory=list)
    disclaimer: str = Field(default="LegalLens provides informational assistance and does not replace professional legal advice.")

class ComparisonDifference(BaseModel):
    clause_title: str = Field(..., description="Short title of the compared clause or topic")
    contract_a: str = Field(default="", description="Wording or status of this topic in document A")
    contract_b: str = Field(default="", description="Wording or status of this topic in document B")
    difference_type: Literal['Added', 'Removed', 'Changed', 'Unchanged'] = Field(default='Changed')
    attention_level: Literal['high', 'medium', 'low', 'informational'] = Field(default='medium')
    category: str = Field(default="General")
    ai_explanation: str = Field(default="", description="Plain-language explanation of why this difference matters")

class ComparisonSummary(BaseModel):
    total_changed: int = Field(default=0)
    new_obligations: int = Field(default=0)
    payment_changes: int = Field(default=0)
    wording_changes: int = Field(default=0)

class DocumentComparison(BaseModel):
    document_a_id: str
    document_b_id: str
    document_a_name: str = Field(default="")
    document_b_name: str = Field(default="")
    summary: ComparisonSummary = Field(default_factory=ComparisonSummary)
    differences: List[ComparisonDifference] = Field(default_factory=list)
    disclaimer: str = Field(default="LegalLens provides informational assistance and does not replace professional legal advice.")

class ChecklistItemData(BaseModel):
    id: str = Field(default="")
    section: str = Field(default="General", description="Checklist grouping: Payments, Term, Termination, Obligations, Liability, Dispute Resolution, Renewal")
    title: str = Field(..., description="Short verification task title")
    explanation: str = Field(default="", description="Why this item deserves verification before signing")
    page: int = Field(default=1)
    section_ref: str = Field(default="General", description="Source section heading in the document")
    attention_level: Literal['high', 'medium', 'low', 'informational'] = Field(default='medium')
    completed: bool = Field(default=False)

