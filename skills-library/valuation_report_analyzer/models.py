"""Pydantic output models for Israeli real estate valuation report analysis."""

from typing import List, Optional
from pydantic import BaseModel, Field


# ============== Project Info Models ==============

class ProjectIdentification(BaseModel):
    """Project identification details."""
    project_name: str = Field(..., alias="projectName", description="Project name (Hebrew)")
    developer: Optional[str] = Field(None, description="Developer/builder name (Hebrew)")
    company_number: Optional[str] = Field(None, alias="companyNumber", description="Company registration number")
    project_type: Optional[str] = Field(
        None,
        alias="projectType",
        description="Type: שוק_חופשי|מחיר_מופחת|מחיר_למשתכן|פינוי_בינוי|תמא38|מעורב"
    )
    tender_number: Optional[str] = Field(None, alias="tenderNumber", description="Tender number if applicable")


class ProjectLocation(BaseModel):
    """Project location details."""
    city: str = Field(..., description="City name (Hebrew)")
    neighborhood: Optional[str] = Field(None, description="Neighborhood (Hebrew)")
    street: Optional[str] = Field(None, description="Street address (Hebrew)")
    block: Optional[int] = Field(None, description="Block number (גוש)")
    parcels: Optional[str] = Field(None, description="Parcel numbers (חלקה)")


class ProjectScale(BaseModel):
    """Project scale metrics."""
    total_units: int = Field(..., alias="totalUnits", description="Total number of units")
    reduced_price_units: Optional[int] = Field(None, alias="reducedPriceUnits", description="Units in reduced price track")
    free_market_units: Optional[int] = Field(None, alias="freeMarketUnits", description="Units in free market track")
    total_buildings: Optional[int] = Field(None, alias="totalBuildings", description="Number of buildings")


class ReportInfo(BaseModel):
    """Report metadata."""
    appraiser: Optional[str] = Field(None, description="Appraiser name (Hebrew)")
    appraiser_company: Optional[str] = Field(None, alias="appraiserCompany", description="Appraiser company (Hebrew)")
    report_date: Optional[str] = Field(None, alias="reportDate", description="Report date DD/MM/YYYY")
    client: Optional[str] = Field(None, description="Client name (Hebrew)")


class ProjectInfo(BaseModel):
    """Complete project information."""
    identification: ProjectIdentification
    location: ProjectLocation
    scale: ProjectScale
    report_info: Optional[ReportInfo] = Field(None, alias="reportInfo")

    class Config:
        populate_by_name = True


# ============== Financial Models ==============

class RevenueData(BaseModel):
    """Revenue information."""
    total: int = Field(..., description="Total revenue (integer, no symbols)")
    original_term: Optional[str] = Field(None, alias="originalTerm", description="Original Hebrew term")
    excludes_vat: Optional[bool] = Field(None, alias="excludesVAT", description="Whether amount excludes VAT")


class ExpenseData(BaseModel):
    """Expense information."""
    total: int = Field(..., description="Total expenses (integer)")
    original_term: Optional[str] = Field(None, alias="originalTerm", description="Original Hebrew term")


class ProfitData(BaseModel):
    """Profit information."""
    amount: int = Field(..., description="Profit amount (integer)")
    original_term: Optional[str] = Field(None, alias="originalTerm", description="Original Hebrew term")
    margin_to_revenue: Optional[float] = Field(None, alias="marginToRevenue", description="Profit margin to revenue %")
    margin_to_expenses: Optional[float] = Field(None, alias="marginToExpenses", description="Profit margin to expenses %")


class PerUnitData(BaseModel):
    """Per-unit financial metrics."""
    average_revenue: Optional[int] = Field(None, alias="averageRevenue", description="Average revenue per unit")
    reduced_price_avg: Optional[int] = Field(None, alias="reducedPriceAvg", description="Average for reduced price units")
    free_market_avg: Optional[int] = Field(None, alias="freeMarketAvg", description="Average for free market units")


class FinancialSummary(BaseModel):
    """Financial summary data."""
    revenue: RevenueData
    expenses: ExpenseData
    profit: ProfitData
    per_unit: Optional[PerUnitData] = Field(None, alias="perUnit")

    class Config:
        populate_by_name = True


