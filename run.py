"""Откройте файл в PyCharm и нажмите Run. Зависимости должны быть установлены."""
import uvicorn

if __name__ == "__main__":
    uvicorn.run("app.main:app", host="127.0.0.1", port=8000, reload=True)
