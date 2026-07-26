"""Entry point: `python run.py` starts Cadence on http://localhost:8000"""

import uvicorn

if __name__ == "__main__":
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=False)
