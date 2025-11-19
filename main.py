import os
from typing import List, Optional
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from bson import ObjectId

from database import db, create_document, get_documents

app = FastAPI(title="Bookish Atelier API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---- Models ----
class ProductIn(BaseModel):
    title: str
    description: Optional[str] = None
    price: float = Field(..., ge=0)
    category: str
    image: Optional[str] = None
    rating: Optional[float] = Field(default=4.5, ge=0, le=5)
    tags: List[str] = []

class Product(ProductIn):
    id: str

# ---- Helpers ----
CATEGORIES = [
    {"slug": "books", "name": "Books"},
    {"slug": "merch", "name": "Merch"},
    {"slug": "study", "name": "Study Utilities"},
    {"slug": "snacks", "name": "Snacks"},
]

def serialize_product(doc) -> Product:
    return Product(
        id=str(doc.get("_id")),
        title=doc.get("title", ""),
        description=doc.get("description"),
        price=float(doc.get("price", 0)),
        category=doc.get("category", ""),
        image=doc.get("image"),
        rating=float(doc.get("rating", 0) or 0),
        tags=list(doc.get("tags", []) or []),
    )

async def seed_products_if_empty():
    try:
        if db is None:
            return
        count = db["product"].count_documents({})
        if count > 0:
            return
        samples = [
            {"title": "The Bookish Atelier Journal", "description": "A5 dotted journal for notes and sketches.", "price": 14.99, "category": "study", "image": "/images/journal.jpg", "rating": 4.7, "tags": ["notebook", "stationery"]},
            {"title": "Espresso Shot (Campus Café)", "description": "Quick energy boost while you browse.", "price": 2.49, "category": "snacks", "image": "/images/espresso.jpg", "rating": 4.6, "tags": ["coffee"]},
            {"title": "Bookish Atelier Tote", "description": "Canvas tote for your reads.", "price": 12.0, "category": "merch", "image": "/images/tote.jpg", "rating": 4.4, "tags": ["bag", "gift"]},
            {"title": "Annotated Classics: Pride & Prejudice", "description": "Curated edition with study notes.", "price": 18.5, "category": "books", "image": "/images/pnp.jpg", "rating": 4.9, "tags": ["classic", "novel"]},
            {"title": "Gel Ink Pens (Set of 5)", "description": "Smooth writing, 0.5mm.", "price": 6.99, "category": "study", "image": "/images/pens.jpg", "rating": 4.3, "tags": ["pen", "stationery"]},
            {"title": "Matcha Cookie", "description": "Crisp, lightly sweet.", "price": 1.99, "category": "snacks", "image": "/images/cookie.jpg", "rating": 4.2, "tags": ["cookie"]},
            {"title": "Hardcover: The Midnight Library", "description": "Best-selling novel.", "price": 22.0, "category": "books", "image": "/images/midnight.jpg", "rating": 4.8, "tags": ["fiction"]},
            {"title": "Enamel Pin – Book Lover", "description": "Cute collectible pin.", "price": 4.5, "category": "merch", "image": "/images/pin.jpg", "rating": 4.1, "tags": ["pin", "gift"]},
        ]
        for s in samples:
            create_document("product", s)
    except Exception:
        # Silent fail to avoid blocking startup
        pass

@app.on_event("startup")
async def on_startup():
    await seed_products_if_empty()

# ---- Routes ----
@app.get("/")
def read_root():
    return {"message": "Welcome to Bookish Atelier API"}

@app.get("/api/categories")
def get_categories():
    return CATEGORIES

@app.get("/api/products", response_model=List[Product])
def list_products(category: Optional[str] = Query(None), q: Optional[str] = Query(None), limit: int = Query(40, ge=1, le=100)):
    if db is None:
        # Provide a minimal in-memory fallback view only for demo when DB not configured
        demo = [
            {"_id": ObjectId(), "title": "Sample Book", "description": "Demo product (DB not configured)", "price": 9.99, "category": "books", "image": None, "rating": 4.5, "tags": []}
        ]
        return [serialize_product(d) for d in demo]

    filter_dict = {}
    if category:
        filter_dict["category"] = category
    if q:
        filter_dict["$or"] = [
            {"title": {"$regex": q, "$options": "i"}},
            {"description": {"$regex": q, "$options": "i"}},
            {"tags": {"$regex": q, "$options": "i"}},
        ]

    docs = get_documents("product", filter_dict=filter_dict, limit=limit)
    return [serialize_product(d) for d in docs]

@app.post("/api/products", response_model=Product)
def create_product(product: ProductIn):
    if db is None:
        raise HTTPException(status_code=500, detail="Database not available")
    new_id = create_document("product", product)
    doc = db["product"].find_one({"_id": ObjectId(new_id)})
    return serialize_product(doc)

@app.get("/test")
def test_database():
    response = {
        "backend": "✅ Running",
        "database": "❌ Not Available",
        "database_url": None,
        "database_name": None,
        "connection_status": "Not Connected",
        "collections": []
    }
    try:
        if db is not None:
            response["database"] = "✅ Available"
            response["database_url"] = "✅ Set" if os.getenv("DATABASE_URL") else "❌ Not Set"
            response["database_name"] = os.getenv("DATABASE_NAME") or "❌ Not Set"
            response["connection_status"] = "Connected"
            try:
                collections = db.list_collection_names()
                response["collections"] = collections[:10]
                response["database"] = "✅ Connected & Working"
            except Exception as e:
                response["database"] = f"⚠️ Connected but Error: {str(e)[:50]}"
        else:
            response["database"] = "❌ Not Available"
    except Exception as e:
        response["database"] = f"❌ Error: {str(e)[:50]}"
    return response

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
