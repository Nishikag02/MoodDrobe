
from fastapi import FastAPI, UploadFile, File, HTTPException
from PIL import Image, UnidentifiedImageError
from io import BytesIO

app = FastAPI(title="MoodDrobe ML Service")


@app.get("/")
def home():
    return {"message": "MoodDrobe ML Service is running!"}


@app.get("/health")
def health_check():
    return {"status": "healthy"}


@app.post("/analyze-image")
async def analyze_image(file: UploadFile = File(...)):
    if not file.content_type or not file.content_type.startswith("image/"):
        raise HTTPException(
            status_code=400,
            detail="Please upload an image file."
        )

    image_bytes = await file.read()

    try:
        image = Image.open(BytesIO(image_bytes))
        image.verify()

        image = Image.open(BytesIO(image_bytes))
        width, height = image.size

    except (UnidentifiedImageError, OSError):
        raise HTTPException(
            status_code=400,
            detail="The uploaded file is not a valid image."
        )

    return {
        "filename": file.filename,
        "width": width,
        "height": height,
        "message": "Image received successfully!"
    }
