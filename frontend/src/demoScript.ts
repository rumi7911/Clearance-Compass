// Mirrors backend/data/parse_script.py's MAX_SCRIPT_CHARS -- kept as a
// single small constant (not the script text itself) so the client-side
// character counter matches the server's real limit. The actual demo
// script text is fetched from GET /api/demo-script rather than duplicated
// here, so it can never drift from backend/data/scenes.py.
export const MAX_SCRIPT_CHARS = 6000
