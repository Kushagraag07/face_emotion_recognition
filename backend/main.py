from fastapi import FastAPI, File, UploadFile
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from deepface import DeepFace
import cv2
import numpy as np
import face_recognition
from PIL import Image
import io
import mediapipe as mp
from skimage import measure
from skimage.measure import label, regionprops
import imutils

app = FastAPI()

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize MediaPipe
mp_face_detection = mp.solutions.face_detection
mp_face_mesh = mp.solutions.face_mesh
mp_hands = mp.solutions.hands
mp_drawing = mp.solutions.drawing_utils

def detect_multiple_faces_mediapipe(image):
    """Enhanced multiple face detection using MediaPipe"""
    try:
        with mp_face_detection.FaceDetection(
            model_selection=1, min_detection_confidence=0.5) as face_detection:
            
            # Convert BGR to RGB
            rgb_image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
            results = face_detection.process(rgb_image)
            
            if results.detections:
                return len(results.detections) > 1, len(results.detections)
            return False, 0
    except Exception as e:
        print(f"Error in MediaPipe face detection: {e}")
        return False, 0

def detect_mobile_device_enhanced(image):
    """Enhanced mobile device detection using multiple techniques"""
    try:
        # Convert to grayscale
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        
        # Apply Gaussian blur to reduce noise
        blurred = cv2.GaussianBlur(gray, (5, 5), 0)
        
        # Edge detection with different thresholds
        edges_low = cv2.Canny(blurred, 30, 100)
        edges_high = cv2.Canny(blurred, 50, 150)
        
        # Combine edge detections
        edges = cv2.bitwise_or(edges_low, edges_high)
        
        # Morphological operations to connect edges
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
        edges = cv2.morphologyEx(edges, cv2.MORPH_CLOSE, kernel)
        
        # Find contours
        contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        # Filter contours based on area and aspect ratio
        for contour in contours:
            area = cv2.contourArea(contour)
            if area < 500:  # Too small
                continue
                
            # Get bounding rectangle
            x, y, w, h = cv2.boundingRect(contour)
            aspect_ratio = w / float(h)
            
            # Phone/tablet typically have aspect ratio between 0.5 and 2.0
            if 0.5 <= aspect_ratio <= 2.0:
                # Approximate the contour
                epsilon = 0.02 * cv2.arcLength(contour, True)
                approx = cv2.approxPolyDP(contour, epsilon, True)
                
                # Check if it's roughly rectangular (4-6 points)
                if 4 <= len(approx) <= 6:
                    # Calculate rectangularity
                    rect_area = w * h
                    contour_area = cv2.contourArea(contour)
                    rectangularity = contour_area / rect_area
                    
                    if rectangularity > 0.7:  # Good rectangular shape
                        return True
        
        return False
    except Exception as e:
        print(f"Error in enhanced mobile device detection: {e}")
        return False

