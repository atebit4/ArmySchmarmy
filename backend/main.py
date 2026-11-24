from pathlib import Path

from fastapi import FastAPI
from nicegui import app as nicegui_app
from nicegui import ui

import pages  # noqa: F401  registers the NiceGUI pages

STATIC_DIR = Path(__file__).with_name("static")

app = FastAPI(title="ArmySchmarmy")


@app.get("/api/health")
def health():
    return {"status": "ok"}


# images, icons, etc. dropped in backend/static/ are served at /static/...
nicegui_app.add_static_files("/static", STATIC_DIR)

# mount NiceGUI last so the /api routes above take priority
ui.run_with(app, title="ArmySchmarmy", show_welcome_message=False)
