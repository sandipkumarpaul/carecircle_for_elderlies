from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException

from app.controllers.health import router
from app.controllers.auth import router as auth_router
from app.controllers.circle import router as circle_router
from app.controllers.medicines import router as medicine_router
from app.controllers.vitals import router as vitals_router

app = FastAPI(title="CareCircle API", version="0.1.0", docs_url="/api/docs",
              redoc_url=None, openapi_url="/api/openapi.json")
app.include_router(router)
app.include_router(auth_router)
app.include_router(circle_router)
app.include_router(medicine_router)
app.include_router(vitals_router)


@app.middleware('http')
async def private_responses(request: Request, call_next):
    response = await call_next(request)
    response.headers['Cache-Control'] = 'no-store'
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['Referrer-Policy'] = 'no-referrer'
    return response


@app.exception_handler(HTTPException)
async def http_error(request: Request, exc: HTTPException):
    codes = {401: "unauthenticated", 403: "forbidden", 404: "not_found", 409: "conflict"}
    return JSONResponse(status_code=exc.status_code, headers=exc.headers,
                        content={"error": {"code": codes.get(exc.status_code, "http_error"),
                                           "message": str(exc.detail), "details": []}})


@app.exception_handler(RequestValidationError)
async def validation_error(request: Request, exc: RequestValidationError):
    # Exclude raw input/context: these can contain passwords or health data.
    details = [{"field": ".".join(map(str, error["loc"])), "type": error["type"]}
               for error in exc.errors()]
    return JSONResponse(status_code=422, content={"error": {
        "code": "validation_error", "message": "Invalid request", "details": details}})


@app.exception_handler(Exception)
async def unexpected_error(request: Request, exc: Exception):
    return JSONResponse(status_code=500, content={"error": {
        "code": "internal_error", "message": "An unexpected error occurred", "details": []}})
