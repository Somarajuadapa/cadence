"""Entry point: `python run.py` starts Cadence.

Binds to $PORT if set (deploy hosts inject it), otherwise 8000.
"""

import os

import uvicorn

if __name__ == "__main__":
    port = int(os.environ.get("PORT", "8000"))
    uvicorn.run("app.main:app", host="0.0.0.0", port=port, reload=False)
