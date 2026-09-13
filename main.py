"""Start the Aquarius API from the repository root: python main.py."""

import uvicorn

if __name__ == "__main__":
    uvicorn.run("services.api.app.main:app", host="127.0.0.1", port=8000, reload=True)
