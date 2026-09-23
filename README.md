# ThreatShield — Python/MySQL version

This is the same ThreatShield interface and front-end logic as the supplied PHP version. The PHP files are replaced by Python/Flask routes; the HTML/CSS/JavaScript UI and API calculations are kept equivalent.

## Run on Windows

1. Install Python 3.10+.
2. Open Command Prompt in this folder.
3. Run:
   `python -m venv venv`
4. Activate:
   `venv\Scripts\activate`
5. Run:
   `pip install -r requirements.txt`
6. Start:
   `python app.py`
7. Open `http://127.0.0.1:5000/`

## MySQL

The supplied `database.sql` is retained unchanged. Import it into MySQL/phpMyAdmin if you want the same database schema available for future persistence. The original PHP prototype's active scan endpoints did not write to the database, so this Python conversion likewise does not add database behavior that was not present in the original.

## Important

- The interface is not redesigned.
- The existing `assets/style.css` and `assets/app.js` are retained.
- `/api.php` is intentionally provided as a Flask POST route so the existing JavaScript can keep calling `api.php` without changing the UI or request flow.
- Evidence file fields are accepted by the browser form exactly as before; the original PHP endpoint did not process the uploaded file, so the Python endpoint also preserves that behavior.
