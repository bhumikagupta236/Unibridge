# ============================================
# IMPORTS - External libraries we need
# ============================================
import cv2  # OpenCV - for image processing and hand detection
import numpy as np  # NumPy - for numerical operations
import base64  # For encoding/decoding images from browser
import math  # For mathematical calculations (angles, distances)
import re  # For text pattern matching
from collections import deque  # For storing recent gesture history
from pathlib import Path  # For handling file paths
from flask import Flask, render_template, request, jsonify, send_from_directory, session, redirect, url_for, flash  # Web framework
from flask_socketio import SocketIO, emit  # For real-time communication with browser
from werkzeug.security import generate_password_hash, check_password_hash
import database

# ============================================
# APP SETUP - Initialize Flask web server
# ============================================
app = Flask(__name__)  # Create our web application
app.config['SECRET_KEY'] = 'your_very_secret_key_!@#'  # Security key for sessions
socketio = SocketIO(app,
                    cors_allowed_origins="*",
                    async_mode='gevent',
                    logger=True,
                    engineio_logger=True)  # Enable real-time communication

database.init_db()  # Initialize SQLite Database

# Context processor to make username available to all templates
@app.context_processor
def inject_user():
    return dict(current_user=session.get('username'))

# ============================================
# DIRECTORY PATHS - Where our files are stored
# ============================================
BASE_DIR = Path(__file__).resolve().parent  # Get the main project folder
STATIC_ASL_DIR = BASE_DIR / 'static' / 'images' / 'signs' / 'asl'  # ASL sign images folder
LOCAL_ASL_DIR = BASE_DIR / 'asl'  # Alternative local folder for ASL images


# ============================================
# BRAILLE TRANSLATION - Convert between text and Braille
# ============================================
# Dictionary to convert letters/numbers to Braille symbols
BRAILLE_DICT = {
    'A': '⠁', 'B': '⠃', 'C': '⠉', 'D': '⠙', 'E': '⠑', 'F': '⠋', 'G': '⠛', 'H': '⠓',
    'I': '⠊', 'J': '⠚', 'K': '⠅', 'L': '⠇', 'M': '⠍', 'N': '⠝', 'O': '⠕', 'P': '⠏',
    'Q': '⠟', 'R': '⠗', 'S': '⠎', 'T': '⠞', 'U': '⠥', 'V': '⠧', 'W': '⠺', 'X': '⠭',
    'Y': '⠽', 'Z': '⠵', ' ': ' ',
    '1': '⠼⠁', '2': '⠼⠃', '3': '⠼⠉', '4': '⠼⠙', '5': '⠼⠑',
    '6': '⠼⠋', '7': '⠼⠛', '8': '⠼⠓', '9': '⠼⠊', '0': '⠼⠚',
}

# Reverse dictionary to convert Braille symbols back to text
TEXT_DICT = {v: k for k, v in BRAILLE_DICT.items()}

# ============================================
# GESTURE RECOGNITION SETTINGS
# ============================================
# Store the last 5 detected gestures to smooth out recognition
GESTURE_HISTORY = deque(maxlen=5)
# How many times we need to see the same gesture before confirming it
MIN_STABLE_FRAMES = 2

# Hand detection constants (makes code easier to understand)
ROI_START = 50  # Region of interest starting position
ROI_END = 450  # Region of interest ending position
BLUR_SIZE = 35  # Size for smoothing the image
THRESHOLD_VALUE = 127  # Value for separating hand from background
KERNEL_SIZE = 5  # Size for morphological operations
MIN_HAND_AREA = 3000  # Minimum area to consider as a hand
MAX_FINGER_ANGLE = 95  # Maximum angle to count as a finger
MIN_DEPTH = 20  # Minimum depth between fingers
ASPECT_RATIO_THRESHOLD = 1.25  # Ratio to distinguish A from C gesture


