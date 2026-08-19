import uvicorn
import os

if __name__ == "__main__":
    port = int(os.getenv("PORT", 8000))
    host = os.getenv("HOST", "0.0.0.0")
    backend_dir = os.path.dirname(os.path.abspath(__file__))
    app_dir = os.path.join(backend_dir, "app")
    
    print(f">> Starting SIH 2026 FastAPI Server on http://localhost:{port}")
    print(f">> Swagger API Docs available at http://localhost:{port}/docs")
    uvicorn.run("app.main:app", host=host, port=port, reload=True, reload_dirs=[app_dir])
