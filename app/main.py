from fastapi import FastAPI, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List, Optional
import logging

from .database import engine, get_db, Base
from .models import Technology, Paper, Patent, RedditPost, NewsArticle, StockPrice, StockInfo, TechnologyAnalysis
from .schemas import (
    TechnologyCreate, TechnologyUpdate, TechnologyResponse,
    PaperResponse, CollectionStats,
    PatentResponse, PatentCollectionStats,
    RedditPostResponse, RedditCollectionStats,
    NewsArticleResponse, NewsCollectionStats,
    StockPriceResponse, StockInfoResponse, FinanceCollectionStats,
    AnalysisResponse
)
from .services.semantic_scholar_collector import SemanticScholarCollector
from .services.patents_view_collector import PatentsViewCollector
from .services.reddit_collector import RedditCollector
from .services.news_collector import NewsCollector
from .services.yahoo_finance_collector import YahooFinanceCollector
from .services.paper_metrics_calculator import PaperMetricsCalculator
from .services.hype_cycle_rule_engine import HypeCycleRuleEngine
from .config import settings

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


@app.post(
    "/technologies/{technology_id}/collect-patents",
    response_model=PatentCollectionStats,
    status_code=200,
    tags=["Patents"]
)
async def collect_patents(
    technology_id: int,
    db: Session = Depends(get_db)
):
    """
    Trigger patent collection from PatentsView for a specific technology.

    - **technology_id**: ID of the technology to collect patents for

    Process:
    1. Builds JSON query from technology keywords and excluded terms
    2. Searches PatentsView for patents in the last 10 years
    3. Collects all matching patents using cursor pagination
    4. Applies rate limiting (45 requests/minute)
    5. Saves patents with assignee data and duplicate detection

    Returns collection statistics including:
    - Total patents found
    - Patents collected
    - New vs duplicate patents
    - Any errors encountered
    """
    # Verify technology exists
    technology = db.query(Technology).filter(Technology.id == technology_id).first()
    if not technology:
        raise HTTPException(status_code=404, detail=f"Technology with ID {technology_id} not found")

    if not technology.is_active:
        raise HTTPException(status_code=400, detail=f"Technology '{technology.name}' is not active")

    # Initialize collector
    collector = PatentsViewCollector(db)

    # Execute collection
    try:
        stats = await collector.collect_patents(technology_id)
        return stats
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Patent collection failed: {str(e)}")
        raise HTTPException(status_code=500, detail="Patent collection failed. Check logs for details.")


@app.get(
    "/technologies/{technology_id}/patents",
    response_model=List[PatentResponse],
    tags=["Patents"]
)
def get_technology_patents(
    technology_id: int,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    db: Session = Depends(get_db)
):
    """
    Get all patents collected for a specific technology.

    - **technology_id**: ID of the technology
    - **skip**: Pagination offset
    - **limit**: Max results (default 100, max 1000)

    Results ordered by citation count (most cited first).
    """
    # Verify technology exists
    technology = db.query(Technology).filter(Technology.id == technology_id).first()
    if not technology:
        raise HTTPException(status_code=404, detail=f"Technology with ID {technology_id} not found")

    # Query patents ordered by citation count (descending)
    patents = db.query(Patent)\
        .filter(Patent.technology_id == technology_id)\
        .order_by(Patent.patent_num_times_cited_by_us_patents.desc())\
        .offset(skip)\
        .limit(limit)\
        .all()

    return patents


@app.post(
    "/technologies/{technology_id}/collect-reddit-posts",
    response_model=RedditCollectionStats,
    status_code=200,
    tags=["Reddit"]
)
async def collect_reddit_posts(
    technology_id: int,
    db: Session = Depends(get_db)
):
    """
    Trigger Reddit post collection for a specific technology.

    - **technology_id**: ID of the technology to collect posts for

    Process:
    1. Builds search query from technology keywords and excluded terms
    2. Searches Reddit for the top 250 most relevant posts
    3. Collects posts in 3 batches (100+100+50) using pagination
    4. Saves posts to database with duplicate detection

    Returns collection statistics including:
    - Total posts found
    - Posts collected
    - New vs duplicate posts
    - Any errors encountered
    """
    # Verify technology exists
    technology = db.query(Technology).filter(Technology.id == technology_id).first()
    if not technology:
        raise HTTPException(status_code=404, detail=f"Technology with ID {technology_id} not found")

    if not technology.is_active:
        raise HTTPException(status_code=400, detail=f"Technology '{technology.name}' is not active")

    # Initialize collector
    collector = RedditCollector(db)

    # Execute collection
    try:
        stats = await collector.collect_posts(technology_id)
        return stats
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Reddit collection failed: {str(e)}")
        raise HTTPException(status_code=500, detail="Reddit collection failed. Check logs for details.")


