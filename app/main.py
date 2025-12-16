from fastapi import FastAPI, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List, Optional
import logging

from .database import engine, get_db, Base
from .models import Technology, Paper
from .schemas import TechnologyCreate, TechnologyUpdate, TechnologyResponse, PaperResponse, CollectionStats
from .services.semantic_scholar_collector import SemanticScholarCollector

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Create database tables
Base.metadata.create_all(bind=engine)

# Initialize FastAPI app
app = FastAPI(
    title="Gartner Hype Cycle API - Tech Catalog",
    description="API for managing technology catalog with keywords, excluded terms, and tickers",
    version="1.0.0"
)


@app.get("/", tags=["Root"])
def read_root():
    """Root endpoint - API status"""
    return {
        "message": "Gartner Hype Cycle API - Tech Catalog",
        "version": "1.0.0",
        "docs": "/docs"
    }


@app.post("/technologies", response_model=TechnologyResponse, status_code=201, tags=["Technologies"])
def create_technology(
    technology: TechnologyCreate,
    db: Session = Depends(get_db)
):
    """
    Create a new technology in the catalog.

    - **name**: Unique technology name
    - **description**: Optional description
    - **keywords**: List of keywords for data collection (required, at least 1)
    - **excluded_terms**: Optional list of terms to exclude from search
    - **tickers**: Optional list of stock ticker symbols
    """
    # Check if technology with same name already exists
    existing = db.query(Technology).filter(Technology.name == technology.name).first()
    if existing:
        raise HTTPException(status_code=400, detail=f"Technology with name '{technology.name}' already exists")

    # Create new technology
    db_technology = Technology(
        name=technology.name,
        description=technology.description,
        is_active=True
    )

    # Set JSON fields using properties
    db_technology.keywords = technology.keywords
    db_technology.excluded_terms = technology.excluded_terms if technology.excluded_terms else []
    db_technology.tickers = technology.tickers if technology.tickers else []

    db.add(db_technology)
    db.commit()
    db.refresh(db_technology)

    return db_technology


@app.get("/technologies", response_model=List[TechnologyResponse], tags=["Technologies"])
def list_technologies(
    is_active: Optional[bool] = Query(None, description="Filter by active status"),
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(100, ge=1, le=500, description="Maximum number of records to return"),
    db: Session = Depends(get_db)
):
    """
    List all technologies with optional filtering and pagination.

    - **is_active**: Optional filter by active/inactive status
    - **skip**: Number of records to skip (for pagination)
    - **limit**: Maximum number of records to return (max 500)
    """
    query = db.query(Technology)

    # Apply filter if provided
    if is_active is not None:
        query = query.filter(Technology.is_active == is_active)

    # Apply pagination
    technologies = query.offset(skip).limit(limit).all()

    return technologies


@app.get("/technologies/{technology_id}", response_model=TechnologyResponse, tags=["Technologies"])
def get_technology(
    technology_id: int,
    db: Session = Depends(get_db)
):
    """
    Get a specific technology by ID.

    - **technology_id**: The ID of the technology to retrieve
    """
    technology = db.query(Technology).filter(Technology.id == technology_id).first()

    if not technology:
        raise HTTPException(status_code=404, detail=f"Technology with ID {technology_id} not found")

    return technology


@app.put("/technologies/{technology_id}", response_model=TechnologyResponse, tags=["Technologies"])
def update_technology(
    technology_id: int,
    technology_update: TechnologyUpdate,
    db: Session = Depends(get_db)
):
    """
    Update a technology (partial update supported).

    - **technology_id**: The ID of the technology to update
    - All fields are optional - only provided fields will be updated
    """
    # Find existing technology
    db_technology = db.query(Technology).filter(Technology.id == technology_id).first()

    if not db_technology:
        raise HTTPException(status_code=404, detail=f"Technology with ID {technology_id} not found")

    # Update fields if provided
    update_data = technology_update.model_dump(exclude_unset=True)

    for field, value in update_data.items():
        if field == "keywords":
            db_technology.keywords = value
        elif field == "excluded_terms":
            db_technology.excluded_terms = value if value else []
        elif field == "tickers":
            db_technology.tickers = value if value else []
        else:
            setattr(db_technology, field, value)

    db.commit()
    db.refresh(db_technology)

    return db_technology


@app.delete("/technologies/{technology_id}", status_code=204, tags=["Technologies"])
def delete_technology(
    technology_id: int,
    hard_delete: bool = Query(False, description="If True, permanently delete; if False, soft delete (set is_active=False)"),
    db: Session = Depends(get_db)
):
    """
    Delete a technology (soft delete by default, hard delete if hard_delete=True).

    - **technology_id**: The ID of the technology to delete
    - **hard_delete**: If True, permanently delete from database; if False, set is_active=False
    """
    db_technology = db.query(Technology).filter(Technology.id == technology_id).first()

    if not db_technology:
        raise HTTPException(status_code=404, detail=f"Technology with ID {technology_id} not found")

    if hard_delete:
        # Permanent delete
        db.delete(db_technology)
    else:
        # Soft delete
        db_technology.is_active = False

    db.commit()

    return None


@app.post(
    "/technologies/{technology_id}/collect",
    response_model=CollectionStats,
    status_code=200,
    tags=["Collection"]
)
async def collect_papers(
    technology_id: int,
    db: Session = Depends(get_db)
):
    """
    Trigger paper collection from Semantic Scholar for a specific technology.

    - **technology_id**: ID of the technology to collect papers for

    Process:
    1. Builds query from technology keywords and excluded terms (wrapped in quotes)
    2. Searches Semantic Scholar for papers in the last 10 years
    3. Collects ALL matching papers using pagination (no batch limit)
    4. Saves papers to database with duplicate detection

    Returns collection statistics including:
    - Total papers found
    - Papers collected
    - New vs duplicate papers
    - Any errors encountered
    """
    # Verify technology exists
    technology = db.query(Technology).filter(Technology.id == technology_id).first()
    if not technology:
        raise HTTPException(status_code=404, detail=f"Technology with ID {technology_id} not found")

    if not technology.is_active:
        raise HTTPException(status_code=400, detail=f"Technology '{technology.name}' is not active")

    # Initialize collector
    collector = SemanticScholarCollector(db)

    # Execute collection
    try:
        stats = await collector.collect_papers(technology_id)
        return stats
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Collection failed: {str(e)}")
        raise HTTPException(status_code=500, detail="Collection failed. Check logs for details.")


@app.get(
    "/technologies/{technology_id}/papers",
    response_model=List[PaperResponse],
    tags=["Collection"]
)
def get_technology_papers(
    technology_id: int,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    db: Session = Depends(get_db)
):
    """
    Get all papers collected for a specific technology.

    - **technology_id**: ID of the technology
    - **skip**: Pagination offset
    - **limit**: Max results (default 100, max 1000)
    """
    # Verify technology exists
    technology = db.query(Technology).filter(Technology.id == technology_id).first()
    if not technology:
        raise HTTPException(status_code=404, detail=f"Technology with ID {technology_id} not found")

    # Query papers ordered by citation count (descending)
    papers = db.query(Paper)\
        .filter(Paper.technology_id == technology_id)\
        .order_by(Paper.citation_count.desc())\
        .offset(skip)\
        .limit(limit)\
        .all()

    return papers


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