def analyze_eye_gaze_mediapipe(image):
    """Enhanced eye gaze analysis using MediaPipe Face Mesh"""
    try:
        with mp_face_mesh.FaceMesh(
            static_image_mode=False,
            max_num_faces=1,
            refine_landmarks=True,
            min_detection_confidence=0.5,
            min_tracking_confidence=0.5) as face_mesh:
            
            # Convert BGR to RGB
            rgb_image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
            results = face_mesh.process(rgb_image)
            
            if not results.multi_face_landmarks:
                return {"looking_away": True, "confidence": 0.8, "reason": "No face detected"}
            
            # Get the first face landmarks
            face_landmarks = results.multi_face_landmarks[0]
            
            # Get eye landmarks (MediaPipe face mesh indices)
            # Left eye landmarks
            left_eye_top = face_landmarks.landmark[159]  # Upper eyelid
            left_eye_bottom = face_landmarks.landmark[145]  # Lower eyelid
            left_eye_left = face_landmarks.landmark[33]  # Left corner
            left_eye_right = face_landmarks.landmark[133]  # Right corner
            
            # Right eye landmarks
            right_eye_top = face_landmarks.landmark[386]  # Upper eyelid
            right_eye_bottom = face_landmarks.landmark[374]  # Lower eyelid
            right_eye_left = face_landmarks.landmark[362]  # Left corner
            right_eye_right = face_landmarks.landmark[263]  # Right corner
            
            # Calculate eye aspect ratios
            def calculate_ear(eye_landmarks):
                # Vertical distances
                A = np.sqrt((eye_landmarks[1].x - eye_landmarks[5].x)**2 + 
                           (eye_landmarks[1].y - eye_landmarks[5].y)**2)
                B = np.sqrt((eye_landmarks[2].x - eye_landmarks[4].x)**2 + 
                           (eye_landmarks[2].y - eye_landmarks[4].y)**2)
                # Horizontal distance
                C = np.sqrt((eye_landmarks[0].x - eye_landmarks[3].x)**2 + 
                           (eye_landmarks[0].y - eye_landmarks[3].y)**2)
                # EAR
                ear = (A + B) / (2.0 * C)
                return ear
            
            # Calculate EAR for both eyes
            left_ear = calculate_ear([left_eye_left, left_eye_top, left_eye_right, 
                                    left_eye_right, left_eye_bottom, left_eye_left])
            right_ear = calculate_ear([right_eye_left, right_eye_top, right_eye_right, 
                                     right_eye_right, right_eye_bottom, right_eye_left])
            
            avg_ear = (left_ear + right_ear) / 2.0
            
            # EAR threshold for closed eyes
            ear_threshold = 0.21
            
            if avg_ear < ear_threshold:
                return {"looking_away": True, "confidence": 0.9, "reason": "Eyes closed or looking down"}
            
            # Analyze gaze direction using eye position
            image_height, image_width = image.shape[:2]
            
            # Get eye centers
            left_eye_center_x = (left_eye_left.x + left_eye_right.x) / 2
            left_eye_center_y = (left_eye_top.y + left_eye_bottom.y) / 2
            right_eye_center_x = (right_eye_left.x + right_eye_right.x) / 2
            right_eye_center_y = (right_eye_top.y + right_eye_bottom.y) / 2
            
            # Check if eyes are too close to edges
            eye_y_ratio = (left_eye_center_y + right_eye_center_y) / 2
            
            if eye_y_ratio < 0.25 or eye_y_ratio > 0.75:
                return {"looking_away": True, "confidence": 0.8, "reason": "Looking up or down"}
            
            # Check horizontal gaze
            eye_x_ratio = (left_eye_center_x + right_eye_center_x) / 2
            if eye_x_ratio < 0.2 or eye_x_ratio > 0.8:
                return {"looking_away": True, "confidence": 0.7, "reason": "Looking left or right"}
            
            return {"looking_away": False, "confidence": 0.85, "reason": "Looking at screen"}
            
    except Exception as e:
        print(f"Error in MediaPipe eye gaze analysis: {e}")
        return {"looking_away": True, "confidence": 0.5, "reason": "Error in analysis"}

def detect_face_occlusion_enhanced(image):
    """Enhanced face occlusion detection using MediaPipe"""
    try:
        with mp_face_mesh.FaceMesh(
            static_image_mode=False,
            max_num_faces=1,
            refine_landmarks=True,
            min_detection_confidence=0.5,
            min_tracking_confidence=0.5) as face_mesh:
            
            # Convert BGR to RGB
            rgb_image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
            results = face_mesh.process(rgb_image)
            
            if not results.multi_face_landmarks:
                return {"occluded": True, "confidence": 0.8, "reason": "No face detected"}
            
            face_landmarks = results.multi_face_landmarks[0]
            
            # Check key facial features visibility
            # Nose tip
            nose_tip = face_landmarks.landmark[4]
            # Left eye center
            left_eye_center = face_landmarks.landmark[468]
            # Right eye center
            right_eye_center = face_landmarks.landmark[473]
            # Mouth center
            mouth_center = face_landmarks.landmark[13]
            
            # Check if key points are within reasonable bounds
            key_points = [nose_tip, left_eye_center, right_eye_center, mouth_center]
            
            for point in key_points:
                if point.x < 0.1 or point.x > 0.9 or point.y < 0.1 or point.y > 0.9:
                    return {"occluded": True, "confidence": 0.7, "reason": "Key facial features at edges"}
            
            # Check for hand occlusion using MediaPipe Hands
            with mp_hands.Hands(
                static_image_mode=False,
                max_num_hands=2,
                min_detection_confidence=0.5,
                min_tracking_confidence=0.5) as hands:
                
                hand_results = hands.process(rgb_image)
                
                if hand_results.multi_hand_landmarks:
                    for hand_landmarks in hand_results.multi_hand_landmarks:
                        # Check if hand is near face
                        hand_center = hand_landmarks.landmark[9]  # Middle finger MCP
                        
                        # Calculate distance between hand and face center
                        face_center_x = (left_eye_center.x + right_eye_center.x) / 2
                        face_center_y = (left_eye_center.y + right_eye_center.y) / 2
                        
                        distance = np.sqrt((hand_center.x - face_center_x)**2 + 
                                         (hand_center.y - face_center_y)**2)
                        
                        if distance < 0.3:  # Hand is close to face
                            return {"occluded": True, "confidence": 0.8, "reason": "Hand detected near face"}
            
            return {"occluded": False, "confidence": 0.9, "reason": "Face fully visible"}
            
    except Exception as e:
        print(f"Error in enhanced face occlusion detection: {e}")
        return {"occluded": True, "confidence": 0.5, "reason": "Error in analysis"}

