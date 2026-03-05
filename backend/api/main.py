"""
Motor Insurance Risk-Based Premium API v3.0
FastAPI backend — IT22271600
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

from .routes import policy, renewal, claims, dashboard, predict, explain

app = FastAPI(
    title="Motor Insurance Risk-Based Premium API v3.0",
    description="""
## IT22271600 — Elite-Grade Insurance ML System

### What's new in v3.0:
-  **Full Pipeline Artifacts** — no training-deployment mismatch
-  **Frequency-Severity Actuarial Model** — E[Loss] = P(Claim) × E[Severity|Claim]
-  **SHAP Explainability** — top 5 risk drivers per policy
-  **Probability Calibration** — Brier score + ECE + reliability diagram
-  **Cost-Sensitive Threshold** — optimal cutoff (not 0.5) based on insurance cost matrix
-  **Model Governance** — model card, PSI drift, versioning, artifact registry
""",
    version="3.0.0",
    docs_url="/api/docs",
)

app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

app.include_router(predict.router,   prefix="/api/v1", tags=["ML Predictions"])
app.include_router(explain.router,   prefix="/api/v1", tags=["Explainability & Governance"])
app.include_router(policy.router,    prefix="/api/v1", tags=["Policy"])
app.include_router(renewal.router,   prefix="/api/v1", tags=["Renewal"])
app.include_router(claims.router,    prefix="/api/v1", tags=["Claims"])
app.include_router(dashboard.router, prefix="/api/v1", tags=["Dashboard"])

@app.get("/")
async def root():
    return {"message": "Motor Insurance API v3.0 — IT22271600", "docs": "/api/docs",
            "features": ["full_pipeline","freq_severity","shap","calibration","cost_threshold","governance"]}

@app.get("/health")
async def health():
    from .routes.explain import get_engine as ge
    try:
        engine = ge()
        return {"status": "healthy", "models_loaded": engine.is_ready(),
                "optimal_threshold": engine.optimal_threshold, "version": "3.0.0"}
    except:
        return {"status": "healthy", "models_loaded": False}

if __name__ == "__main__":
    uvicorn.run("backend.api.main:app", host="0.0.0.0", port=8000, reload=True)
