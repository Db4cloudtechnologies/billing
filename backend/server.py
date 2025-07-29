from fastapi import FastAPI, APIRouter, HTTPException
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
import os
import logging
from pathlib import Path
from pydantic import BaseModel, Field
from typing import List, Optional
import uuid
from datetime import datetime, date
from enum import Enum
import json

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

# MongoDB connection
mongo_url = os.environ['MONGO_URL']
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ['DB_NAME']]

# Create the main app without a prefix
app = FastAPI()

# Create a router with the /api prefix
api_router = APIRouter(prefix="/api")

# Enums
class BillingType(str, Enum):
    ADVANCE_INVOICE = "Advance invoice BR"
    STANDARD_INVOICE = "Standard invoice"
    RECEIPT = "Receipt"
    CREDIT_NOTE = "Credit note"
    PROFORMA_INVOICE = "Proforma invoice"

class DocumentStatus(str, Enum):
    DRAFT = "Draft"
    PENDING = "Pending"
    PROCESSED = "Processed"
    COMPLETED = "Completed"
    CANCELLED = "Cancelled"

class ItemCategory(str, Enum):
    PRODUCT = "Product"
    SERVICE = "Service"
    DISCOUNT = "Discount"
    TAX = "Tax"

# Models
class BillingItem(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    item_name: str
    description: Optional[str] = None
    category: ItemCategory = ItemCategory.PRODUCT
    quantity: float = 1.0
    unit_price: float = 0.0
    total_price: float = 0.0
    tax_rate: float = 0.0
    tax_amount: float = 0.0

class BillingDocument(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    document_number: str
    billing_type: BillingType
    billing_date: date
    pricing_date: Optional[date] = None
    service_rendered_date: Optional[date] = None
    due_date: Optional[date] = None
    
    # Customer information
    customer_name: Optional[str] = None
    customer_email: Optional[str] = None
    customer_address: Optional[str] = None
    
    # Items
    items: List[BillingItem] = []
    
    # Totals
    subtotal: float = 0.0
    total_tax: float = 0.0
    total_amount: float = 0.0
    
    # Status
    status: DocumentStatus = DocumentStatus.DRAFT
    
    # Metadata
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    notes: Optional[str] = None

# Request/Response models
class BillingDocumentCreate(BaseModel):
    billing_type: BillingType
    billing_date: date
    pricing_date: Optional[date] = None
    service_rendered_date: Optional[date] = None
    due_date: Optional[date] = None
    customer_name: Optional[str] = None
    customer_email: Optional[str] = None
    customer_address: Optional[str] = None
    notes: Optional[str] = None

class BillingDocumentUpdate(BaseModel):
    billing_type: Optional[BillingType] = None
    billing_date: Optional[date] = None
    pricing_date: Optional[date] = None
    service_rendered_date: Optional[date] = None
    due_date: Optional[date] = None
    customer_name: Optional[str] = None
    customer_email: Optional[str] = None
    customer_address: Optional[str] = None
    status: Optional[DocumentStatus] = None
    notes: Optional[str] = None

class BillingItemCreate(BaseModel):
    item_name: str
    description: Optional[str] = None
    category: ItemCategory = ItemCategory.PRODUCT
    quantity: float = 1.0
    unit_price: float = 0.0
    tax_rate: float = 0.0

class BillingItemUpdate(BaseModel):
    item_name: Optional[str] = None
    description: Optional[str] = None
    category: Optional[ItemCategory] = None
    quantity: Optional[float] = None
    unit_price: Optional[float] = None
    tax_rate: Optional[float] = None

# Utility functions
def calculate_item_totals(item: BillingItem) -> BillingItem:
    """Calculate total price and tax amount for an item"""
    item.total_price = item.quantity * item.unit_price
    item.tax_amount = item.total_price * (item.tax_rate / 100)
    return item

def calculate_document_totals(document: BillingDocument) -> BillingDocument:
    """Calculate document totals from items"""
    document.subtotal = sum(item.total_price for item in document.items)
    document.total_tax = sum(item.tax_amount for item in document.items)
    document.total_amount = document.subtotal + document.total_tax
    return document

def generate_document_number(billing_type: BillingType) -> str:
    """Generate document number based on type and timestamp"""
    prefix_map = {
        BillingType.ADVANCE_INVOICE: "ADV",
        BillingType.STANDARD_INVOICE: "INV",
        BillingType.RECEIPT: "RCT",
        BillingType.CREDIT_NOTE: "CN",
        BillingType.PROFORMA_INVOICE: "PRO"
    }
    prefix = prefix_map.get(billing_type, "DOC")
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    return f"{prefix}-{timestamp}"

# Routes
@api_router.get("/")
async def root():
    return {"message": "Billing System API"}

# Billing Document endpoints
@api_router.post("/billing-documents", response_model=BillingDocument)
async def create_billing_document(document_data: BillingDocumentCreate):
    """Create a new billing document"""
    try:
        document_dict = document_data.dict()
        document_dict["document_number"] = generate_document_number(document_data.billing_type)
        
        document = BillingDocument(**document_dict)
        document = calculate_document_totals(document)
        
        await db.billing_documents.insert_one(document.dict())
        return document
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error creating document: {str(e)}")

@api_router.get("/billing-documents", response_model=List[BillingDocument])
async def get_billing_documents(
    status: Optional[DocumentStatus] = None,
    billing_type: Optional[BillingType] = None,
    limit: int = 100
):
    """Get all billing documents with optional filtering"""
    try:
        query = {}
        if status:
            query["status"] = status
        if billing_type:
            query["billing_type"] = billing_type
            
        documents = await db.billing_documents.find(query).limit(limit).to_list(length=limit)
        return [BillingDocument(**doc) for doc in documents]
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching documents: {str(e)}")

@api_router.get("/billing-documents/{document_id}", response_model=BillingDocument)
async def get_billing_document(document_id: str):
    """Get a specific billing document"""
    try:
        document = await db.billing_documents.find_one({"id": document_id})
        if not document:
            raise HTTPException(status_code=404, detail="Document not found")
        return BillingDocument(**document)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching document: {str(e)}")

@api_router.put("/billing-documents/{document_id}", response_model=BillingDocument)
async def update_billing_document(document_id: str, update_data: BillingDocumentUpdate):
    """Update a billing document"""
    try:
        document = await db.billing_documents.find_one({"id": document_id})
        if not document:
            raise HTTPException(status_code=404, detail="Document not found")
        
        update_dict = {k: v for k, v in update_data.dict().items() if v is not None}
        update_dict["updated_at"] = datetime.utcnow()
        
        await db.billing_documents.update_one(
            {"id": document_id},
            {"$set": update_dict}
        )
        
        updated_document = await db.billing_documents.find_one({"id": document_id})
        return BillingDocument(**updated_document)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error updating document: {str(e)}")

@api_router.delete("/billing-documents/{document_id}")
async def delete_billing_document(document_id: str):
    """Delete a billing document"""
    try:
        result = await db.billing_documents.delete_one({"id": document_id})
        if result.deleted_count == 0:
            raise HTTPException(status_code=404, detail="Document not found")
        return {"message": "Document deleted successfully"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error deleting document: {str(e)}")

# Billing Item endpoints
@api_router.post("/billing-documents/{document_id}/items", response_model=BillingDocument)
async def add_item_to_document(document_id: str, item_data: BillingItemCreate):
    """Add an item to a billing document"""
    try:
        document = await db.billing_documents.find_one({"id": document_id})
        if not document:
            raise HTTPException(status_code=404, detail="Document not found")
        
        # Create new item
        item_dict = item_data.dict()
        item = BillingItem(**item_dict)
        item = calculate_item_totals(item)
        
        # Add item to document
        document_obj = BillingDocument(**document)
        document_obj.items.append(item)
        document_obj = calculate_document_totals(document_obj)
        document_obj.updated_at = datetime.utcnow()
        
        await db.billing_documents.update_one(
            {"id": document_id},
            {"$set": document_obj.dict()}
        )
        
        return document_obj
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error adding item: {str(e)}")

@api_router.put("/billing-documents/{document_id}/items/{item_id}", response_model=BillingDocument)
async def update_item_in_document(document_id: str, item_id: str, item_data: BillingItemUpdate):
    """Update an item in a billing document"""
    try:
        document = await db.billing_documents.find_one({"id": document_id})
        if not document:
            raise HTTPException(status_code=404, detail="Document not found")
        
        document_obj = BillingDocument(**document)
        
        # Find and update item
        item_found = False
        for i, item in enumerate(document_obj.items):
            if item.id == item_id:
                update_dict = {k: v for k, v in item_data.dict().items() if v is not None}
                for key, value in update_dict.items():
                    setattr(item, key, value)
                document_obj.items[i] = calculate_item_totals(item)
                item_found = True
                break
        
        if not item_found:
            raise HTTPException(status_code=404, detail="Item not found")
        
        document_obj = calculate_document_totals(document_obj)
        document_obj.updated_at = datetime.utcnow()
        
        await db.billing_documents.update_one(
            {"id": document_id},
            {"$set": document_obj.dict()}
        )
        
        return document_obj
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error updating item: {str(e)}")

@api_router.delete("/billing-documents/{document_id}/items/{item_id}", response_model=BillingDocument)
async def remove_item_from_document(document_id: str, item_id: str):
    """Remove an item from a billing document"""
    try:
        document = await db.billing_documents.find_one({"id": document_id})
        if not document:
            raise HTTPException(status_code=404, detail="Document not found")
        
        document_obj = BillingDocument(**document)
        
        # Remove item
        original_length = len(document_obj.items)
        document_obj.items = [item for item in document_obj.items if item.id != item_id]
        
        if len(document_obj.items) == original_length:
            raise HTTPException(status_code=404, detail="Item not found")
        
        document_obj = calculate_document_totals(document_obj)
        document_obj.updated_at = datetime.utcnow()
        
        await db.billing_documents.update_one(
            {"id": document_id},
            {"$set": document_obj.dict()}
        )
        
        return document_obj
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error removing item: {str(e)}")

# Dashboard/Statistics endpoints
@api_router.get("/dashboard/stats")
async def get_dashboard_stats():
    """Get dashboard statistics"""
    try:
        total_documents = await db.billing_documents.count_documents({})
        
        # Count by status
        status_counts = {}
        for status in DocumentStatus:
            count = await db.billing_documents.count_documents({"status": status})
            status_counts[status] = count
        
        # Count by type
        type_counts = {}
        for billing_type in BillingType:
            count = await db.billing_documents.count_documents({"billing_type": billing_type})
            type_counts[billing_type] = count
        
        # Total amount (sum of all completed documents)
        pipeline = [
            {"$match": {"status": DocumentStatus.COMPLETED}},
            {"$group": {"_id": None, "total_amount": {"$sum": "$total_amount"}}}
        ]
        total_amount_result = await db.billing_documents.aggregate(pipeline).to_list(length=1)
        total_amount = total_amount_result[0]["total_amount"] if total_amount_result else 0
        
        return {
            "total_documents": total_documents,
            "status_counts": status_counts,
            "type_counts": type_counts,
            "total_amount": total_amount
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching stats: {str(e)}")

# Include the router in the main app
app.include_router(api_router)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()