@app.get(
    "/technologies/{technology_id}/reddit-posts",
    response_model=List[RedditPostResponse],
    tags=["Reddit"]
)
def get_technology_reddit_posts(
    technology_id: int,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    order_by: str = Query("score", description="Order by: score, created_utc, or num_comments"),
    db: Session = Depends(get_db)
):
    """
    Get all Reddit posts collected for a specific technology.

    - **technology_id**: ID of the technology
    - **skip**: Pagination offset
    - **limit**: Max results (default 100, max 1000)
    - **order_by**: Sort field (score, created_utc, or num_comments)

    Results ordered by the specified field in descending order.
    """
    # Verify technology exists
    technology = db.query(Technology).filter(Technology.id == technology_id).first()
    if not technology:
        raise HTTPException(status_code=404, detail=f"Technology with ID {technology_id} not found")

    # Build query with ordering
    query = db.query(RedditPost).filter(RedditPost.technology_id == technology_id)

    # Apply ordering based on parameter
    if order_by == "score":
        query = query.order_by(RedditPost.score.desc())
    elif order_by == "created_utc":
        query = query.order_by(RedditPost.created_utc.desc())
    elif order_by == "num_comments":
        query = query.order_by(RedditPost.num_comments.desc())
    else:
        # Default to score if invalid parameter
        query = query.order_by(RedditPost.score.desc())

    # Apply pagination
    posts = query.offset(skip).limit(limit).all()

    return posts


@app.post(
    "/technologies/{technology_id}/collect-news",
    response_model=NewsCollectionStats,
    status_code=200,
    tags=["News"]
)
async def collect_news(
    technology_id: int,
    db: Session = Depends(get_db)
):
    """
    Trigger news article collection from NewsAPI.org for a specific technology.

    - **technology_id**: ID of the technology to collect news for

    Process:
    1. Builds search query from technology keywords and excluded terms
    2. Searches NewsAPI.org for articles in the last 10 years
    3. Collects up to 500 articles using pagination
    4. Saves articles to database with duplicate detection

    Returns collection statistics including:
    - Total articles found
    - Articles collected
    - New vs duplicate articles
    - Any errors encountered

    Rate Limit: NewsAPI free tier allows 100 requests/day
    """
    # Verify technology exists
    technology = db.query(Technology).filter(Technology.id == technology_id).first()
    if not technology:
        raise HTTPException(status_code=404, detail=f"Technology with ID {technology_id} not found")

    if not technology.is_active:
        raise HTTPException(status_code=400, detail=f"Technology '{technology.name}' is not active")

    # Initialize collector
    collector = NewsCollector(db)

    # Execute collection
    try:
        stats = await collector.collect_articles(technology_id)
        return stats
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"News collection failed: {str(e)}")
        raise HTTPException(status_code=500, detail="News collection failed. Check logs for details.")


@app.get(
    "/technologies/{technology_id}/news",
    response_model=List[NewsArticleResponse],
    tags=["News"]
)
def get_technology_news(
    technology_id: int,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    db: Session = Depends(get_db)
):
    """
    Get all news articles collected for a specific technology.

    - **technology_id**: ID of the technology
    - **skip**: Pagination offset
    - **limit**: Max results (default 100, max 1000)

    Results ordered by publication date (most recent first).
    """
    # Verify technology exists
    technology = db.query(Technology).filter(Technology.id == technology_id).first()
    if not technology:
        raise HTTPException(status_code=404, detail=f"Technology with ID {technology_id} not found")

    # Query articles ordered by publication date (descending)
    articles = db.query(NewsArticle)\
        .filter(NewsArticle.technology_id == technology_id)\
        .order_by(NewsArticle.published_at.desc())\
        .offset(skip)\
        .limit(limit)\
        .all()

    return articles