# ============================================
# WEB ROUTES - Pages users can visit
# ============================================

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        if not username or not password:
            flash('Username and Password are required')
            return redirect(url_for('register'))
        
        hashed = generate_password_hash(password)
        if database.create_user(username, hashed):
            flash('Registration successful! Please log in.')
            return redirect(url_for('login'))
        else:
            flash('Username already exists.')
            return redirect(url_for('register'))
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        user = database.get_user_by_username(username)
        
        if user and check_password_hash(user['password_hash'], password):
            session['user_id'] = user['id']
            session['username'] = user['username']
            database.log_activity(user['id'], 'Login', 'User successfully logged in.')
            return redirect(url_for('dashboard'))
        else:
            flash('Invalid username or password')
            return redirect(url_for('login'))
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    flash('Logged out successfully.')
    return redirect(url_for('index'))

@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    activities = database.get_user_activity(session['user_id'])
    return render_template('dashboard.html', activities=activities)

def log_user_activity(activity_name, details=''):
    if 'user_id' in session:
        database.log_activity(session['user_id'], activity_name, details)

@app.route('/api/log_activity', methods=['POST'])
def api_log_activity():
    if 'user_id' in session:
        data = request.json
        if data and 'activity' in data and 'details' in data:
            database.log_activity(session['user_id'], data['activity'], data['details'])
            return jsonify({'status': 'success'})
    return jsonify({'status': 'unauthorized'}), 401

@app.route('/clear_history', methods=['POST'])
def clear_history():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    database.clear_user_activity(session['user_id'])
    flash('Activity history cleared successfully!', 'success')
    return redirect(url_for('dashboard'))

@app.route('/')
def index():
    """Home page - Main landing page with all features."""
    return render_template('index.html')

@app.route('/speech')
def speech_page():
    """Speech page - Convert speech to text using microphone."""
    log_user_activity('Opened Speech Tool', 'Viewed the speech to text page')
    return render_template('speech.html')

@app.route('/braille', methods=['GET', 'POST'])
def braille_page():
    """Braille page - Convert between regular text and Braille.
    
    This page accepts form submissions to translate:
    - Text to Braille (text_to_braille)
    - Braille to Text (braille_to_text)
    """
    translation = ""  # Will store the translated result
    original_text = ""  # Will store what user typed

    # Check if user submitted a form
    if request.method == 'POST':
        # OPTION 1: Convert regular text to Braille
        if 'text_to_braille' in request.form:
            text = request.form.get('text', '').upper()  # Get text and make it uppercase
            log_user_activity('Used Braille Tool', f'Converted text to braille: "{text}"')
            original_text = text
            # Convert each character to Braille using our dictionary
            braille_translation = [BRAILLE_DICT.get(char, '') for char in text]
            translation = ' '.join(braille_translation)  # Join with spaces

        # OPTION 2: Convert Braille to regular text
        elif 'braille_to_text' in request.form:
            braille = request.form.get('braille', '')  # Get Braille input
            log_user_activity('Used Braille Tool', f'Converted braille to text: "{braille}"')
            original_text = braille
            
            # Iterate through the string, handling the 2-char number prefix 
            text_translation = []
            i = 0
            while i < len(braille):
                char = braille[i]
                # Check for number prefix '⠼'
                if char == '⠼' and i + 1 < len(braille):
                    symbol = char + braille[i+1]
                    text_translation.append(TEXT_DICT.get(symbol, '?'))
                    i += 2
                else:
                    text_translation.append(TEXT_DICT.get(char, '?'))
                    i += 1
            translation = ''.join(text_translation)  # Join without spaces

    return render_template('braille.html', translation=translation, original_text=original_text)


@app.route('/learn-sign')
def learn_sign_page():
    """Learn Sign Language page - Interactive lessons to learn ASL alphabet."""
    log_user_activity('Learning', 'Started learning sign language')
    return render_template('learn-sign.html')


@app.route('/local-asl/<path:filename>')
def serve_local_asl(filename):
    """Serve ASL images from local folder."""
    return send_from_directory(str(LOCAL_ASL_DIR), filename)

