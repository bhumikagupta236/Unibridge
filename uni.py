import cv2
import numpy as np
import base64
import math
import re
from collections import deque
from pathlib import Path
from flask import Flask, render_template, request, jsonify, send_from_directory
from flask_socketio import SocketIO, emit

app = Flask(__name__)

app.config['SECRET_KEY'] = 'your_very_secret_key_!@#'


socketio = SocketIO(app, cors_allowed_origins="*")


BASE_DIR = Path(__file__).resolve().parent

STATIC_ASL_DIR = BASE_DIR / 'static' / 'images' / 'signs' / 'asl'
LOCAL_ASL_DIR = BASE_DIR / 'asl'


BRAILLE_DICT = {
    'A': '⠁', 'B': '⠃', 'C': '⠉', 'D': '⠙', 'E': '⠑', 'F': '⠋', 'G': '⠛', 'H': '⠓',
    'I': '⠊', 'J': '⠚', 'K': '⠅', 'L': '⠇', 'M': '⠍', 'N': '⠝', 'O': '⠕', 'P': '⠏',
    'Q': '⠟', 'R': '⠗', 'S': '⠎', 'T': '⠞', 'U': '⠥', 'V': '⠧', 'W': '⠺', 'X': '⠭',
    'Y': '⠽', 'Z': '⠵', ' ': ' ',
    '1': '⠼⠁', '2': '⠼⠃', '3': '⠼⠉', '4': '⠼⠙', '5': '⠼⠑',
    '6': '⠼⠋', '7': '⠼⠛', '8': '⠼⠓', '9': '⠼⠊', '0': '⠼⠚',
}

TEXT_DICT = {v: k for k, v in BRAILLE_DICT.items()}


GESTURE_HISTORY = deque(maxlen=5)
MIN_STABLE_FRAMES = 2


@app.route('/')
def index():
    """Serves the homepage."""
    return render_template('index.html')

@app.route('/speech')
def speech_page():
    """Serves the Speech-to-Text page."""
    return render_template('speech.html')

@app.route('/braille', methods=['GET', 'POST'])
def braille_page():
    """Serves the Braille translator page and handles form submissions."""
    translation = ""
    original_text = ""

    if request.method == 'POST':
        if 'text_to_braille' in request.form:

            text = request.form.get('text', '').upper()
            original_text = text
            braille_translation = [BRAILLE_DICT.get(char, '') for char in text]
            translation = ' '.join(braille_translation)

        elif 'braille_to_text' in request.form:

            braille = request.form.get('braille', '')
            original_text = braille

            braille_chars = braille.split(' ')
            text_translation = [TEXT_DICT.get(char, '?') for char in braille_chars]
            translation = ''.join(text_translation)

    return render_template('braille.html', translation=translation, original_text=original_text)


@app.route('/learn-sign')
def learn_sign_page():
    """Serves the 'Learn Sign Language' page."""
    return render_template('learn-sign.html')


@app.route('/local-asl/<path:filename>')
def serve_local_asl(filename):
    return send_from_directory(str(LOCAL_ASL_DIR), filename)

def _letter_from_name(name: str):
    """Extract a single A–Z letter from a filename (stem).
    Accepts exact 'A' or names that start with a single letter followed by non-letter.
    """
    stem = Path(name).stem.upper()
    if len(stem) == 1 and 'A' <= stem <= 'Z':
        return stem
    m = re.match(r'^([A-Z])(?![A-Z])', stem)
    return m.group(1) if m else None

@app.route('/api/asl_images')
def api_asl_images():
    """Return mapping of available local ASL images by letter.
    Prefers static/images/asl, then optional ./asl folder.
    """
    mapping = {}
    exts = {'.png', '.jpg', '.jpeg', '.gif', '.webp', '.bmp', '.svg'}


    if STATIC_ASL_DIR.exists():
        for p in STATIC_ASL_DIR.iterdir():
            if p.is_file() and p.suffix.lower() in exts:
                letter = _letter_from_name(p.name)
                if letter and letter not in mapping:
                    mapping[letter] = {
                        'url': f"/static/images/signs/asl/{p.name}",
                        'source': 'static'
                    }

    if LOCAL_ASL_DIR.exists():
        for p in LOCAL_ASL_DIR.iterdir():
            if p.is_file() and p.suffix.lower() in exts:
                letter = _letter_from_name(p.name)
                if letter and letter not in mapping:
                    mapping[letter] = {
                        'url': f"/local-asl/{p.name}",
                        'source': 'local'
                    }

    return jsonify(mapping)

@app.route('/test-svg')
def test_svg_page():
    """Test page for SVG images."""
    return render_template('test-svg.html')

@app.route('/learn-braille')
def learn_braille_page():
    """Serves the 'Learn Braille' page."""
    return render_template('learn-braille.html')


@app.route('/sign-to-text')
def sign_page():
    """
    Serves the Sign-to-Text (upload) page.
    NOTE: This route now serves our *live webcam* page.
    """
    return render_template('sign.html')


