"""
SmartLoad API - Main application entry point.
"""

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
import logging

from app.models import OptimizeRequest, OptimizeResponse
from app.optimizer import optimize_load

# basic logging setup
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="SmartLoad Optimization API",
    description="Finds the most profitable combination of shipments for a truck",
    version="1.0.0",
)

# reject anything over 1MB - don't want someone sending us a huge payload
MAX_CONTENT_LENGTH = 1 * 1024 * 1024


@app.exception_handler(RequestValidationError)
async def handle_validation_error(request: Request, exc: RequestValidationError):
    """
    Return 400 with readable error messages when validation fails.
    The default pydantic errors are a bit hard to read, so we clean them up.
    """
    errors = []
    for error in exc.errors():
        field = " -> ".join(str(x) for x in error["loc"])
        errors.append(f"{field}: {error['msg']}")
    
    return JSONResponse(
        status_code=400,
        content={"error": "Validation error", "details": errors}
    )


@app.middleware("http")
async def check_payload_size(request: Request, call_next):
    """Block requests that are too large before we try to parse them."""
    content_length = request.headers.get("content-length")
    if content_length and int(content_length) > MAX_CONTENT_LENGTH:
        return JSONResponse(
            status_code=413,
            content={"error": "Payload too large", "max_size_bytes": MAX_CONTENT_LENGTH}
        )
    return await call_next(request)


# health check endpoints - supporting multiple common patterns
# so it works with kubernetes, docker, spring-style health checks, etc.
@app.get("/healthz")
@app.get("/health")
@app.get("/actuator/health")
async def health_check():
    """Simple health check for container orchestration."""
    return {"status": "UP"}


@app.post("/api/v1/load-optimizer/optimize", response_model=OptimizeResponse)
async def optimize_truck_load(request: OptimizeRequest):
    """
    Main endpoint - finds the best combination of orders for a truck.
    
    Takes into account:
    - Weight and volume limits
    - Route compatibility (orders must have same origin/destination)
    - Time windows (pickup/delivery dates must overlap)
    - Hazmat rules (can't mix hazmat with regular cargo)
    """
    try:
        order_count = len(request.orders)
        logger.info(f"Optimizing: truck={request.truck.id}, orders={order_count}")
        
        result = optimize_load(request.truck, request.orders)
        
        # log the result for debugging
        payout_dollars = result['total_payout_cents'] / 100
        logger.info(f"Done: selected {len(result['selected_order_ids'])} orders, ${payout_dollars:.2f}")
        
        return OptimizeResponse(**result)
    
    except Exception as e:
        # something unexpected happened - log it and return 500
        logger.error(f"Optimization failed: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")


@app.get("/")
async def root():
    """Just a simple landing page with API info."""
    return {
        "service": "SmartLoad Optimization API",
        "version": "1.0.0",
        "endpoints": {
            "optimize": "POST /api/v1/load-optimizer/optimize",
            "health": "GET /healthz"
        }
    }