def _letter_from_name(name: str):
    """Extract a letter from a filename.
    
    Examples:
    - 'A.png' returns 'A'
    - 'a.png' returns 'A'
    - 'B (2).png' returns 'B'
    
    Returns None if no valid letter found.
    """
    # Get filename without extension and make it uppercase
    stem = Path(name).stem.upper()
    
    # If it's just a single letter, return it
    if len(stem) == 1 and 'A' <= stem <= 'Z':
        return stem
    
    # If it starts with a letter, extract that letter
    m = re.match(r'^([A-Z])(?![A-Z])', stem)
    return m.group(1) if m else None

@app.route('/api/asl_images')
def api_asl_images():
    """API endpoint - Get all available ASL sign images.
    
    Returns a JSON object mapping letters (A-Z) to their image URLs.
    Checks static folder first, then local folder.
    """
    mapping = {}  # Will store letter -> image URL mapping
    # Supported image formats
    exts = {'.png', '.jpg', '.jpeg', '.gif', '.webp', '.bmp', '.svg'}

    # STEP 1: Check static images folder
    if STATIC_ASL_DIR.exists():
        for p in STATIC_ASL_DIR.iterdir():  # Loop through all files
            # Check if it's a file with a valid image extension
            if p.is_file() and p.suffix.lower() in exts:
                letter = _letter_from_name(p.name)  # Extract letter from filename
                # Add to mapping if we found a letter and don't have it yet
                if letter and letter not in mapping:
                    mapping[letter] = {
                        'url': f"/static/images/signs/asl/{p.name}",
                        'source': 'static'
                    }

    # STEP 2: Check local ASL folder for any missing letters
    if LOCAL_ASL_DIR.exists():
        for p in LOCAL_ASL_DIR.iterdir():
            if p.is_file() and p.suffix.lower() in exts:
                letter = _letter_from_name(p.name)
                # Only add if we don't already have this letter
                if letter and letter not in mapping:
                    mapping[letter] = {
                        'url': f"/local-asl/{p.name}",
                        'source': 'local'
                    }

    return jsonify(mapping)  # Return as JSON

@app.route('/test-svg')
def test_svg_page():
    """Test page for testing SVG image display."""
    return render_template('test-svg.html')

@app.route('/learn-braille')
def learn_braille_page():
    """Learn Braille page - Interactive lessons to learn Braille alphabet."""
    log_user_activity('Learning', 'Started learning braille')
    return render_template('learn-braille.html')


@app.route('/sign-to-text')
def sign_page():
    """Sign to Text page - Use webcam to recognize sign language gestures.
    
    Uses your webcam to detect hand gestures and convert them to text.
    """
    log_user_activity('Used Sign Tool', 'Opened sign to text recognition')
    return render_template('sign.html')


# ============================================
# IMAGE PROCESSING FUNCTIONS
# ============================================

def decode_image(b64_data):
    """Convert a Base64 string from browser into an OpenCV image.
    
    The browser captures video and sends it as Base64 encoded image.
    This function converts it back to an image we can process.
    
    Args:
        b64_data: Base64 encoded string from browser
    
    Returns:
        OpenCV image (numpy array)
    """
    # Step 1: Decode Base64 string to bytes
    img_bytes = base64.b64decode(b64_data)
    
    # Step 2: Convert bytes to numpy array
    np_arr = np.frombuffer(img_bytes, np.uint8)
    
    # Step 3: Decode numpy array to OpenCV image
    img = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)
    return img

