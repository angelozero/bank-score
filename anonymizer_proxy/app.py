"""
Proxy for Presidio Anonymizer that applies custom operators.

The Presidio Anonymizer REST API ignores the 'operators' field in the JSON payload,
so this proxy uses the Presidio Python API directly to apply custom replace operators.
All other endpoints are forwarded to the real Presidio Anonymizer upstream.
"""

import os
import httpx
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from presidio_anonymizer import AnonymizerEngine
from presidio_anonymizer.entities import RecognizerResult, OperatorConfig

app = FastAPI()

ANONYMIZER_UPSTREAM = os.getenv(
    "ANONYMIZER_UPSTREAM", "http://presidio-anonymizer-upstream:3000"
)

# Custom operators: map entity_type -> OperatorConfig
CUSTOM_OPERATORS = {
    "BRAZIL_CPF": OperatorConfig("replace", {"new_value": "XXX.***.***-XX"}),
}

engine = AnonymizerEngine()


@app.post("/anonymize")
async def anonymize(request: Request):
    print(f"\n\n[ANONYMIZE] - anonymize - Received request\n\n")  # Debug log
    """Use Presidio Python API directly with custom operators."""
    payload = await request.json()

    text = payload.get("text", "")
    analyzer_results_raw = payload.get("analyzer_results", [])

    # Convert raw dicts to RecognizerResult objects
    analyzer_results = []
    for item in analyzer_results_raw:
        analyzer_results.append(
            RecognizerResult(
                entity_type=item["entity_type"],
                start=item["start"],
                end=item["end"],
                score=item.get("score", 1.0),
            )
        )

    # Build operators: use custom ones, fall back to default replace
    operators = dict(CUSTOM_OPERATORS)

    # Anonymize using the Python engine
    result = engine.anonymize(
        text=text,
        analyzer_results=analyzer_results,
        operators=operators,
    )

    # Return in the same format as the Presidio REST API
    response = {
        "text": result.text,
        "items": [
            {
                "start": item.start,
                "end": item.end,
                "entity_type": item.entity_type,
                "text": item.text,
                "operator": item.operator,
            }
            for item in result.items
        ],
    }

    return JSONResponse(content=response)


@app.api_route("/{path:path}", methods=["GET", "POST", "PUT", "DELETE"])
async def proxy_all(path: str, request: Request):
    print(f"\n\n[ANONYMIZE] - proxy_all - Received request\n\n")  # Debug log
    """Forward all other requests to the real anonymizer unchanged."""
    body = await request.body()
    async with httpx.AsyncClient() as client:
        resp = await client.request(
            method=request.method,
            url=f"{ANONYMIZER_UPSTREAM}/{path}",
            content=body,
            headers={
                k: v
                for k, v in request.headers.items()
                if k.lower() not in ("host", "content-length")
            },
            timeout=30.0,
        )
        return JSONResponse(content=resp.json(), status_code=resp.status_code)


if __name__ == "__main__":
    import uvicorn

    port = int(os.getenv("PORT", "3000"))
    uvicorn.run(app, host="0.0.0.0", port=port)