class ExpenseItem(BaseModel):
    """Individual expense item."""
    item: str = Field(..., description="Item name (Hebrew)")
    amount: int = Field(..., description="Amount (integer)")
    price_per_sqm: Optional[float] = Field(None, alias="pricePerSqm", description="Price per sqm if applicable")


class LandAcquisition(BaseModel):
    """Land acquisition costs."""
    amount: int = Field(..., description="Land cost")
    status: Optional[str] = Field(None, description="Payment status (Hebrew)")


class AcquisitionCosts(BaseModel):
    """Acquisition cost breakdown."""
    land: Optional[LandAcquisition] = None
    development: Optional[int] = Field(None, description="Development costs")
    purchase_tax: Optional[int] = Field(None, alias="purchaseTax", description="Purchase tax")
    total_acquisition: Optional[int] = Field(None, alias="totalAcquisition", description="Total acquisition costs")


class DirectConstruction(BaseModel):
    """Direct construction costs."""
    total: int = Field(..., description="Total direct construction")
    original_term: Optional[str] = Field(None, alias="originalTerm", description="Original Hebrew term")
    breakdown: List[ExpenseItem] = Field(default_factory=list, description="Itemized breakdown")


class ConstructionCosts(BaseModel):
    """Construction cost breakdown."""
    direct: Optional[DirectConstruction] = None


class IndirectCosts(BaseModel):
    """Indirect costs."""
    total: Optional[int] = Field(None, description="Total indirect costs")
    breakdown: List[ExpenseItem] = Field(default_factory=list, description="Itemized breakdown")


class ExpenseBreakdown(BaseModel):
    """Complete expense breakdown."""
    acquisition: Optional[AcquisitionCosts] = None
    construction: Optional[ConstructionCosts] = None
    indirect: Optional[IndirectCosts] = None
    total_expenses: Optional[int] = Field(None, alias="totalExpenses", description="Total of all expenses")

    class Config:
        populate_by_name = True


# ============== Risk Models ==============

class RiskItem(BaseModel):
    """Individual risk item."""
    category: str = Field(
        ...,
        description="Risk category: permits|regulatory|construction|market|legal|archaeological|environmental|financial"
    )
    description: str = Field(..., description="Risk description (Hebrew)")
    severity: str = Field(..., description="Severity: low|medium|high")
    mitigation: Optional[str] = Field(None, description="Mitigation measures (Hebrew)")


class OverallAssessment(BaseModel):
    """Overall risk assessment."""
    level: str = Field(..., description="Overall level: low|medium|high")
    main_concerns: List[str] = Field(default_factory=list, alias="mainConcerns", description="Main concerns (Hebrew)")


class ConditionalFlags(BaseModel):
    """Conditional report flags."""
    conditional_report: bool = Field(False, alias="conditionalReport", description="Is this a conditional report")
    permit_pending: bool = Field(False, alias="permitPending", description="Building permit pending")
    reduced_price_approval_pending: bool = Field(
        False,
        alias="reducedPriceApprovalPending",
        description="Reduced price approval pending"
    )
    archaeological_risk: bool = Field(False, alias="archaeologicalRisk", description="Archaeological site risk")


class RiskAssessment(BaseModel):
    """Complete risk assessment."""
    identified: List[RiskItem] = Field(default_factory=list, description="Identified risks")
    overall_assessment: Optional[OverallAssessment] = Field(None, alias="overallAssessment")
    conditional_flags: Optional[ConditionalFlags] = Field(None, alias="conditionalFlags")

    class Config:
        populate_by_name = True


# ============== Main Result Model ==============

class ValuationReportResult(BaseModel):
    """Complete valuation report extraction result."""

    project_info: ProjectInfo = Field(..., alias="projectInfo", description="Project identification and info")
    financial_summary: Optional[FinancialSummary] = Field(None, alias="financialSummary", description="Financial summary")
    expense_breakdown: Optional[ExpenseBreakdown] = Field(None, alias="expenseBreakdown", description="Expense breakdown")
    risks: Optional[RiskAssessment] = Field(None, description="Risk assessment")

    class Config:
        populate_by_name = True