@app.post(
    "/technologies/{technology_id}/collect-finance",
    response_model=FinanceCollectionStats,
    status_code=200,
    tags=["Finance"]
)
async def collect_finance_data(
    technology_id: int,
    db: Session = Depends(get_db)
):
    """
    Trigger stock market data collection from Yahoo Finance for a specific technology.

    - **technology_id**: ID of the technology to collect finance data for

    Process:
    1. Collects 10 years of monthly OHLCV data (Open, High, Low, Close, Volume)
    2. Collects latest fundamentals (Market Cap, P/E Ratio, EPS, Beta, etc.)
    3. Collects company information (sector, industry, description)
    4. Includes market indices for comparison (NASDAQ, S&P500)

    Data sources:
    - Technology-specific tickers from technology.tickers field
    - Market indices (^IXIC NASDAQ, ^GSPC S&P500)

    Returns collection statistics including:
    - Tickers processed
    - Prices collected (new vs duplicates)
    - Company info updated
    - Any errors encountered

    Note: Yahoo Finance data is free via yfinance library (no API key required)
    Rate limiting: 0.5s delay between ticker requests
    """
    # Verify technology exists
    technology = db.query(Technology).filter(Technology.id == technology_id).first()
    if not technology:
        raise HTTPException(status_code=404, detail=f"Technology with ID {technology_id} not found")

    if not technology.is_active:
        raise HTTPException(status_code=400, detail=f"Technology '{technology.name}' is not active")

    # Initialize collector
    collector = YahooFinanceCollector(db)

    # Execute collection
    try:
        stats = await collector.collect_finance_data(technology_id)
        return stats
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Finance collection failed: {str(e)}")
        raise HTTPException(status_code=500, detail="Finance collection failed. Check logs for details.")


@app.get(
    "/technologies/{technology_id}/finance/prices",
    response_model=List[StockPriceResponse],
    tags=["Finance"]
)
def get_technology_stock_prices(
    technology_id: int,
    ticker: Optional[str] = Query(None, description="Filter by specific ticker (e.g., 'AAPL')"),
    start_date: Optional[str] = Query(None, description="Start date filter (YYYY-MM-DD)"),
    end_date: Optional[str] = Query(None, description="End date filter (YYYY-MM-DD)"),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    db: Session = Depends(get_db)
):
    """
    Get stock price time-series data for a specific technology.

    - **technology_id**: ID of the technology
    - **ticker**: Optional filter by ticker symbol
    - **start_date**: Optional start date filter (YYYY-MM-DD)
    - **end_date**: Optional end date filter (YYYY-MM-DD)
    - **skip**: Pagination offset
    - **limit**: Max results (default 100, max 1000)

    Returns OHLCV data ordered by date descending (most recent first).
    Data includes both technology-specific tickers and market indices.
    """
    # Verify technology exists
    technology = db.query(Technology).filter(Technology.id == technology_id).first()
    if not technology:
        raise HTTPException(status_code=404, detail=f"Technology with ID {technology_id} not found")

    # Build query with optional filters
    query = db.query(StockPrice).filter(StockPrice.technology_id == technology_id)

    if ticker:
        query = query.filter(StockPrice.ticker == ticker)

    if start_date:
        query = query.filter(StockPrice.date >= start_date)

    if end_date:
        query = query.filter(StockPrice.date <= end_date)

    # Order by date descending and apply pagination
    prices = query.order_by(StockPrice.date.desc()).offset(skip).limit(limit).all()

    return prices


@app.get(
    "/technologies/{technology_id}/finance/info",
    response_model=List[StockInfoResponse],
    tags=["Finance"]
)
def get_technology_stock_info(
    technology_id: int,
    db: Session = Depends(get_db)
):
    """
    Get stock metadata and fundamentals for a specific technology.

    - **technology_id**: ID of the technology

    Returns:
    - Company information (name, sector, industry, description, website)
    - Latest fundamentals snapshot (Market Cap, P/E, Beta, Dividend Yield, EPS, etc.)
    - Data for both technology-specific tickers and market indices

    Note: Fundamentals represent current snapshot updated on each collection run.
    For historical price data, use /finance/prices endpoint.
    """
    # Verify technology exists
    technology = db.query(Technology).filter(Technology.id == technology_id).first()
    if not technology:
        raise HTTPException(status_code=404, detail=f"Technology with ID {technology_id} not found")

    # Query all stock info for this technology
    stock_info = db.query(StockInfo)\
        .filter(StockInfo.technology_id == technology_id)\
        .order_by(StockInfo.ticker)\
        .all()

    return stock_info


# ============================================================================
# HYPE CYCLE ANALYSIS ENDPOINTS
# ============================================================================