def decode_image(b64_data):
    """Convert a Base64-encoded JPEG/PNG string into an OpenCV image.

    The browser sends just the raw Base64 data (no data: URL prefix),
    so we decode that directly here.
    """

    img_bytes = base64.b64decode(b64_data)

    np_arr = np.frombuffer(img_bytes, np.uint8)

    img = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)
    return img

def process_frame_opencv(frame):
    """
    Processes a single video frame with OpenCV to count fingers.
    Returns a recognized gesture ('A', 'B', 'C', 'V', 'W') or None.
    """


    rows, cols, _ = frame.shape

    roi = frame[50:450, 50:450]


    gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
    blurred = cv2.GaussianBlur(gray, (35, 35), 0)


    _, thresh = cv2.threshold(blurred, 127, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)


    kernel = np.ones((5, 5), np.uint8)
    thresh = cv2.morphologyEx(thresh, cv2.MORPH_CLOSE, kernel, iterations=2)


    contours, _ = cv2.findContours(thresh.copy(), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    if not contours:
        return None

    hand_contour = max(contours, key=cv2.contourArea)


    if cv2.contourArea(hand_contour) < 3000:
        return None


    def classify_single_blob_as_A_or_C():
        x, y, w, h = cv2.boundingRect(hand_contour)
        if h == 0:
            return None
        aspect_ratio = float(w) / h

        return 'C' if aspect_ratio > 1.25 else 'A'


    hull = cv2.convexHull(hand_contour, returnPoints=False)
    if len(hull) <= 3:

        return classify_single_blob_as_A_or_C()

    defects = cv2.convexityDefects(hand_contour, hull)
    if defects is None or len(defects) == 0:

        return classify_single_blob_as_A_or_C()

    finger_count = 0


    for i in range(defects.shape[0]):
        s, e, f, d = defects[i, 0]
        start = tuple(hand_contour[s][0])
        end = tuple(hand_contour[e][0])
        far = tuple(hand_contour[f][0])


        a = math.sqrt((end[0] - start[0])**2 + (end[1] - start[1])**2)
        b = math.sqrt((far[0] - start[0])**2 + (far[1] - start[1])**2)
        c = math.sqrt((end[0] - far[0])**2 + (end[1] - far[1])**2)


        epsilon = 1e-6
        denom = 2 * b * c + epsilon
        if denom <= 0:
            continue
        cos_angle = (b**2 + c**2 - a**2) / denom
        cos_angle = max(-1.0, min(1.0, cos_angle))
        angle = math.acos(cos_angle) * 180 / math.pi


        depth = d / 256.0


        if angle <= 95 and depth > 20:
            finger_count += 1


    fingers_visible = finger_count + 1


    if fingers_visible >= 4:

        return 'B'

    if fingers_visible == 3:

        return 'W'

    if fingers_visible == 2:

        return 'V'

    if fingers_visible == 1:


        result = classify_single_blob_as_A_or_C()
        return result


    return None


def smooth_gesture_output(new_gesture):
    """Return a smoothed gesture based on recent frames.

    Only emit a letter when we've seen the same non-empty gesture
    at least MIN_STABLE_FRAMES times in the recent history.
    """

    GESTURE_HISTORY.append(new_gesture or '')


    counts = {}
    for g in GESTURE_HISTORY:
        if not g:
            continue
        counts[g] = counts.get(g, 0) + 1

    if not counts:
        return None


    best_gesture, best_count = max(counts.items(), key=lambda kv: kv[1])
    if best_count >= MIN_STABLE_FRAMES:
        return best_gesture
    return None


@socketio.on('video_frame')
def handle_video_frame(data):
    """Handle a frame from the browser.

    The client sends a raw Base64 string (no header). This handler
    decodes it, runs OpenCV, and emits a simple result back.
    """
    try:

        if isinstance(data, str):
            img_b64 = data
        elif isinstance(data, dict) and 'image' in data:
            img_b64 = data['image']
        else:
            print("video_frame: unexpected payload type", type(data))
            emit('recognition_result', {'letter': '', 'status': 'invalid-payload'})
            return


        frame = decode_image(img_b64)
        if frame is None:
            emit('recognition_result', {'letter': '', 'status': 'decode-failed'})
            return


        raw_gesture = process_frame_opencv(frame)


        stable_gesture = smooth_gesture_output(raw_gesture)


        if stable_gesture:
            emit('recognition_result', {
                'letter': stable_gesture,
                'status': 'ok'
            })
        elif raw_gesture:

            emit('recognition_result', {
                'letter': '',
                'status': 'unstable'
            })
        else:
            emit('recognition_result', {
                'letter': '',
                'status': 'no-gesture'
            })

    except Exception as e:
        print(f"Error processing frame: {e}")
        emit('recognition_result', {'letter': '', 'status': 'error'})


if __name__ == '__main__':


    print("Starting SocketIO server on http://127.0.0.1:5000")
    socketio.run(app, debug=True)
