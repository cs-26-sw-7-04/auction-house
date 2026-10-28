from pydantic import AfterValidator, BaseModel, Field, field_validator, model_validator
from decimal import Decimal
import uuid

class bidder(BaseModel):
    id: uuid.UUID
    location: str
    Resources: Resources

class Resources(BaseModel):
    thread_amount: int
    gpu: bool
    gpu_vram: int = Field(0, ge=0, description="Bidder memory amount in MB")
    ram_amount: int = Field(0, ge=0, description="Bidder Ram amount in MB")
    flops_amount: int = Field(0, ge=0, description="Bidder operations number")
    storage_amount: int = Field(0, ge=0, description="Bidder Storage in MB")

class bid(BaseModel): 
    bid: Decimal
    bidder_id: uuid.UUID
    task_id: uuid.UUID