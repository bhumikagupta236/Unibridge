# AGENTS.md

This file provides guidance to WARP (warp.dev) when working with code in this repository.

## Running the Application

**Development server** (auto-reloads on code changes):
```bash
python uni.py
```
Visit http://127.0.0.1:5000

**Production server** (mirrors the Render deployment):
```bash
gunicorn --worker-class eventlet -w 1 uni:app
```

**Install dependencies** (use the virtual environment at `venv/` or `.venv/`):
```bash
pip install -r requirements.txt
```

There is no test suite and no linter/formatter configuration in this repository.

## Architecture Overview

The entire backend is a **single-file Flask application** (`uni.py`) that combines web routes, a Socket.IO WebSocket server, computer vision logic, and Braille translation. `database.py` is a thin SQLite helper.

### Request / Communication Flows

**Sign language recognition** (the most complex feature):
1. `sign.html` captures webcam frames via JavaScript and emits them as Base64 strings over Socket.IO (`video_frame` event).
2. `handle_video_frame()` in `uni.py` decodes the Base64 image, runs `process_frame_opencv()` (contour detection → convex hull → convexity defects → finger count → letter), then passes the result through `smooth_gesture_output()` (a rolling `deque` of the last 5 frames requiring `MIN_STABLE_FRAMES=2` consistent readings) before emitting `recognition_result` back.
3. Recognized gestures are limited to **A, B, C, V, W** only.

**Braille translation** is entirely server-side. The `BRAILLE_DICT` / `TEXT_DICT` in `uni.py` handle bidirectional conversion. Numbers use a two-character prefix `⠼` + digit cell.

**Speech** is 100% client-side using the browser's Web Speech API — the server only serves the page.

**ASL learning module** (`/learn-sign`): The frontend calls `/api/asl_images`, which scans `static/images/signs/asl/` (then the fallback `asl/` directory) and returns a JSON map of letter → image URL. Images are matched by filename using `_letter_from_name()`.

**Braille / Sign lesson data** is stored as static JSON files consumed directly by the frontend:
- `static/data/braille_lessons.json`
- `static/data/sign_lessons.json`

### Authentication & Sessions

- Flask cookie-based sessions store `user_id` and `username`.
- Passwords are hashed with Werkzeug's `generate_password_hash` / `check_password_hash`.
- Every feature page access and tool use is logged to the `activity_log` SQLite table via `log_user_activity()` or the `/api/log_activity` JSON endpoint.
- `inject_user()` is a context processor that makes `current_user` available in every Jinja2 template.

### Deployment Constraints

- **Exactly one worker** (`-w 1`) is required with the `eventlet` worker class. Multiple workers would break Socket.IO session state.
- The `SECRET_KEY` in `uni.py` is hardcoded — replace it with an environment variable before any production deployment.
- The SQLite database file (`unibridge.db`) is created automatically on first run by `database.init_db()`, which is called at module load time.
