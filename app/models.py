"""
Data models for the SmartLoad API.

Using Pydantic for validation - it catches most input errors automatically
and gives decent error messages. All money values are in cents (integers)
to avoid floating point issues.
"""

from pydantic import BaseModel, Field, field_validator
from typing import List
from datetime import date


class Truck(BaseModel):
    """The truck we're trying to fill with orders."""
    id: str = Field(..., min_length=1)
    max_weight_lbs: int = Field(..., gt=0)
    max_volume_cuft: int = Field(..., gt=0)


class Order(BaseModel):
    """
    A single shipment order that we might load onto the truck.
    
    Note: payout is in cents, not dollars. This avoids floating point
    precision issues when we're adding up totals.
    """
    id: str = Field(..., min_length=1)
    payout_cents: int = Field(..., ge=0)  # using cents, not dollars!
    weight_lbs: int = Field(..., gt=0)
    volume_cuft: int = Field(..., gt=0)
    origin: str = Field(..., min_length=1)
    destination: str = Field(..., min_length=1)
    pickup_date: date
    delivery_date: date
    is_hazmat: bool = False

    @field_validator('delivery_date')
    @classmethod
    def check_dates_make_sense(cls, v, info):
        """Delivery can't be before pickup - that would be weird."""
        if 'pickup_date' in info.data and v < info.data['pickup_date']:
            raise ValueError('delivery_date must be on or after pickup_date')
        return v


class OptimizeRequest(BaseModel):
    """Input to the optimization endpoint."""
    truck: Truck
    orders: List[Order] = Field(default_factory=list)

    @field_validator('orders')
    @classmethod
    def not_too_many_orders(cls, v):
        """
        Cap the number of orders to prevent abuse.
        Algorithm can handle 22 easily, but let's allow some headroom.
        """
        if len(v) > 50:
            raise ValueError('Too many orders - maximum is 50')
        return v


class OptimizeResponse(BaseModel):
    """Output from the optimization endpoint."""
    truck_id: str
    selected_order_ids: List[str]
    total_payout_cents: int  # still in cents
    total_weight_lbs: int
    total_volume_cuft: int
    utilization_weight_percent: float
    utilization_volume_percent: float
