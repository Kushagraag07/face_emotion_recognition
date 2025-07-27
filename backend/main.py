from fastapi import FastAPI, File, UploadFile
from fastapi.responses import JSONResponse
from deepface import DeepFace
import cv2
import numpy as np

app = FastAPI()

@app.post("/analyze_emotion/")
async def analyze_emotion(file: UploadFile = File(...)):
    contents = await file.read()
    nparr = np.frombuffer(contents, np.uint8)
    img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
    if img is None:
        return JSONResponse({"error": "Invalid image"}, status_code=400)
    try:
        result = DeepFace.analyze(img, actions=['emotion'], enforce_detection=False)
        return {"emotions": result["emotion"]}
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)