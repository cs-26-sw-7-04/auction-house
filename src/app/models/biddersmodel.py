from pydantic import AfterValidator, BaseModel, Field, field_validator, model_validator
from decimal import Decimal
import uuid

class bidder(BaseModel):
    id: uuid.UUID
    location: str

class Resources(BaseModel):
    thread_amount: int
    gpu: bool
    gpu_vram: int
    ram_amount: int
    flops_amount: int 
    storage_amount: int

class bid(BaseModel): 
    bid: Decimal
    bidder_id: uuid.UUID
    task_id: uuid.UUID