def process_frame_opencv(frame):
    """Process a video frame to detect hand gestures.
    
    This function:
    1. Extracts the region of interest (hand area)
    2. Converts to grayscale and applies blur
    3. Detects the hand contour
    4. Counts visible fingers
    5. Returns the detected gesture letter
    
    Args:
        frame: Video frame from webcam (OpenCV image)
    
    Returns:
        String: 'A', 'B', 'C', 'V', or 'W' if gesture detected, None otherwise
    """
    # Get frame dimensions
    rows, cols, _ = frame.shape

    # Extract Region of Interest (ROI) - the area where we look for the hand
    roi = frame[ROI_START:ROI_END, ROI_START:ROI_END]

    # STEP 1: Convert to grayscale (easier to process than color)
    gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
    # Apply blur to reduce noise and smooth the image
    blurred = cv2.GaussianBlur(gray, (BLUR_SIZE, BLUR_SIZE), 0)


    # STEP 2: Apply threshold to separate hand from background
    # This creates a binary image (black and white)
    _, thresh = cv2.threshold(blurred, THRESHOLD_VALUE, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)

    # STEP 3: Clean up the image using morphological operations
    # This fills small holes and smooths the edges
    kernel = np.ones((KERNEL_SIZE, KERNEL_SIZE), np.uint8)
    thresh = cv2.morphologyEx(thresh, cv2.MORPH_CLOSE, kernel, iterations=2)

    # STEP 4: Find contours (outlines) in the image
    contours, _ = cv2.findContours(thresh.copy(), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    # If no contours found, no hand detected
    if not contours:
        return None

    # Get the largest contour (should be the hand)
    hand_contour = max(contours, key=cv2.contourArea)

    # If the contour is too small, it's probably noise, not a hand
    if cv2.contourArea(hand_contour) < MIN_HAND_AREA:
        return None


    def classify_single_blob_as_A_or_C():
        """Determine if a closed fist is gesture A or C.
        
        Gesture C is wider (more horizontal) than A.
        We calculate the width/height ratio to tell them apart.
        """
        # Get bounding box of the hand contour
        x, y, w, h = cv2.boundingRect(hand_contour)
        if h == 0:  # Avoid division by zero
            return None
        
        # Calculate aspect ratio (width divided by height)
        aspect_ratio = float(w) / h
        
        # If wider than threshold, it's C, otherwise it's A
        return 'C' if aspect_ratio > ASPECT_RATIO_THRESHOLD else 'A'


    # STEP 5: Find convex hull (imagine rubber band around the hand)
    hull = cv2.convexHull(hand_contour, returnPoints=False)
    
    # If hull has too few points, treat as closed fist (A or C)
    if len(hull) <= 3:
        return classify_single_blob_as_A_or_C()

    # STEP 6: Find convexity defects (gaps between fingers)
    defects = cv2.convexityDefects(hand_contour, hull)
    
    # If no defects, it's a closed fist (A or C)
    if defects is None or len(defects) == 0:
        return classify_single_blob_as_A_or_C()

    # STEP 7: Count the fingers by analyzing the defects
    finger_count = 0


    # Loop through each defect (gap between fingers)
    for i in range(defects.shape[0]):
        # Get the defect points
        # s = start point, e = end point, f = farthest point, d = depth
        s, e, f, d = defects[i, 0]
        start_point = tuple(hand_contour[s][0])
        end_point = tuple(hand_contour[e][0])
        far_point = tuple(hand_contour[f][0])  # The point between two fingers

        # Calculate distances between points (using Pythagorean theorem)
        # side_a: distance between start and end points
        side_a = math.sqrt((end_point[0] - start_point[0])**2 + (end_point[1] - start_point[1])**2)
        # side_b: distance between far point and start point
        side_b = math.sqrt((far_point[0] - start_point[0])**2 + (far_point[1] - start_point[1])**2)
        # side_c: distance between end point and far point
        side_c = math.sqrt((end_point[0] - far_point[0])**2 + (end_point[1] - far_point[1])**2)

        # Calculate the angle at the far point using cosine rule
        # angle = arccos((b² + c² - a²) / (2bc))
        epsilon = 1e-6  # Small number to avoid division by zero
        denominator = 2 * side_b * side_c + epsilon
        if denominator <= 0:
            continue
        
        cos_angle = (side_b**2 + side_c**2 - side_a**2) / denominator
        cos_angle = max(-1.0, min(1.0, cos_angle))  # Keep in valid range [-1, 1]
        angle_degrees = math.acos(cos_angle) * 180 / math.pi  # Convert to degrees

        # Convert depth from OpenCV units to pixels
        depth_pixels = d / 256.0

        # If angle is sharp enough and deep enough, count it as a finger gap
        if angle_degrees <= MAX_FINGER_ANGLE and depth_pixels > MIN_DEPTH:
            finger_count += 1


    # STEP 8: Convert finger gaps to finger count
    # If we found N gaps, there are N+1 fingers visible
    fingers_visible = finger_count + 1

    # STEP 9: Map finger count to gesture letter
    if fingers_visible >= 4:
        # 4+ fingers = gesture B (open hand)
        return 'B'
    
    elif fingers_visible == 3:
        # 3 fingers = gesture W
        return 'W'
    
    elif fingers_visible == 2:
        # 2 fingers = gesture V (peace sign)
        return 'V'
    
    elif fingers_visible == 1:
        # 1 finger visible = closed fist (could be A or C)
        result = classify_single_blob_as_A_or_C()
        return result

    # If somehow we get here, no gesture recognized
    return None


def smooth_gesture_output(new_gesture):
    """Smooth out gesture recognition by requiring consistency.
    
    We don't want to output a letter if the detection is flickering.
    Only return a gesture if we've seen it multiple times in a row.
    
    Args:
        new_gesture: The gesture detected in the current frame
    
    Returns:
        String: Confirmed gesture letter, or None if not stable yet
    """
    # Add the new gesture to our history (stores last 5 gestures)
    GESTURE_HISTORY.append(new_gesture or '')

    # Count how many times each gesture appears in recent history
    counts = {}
    for gesture in GESTURE_HISTORY:
        if not gesture:  # Skip empty gestures
            continue
        counts[gesture] = counts.get(gesture, 0) + 1

    # If no gestures in history, return None
    if not counts:
        return None

    # Find the most common gesture
    best_gesture, best_count = max(counts.items(), key=lambda kv: kv[1])
    
    # Only return it if we've seen it enough times (MIN_STABLE_FRAMES)
    if best_count >= MIN_STABLE_FRAMES:
        return best_gesture
    
    return None  # Not stable enough yet


# ============================================
# WEBSOCKET HANDLERS - Real-time communication
# ============================================

@socketio.on('video_frame')
def handle_video_frame(data):
    """Handle incoming video frames from the browser webcam.
    
    The browser captures webcam video and sends frames to us.
    We process each frame and send back the detected gesture.
    
    Flow:
    1. Receive Base64 encoded image from browser
    2. Decode it to OpenCV image
    3. Process the image to detect hand gesture
    4. Smooth the detection to avoid flicker
    5. Send result back to browser
    """
    try:
        # STEP 1: Extract the Base64 image data
        # Browser can send data as string or as {'image': string}
        if isinstance(data, str):
            img_b64 = data
        elif isinstance(data, dict) and 'image' in data:
            img_b64 = data['image']
        else:
            print("Unexpected data type received:", type(data))
            emit('recognition_result', {'letter': '', 'status': 'invalid-payload'})
            return

        # STEP 2: Decode Base64 string to image
        frame = decode_image(img_b64)
        if frame is None:
            emit('recognition_result', {'letter': '', 'status': 'decode-failed'})
            return

        # STEP 3: Process the frame to detect gesture
        raw_gesture = process_frame_opencv(frame)

        # STEP 4: Smooth the gesture (require consistency)
        stable_gesture = smooth_gesture_output(raw_gesture)

        # STEP 5: Send result back to browser
        if stable_gesture:
            # We have a stable, confirmed gesture!
            emit('recognition_result', {
                'letter': stable_gesture,
                'status': 'ok'
            })
        elif raw_gesture:
            # Gesture detected but not stable yet
            emit('recognition_result', {
                'letter': '',
                'status': 'unstable'
            })
        else:
            # No gesture detected in this frame
            emit('recognition_result', {
                'letter': '',
                'status': 'no-gesture'
            })

    except Exception as e:
        # If anything goes wrong, log it and send error status
        print(f"Error processing frame: {e}")
        emit('recognition_result', {'letter': '', 'status': 'error'})


# ============================================
# START THE SERVER
# ============================================

if __name__ == '__main__':
    # This code runs when you execute: python app.py
    print("="*50)
    print("UniBridge Server Starting...")
    print("Open your browser and visit: http://127.0.0.1:5000")
    print("Press Ctrl+C to stop the server")
    print("="*50)
    
    # Start the Flask server with SocketIO support
    # debug=True means it will auto-reload when you change code
    socketio.run(app, debug=True)