def detect_multiple_faces(image):
    """Detect if multiple faces are present in the image"""
    # Try MediaPipe first, fallback to face_recognition
    mediapipe_result, mediapipe_count = detect_multiple_faces_mediapipe(image)
    if mediapipe_result:
        return mediapipe_result, mediapipe_count
    
    try:
        # Fallback to face_recognition
        rgb_image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        face_locations = face_recognition.face_locations(rgb_image)
        return len(face_locations) > 1, len(face_locations)
    except Exception as e:
        print(f"Error detecting multiple faces: {e}")
        return False, 0

def detect_mobile_device(image):
    """Detect if a mobile device is visible in the image"""
    return detect_mobile_device_enhanced(image)

def analyze_eye_gaze(image):
    """Analyze eye gaze direction and detect if looking away from screen"""
    return analyze_eye_gaze_mediapipe(image)

def detect_face_occlusion(image):
    """Detect if face is partially covered (mask, hand, etc.)"""
    return detect_face_occlusion_enhanced(image)

@app.post("/analyze_emotion/")
async def analyze_emotion(file: UploadFile = File(...)):
    contents = await file.read()
    nparr = np.frombuffer(contents, np.uint8)
    img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
    if img is None:
        return JSONResponse({"error": "Invalid image"}, status_code=400)
    
    try:
        # Analyze emotions
        result = DeepFace.analyze(img, actions=['emotion'], enforce_detection=False)
        
        # Detect cheating behaviors
        multiple_faces, face_count = detect_multiple_faces(img)
        mobile_detected = detect_mobile_device(img)
        eye_gaze = analyze_eye_gaze(img)
        face_occlusion = detect_face_occlusion(img)
        
        # Compile cheating analysis
        cheating_indicators = {
            "multiple_faces": {
                "detected": multiple_faces,
                "face_count": face_count,
                "severity": "high" if multiple_faces else "none"
            },
            "mobile_device": {
                "detected": mobile_detected,
                "severity": "medium" if mobile_detected else "none"
            },
            "eye_gaze": {
                "looking_away": eye_gaze["looking_away"],
                "confidence": eye_gaze["confidence"],
                "reason": eye_gaze["reason"],
                "severity": "medium" if eye_gaze["looking_away"] else "none"
            },
            "face_occlusion": {
                "detected": face_occlusion["occluded"],
                "confidence": face_occlusion["confidence"],
                "reason": face_occlusion["reason"],
                "severity": "low" if face_occlusion["occluded"] else "none"
            }
        }
        
        # Calculate overall cheating risk
        risk_factors = []
        if multiple_faces:
            risk_factors.append("Multiple faces detected")
        if mobile_detected:
            risk_factors.append("Mobile device detected")
        if eye_gaze["looking_away"]:
            risk_factors.append("Looking away from screen")
        if face_occlusion["occluded"]:
            risk_factors.append("Face partially covered")
        
        overall_risk = "high" if len(risk_factors) >= 2 else "medium" if len(risk_factors) == 1 else "low"
        
        return {
            "emotions": result["emotion"],
            "cheating_analysis": cheating_indicators,
            "overall_risk": overall_risk,
            "risk_factors": risk_factors,
            "timestamp": str(np.datetime64('now'))
        }
        
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)

@app.get("/health")
async def health_check():
    return {"status": "healthy", "service": "enhanced-face-emotion-cheating-detection"}