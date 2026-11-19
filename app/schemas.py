from pydantic import BaseModel, Field


class LineItem(BaseModel):
    description: str
    quantity: float | None = None
    unit_price: float | None = None


class Invoice(BaseModel):
    vendor: str | None = None
    registration_number: str | None = None   # Japan qualified invoice no.: T + 13 digits
    invoice_number: str | None = None
    date: str | None = None
    currency: str | None = None
    subtotal: float | None = None
    tax: float | None = None
    total: float | None = None
    items: list[LineItem] = []
    source: dict = {}


class ExtractRequest(BaseModel):
    text: str = Field(min_length=1, max_length=20000)


class ExtractResponse(BaseModel):
    data: Invoice
    model: str
    latency_ms: int
    cached: bool = False
    usage: dict = {}
    warnings: list[str] = []