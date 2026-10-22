
from fastapi import FastAPI, UploadFile, File, HTTPException
from PIL import Image, UnidentifiedImageError
from io import BytesIO


def extract_dominant_colors(image, num_colors=5):
    # Convert the image to RGB
    image = image.convert("RGB")

    # Make processing faster
    image.thumbnail((150, 150))

    # Reduce similar colors into a smaller palette
    image = image.quantize(colors=num_colors)

    # Get the representative colors
    palette = image.getpalette()
    color_counts = image.getcolors()

    # Sort colors from most common to least common
    color_counts.sort(reverse=True)

    dominant_colors = []

    for count, color_index in color_counts:
        r, g, b = palette[color_index * 3: color_index * 3 + 3]

        hex_color = f"#{r:02X}{g:02X}{b:02X}"
        dominant_colors.append(hex_color)

    return dominant_colors


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

   
    # Extract dominant colors
    dominant_colors = extract_dominant_colors(image)

    return {
        "filename": file.filename,
        "width": width,
        "height": height,
        "dominant_colors": dominant_colors,
        "message": "Image analyzed successfully!"
    }