@app.post(
    "/technologies/{technology_id}/analyze-papers",
    response_model=AnalysisResponse,
    status_code=200,
    tags=["Analysis"]
)
async def analyze_papers_for_hype_cycle(
    technology_id: int,
    db: Session = Depends(get_db)
):
    """
    Analyze papers for a technology to determine Hype Cycle phase.

    - **technology_id**: ID of the technology to analyze

    Process:
    1. Calculate metrics from collected papers:
       - Publication velocity trends
       - Citation growth rates
       - Research type distribution (basic vs applied)
       - Topic/keyword analysis
       - Venue type distribution

    2. Apply rule-based engine to determine phase:
       - Technology Trigger
       - Peak of Inflated Expectations
       - Trough of Disillusionment
       - Slope of Enlightenment
       - Plateau of Productivity

    3. Store analysis results in database

    Returns:
    - Current Hype Cycle phase
    - Confidence score
    - Detailed metrics
    - Rule evaluation scores
    - Rationale for phase determination

    Requirements:
    - Minimum 100 papers collected for reliable analysis
    """
    # Verify technology exists
    technology = db.query(Technology).filter(Technology.id == technology_id).first()
    if not technology:
        raise HTTPException(status_code=404, detail=f"Technology with ID {technology_id} not found")

    # Check if papers exist
    paper_count = db.query(Paper).filter(Paper.technology_id == technology_id).count()
    min_papers = settings.hype_cycle_min_papers_for_analysis

    if paper_count < min_papers:
        raise HTTPException(
            status_code=400,
            detail=f"Insufficient papers for analysis. Found {paper_count}, need at least {min_papers}."
        )

    try:
        logger.info(f"Starting Hype Cycle analysis for technology {technology_id} ({technology.name})...")

        # Calculate metrics
        logger.info("Calculating metrics from papers...")
        calculator = PaperMetricsCalculator(db)
        metrics = calculator.calculate_metrics(technology_id)

        # Determine phase using rule engine
        logger.info("Determining Hype Cycle phase...")
        engine = HypeCycleRuleEngine()
        phase, confidence, rule_scores, rationale = engine.determine_phase(metrics)

        # Get date range from papers
        papers = db.query(Paper).filter(Paper.technology_id == technology_id).all()
        years = [p.year for p in papers if p.year]
        date_range_start = f"{min(years)}-01-01" if years else None
        date_range_end = f"{max(years)}-12-31" if years else None

        # Save or update analysis
        existing_analysis = db.query(TechnologyAnalysis)\
            .filter(TechnologyAnalysis.technology_id == technology_id)\
            .first()

        if existing_analysis:
            # Update existing
            logger.info("Updating existing analysis...")
            existing_analysis.current_phase = phase.value
            existing_analysis.phase_confidence = confidence
            existing_analysis.analysis_date = func.now()
            existing_analysis.total_papers_analyzed = paper_count
            existing_analysis.date_range_start = date_range_start
            existing_analysis.date_range_end = date_range_end
            existing_analysis.metrics = metrics.to_dict()
            existing_analysis.rule_scores = rule_scores
            existing_analysis.rationale = rationale
            analysis = existing_analysis
        else:
            # Create new
            logger.info("Creating new analysis record...")
            analysis = TechnologyAnalysis(
                technology_id=technology_id,
                current_phase=phase.value,
                phase_confidence=confidence,
                total_papers_analyzed=paper_count,
                date_range_start=date_range_start,
                date_range_end=date_range_end,
                rationale=rationale
            )
            analysis.metrics = metrics.to_dict()
            analysis.rule_scores = rule_scores
            db.add(analysis)

        db.commit()
        db.refresh(analysis)

        logger.info(f"Analysis complete: {phase.value} (confidence: {confidence:.2f})")

        return analysis

    except ValueError as e:
        logger.error(f"Analysis failed: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Analysis failed: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Analysis failed: {str(e)}")


@app.get(
    "/technologies/{technology_id}/analysis",
    response_model=AnalysisResponse,
    tags=["Analysis"]
)
def get_technology_analysis(
    technology_id: int,
    db: Session = Depends(get_db)
):
    """
    Get the latest Hype Cycle analysis for a technology.

    - **technology_id**: ID of the technology

    Returns the most recent analysis including:
    - Current phase determination
    - Confidence score
    - Calculated metrics
    - Rule evaluation results
    - Rationale for phase determination

    Note: If no analysis exists, run /analyze-papers first.
    """
    # Verify technology exists
    technology = db.query(Technology).filter(Technology.id == technology_id).first()
    if not technology:
        raise HTTPException(status_code=404, detail=f"Technology with ID {technology_id} not found")

    # Get analysis
    analysis = db.query(TechnologyAnalysis)\
        .filter(TechnologyAnalysis.technology_id == technology_id)\
        .first()

    if not analysis:
        raise HTTPException(
            status_code=404,
            detail=f"No analysis found for technology {technology_id}. Run /analyze-papers first."
        )

    return analysis


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
