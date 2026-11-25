from nicegui import ui

from army import CATALOG, POINTS_FORMATS, Army

# web version of desktop/mainscreen.ui: chat on the left, army workspace on the right,
# round Build Army button sitting on the divider about one third down.
BUILD_BUTTON_CSS = """
.nicegui-content { padding: 0; gap: 0; }
.app-layout, .panel-content, .message-input {
    background: #303436;
}
.app-layout {
    min-height: 100vh; align-items: stretch; color: #ece8df;
}
.app-panel { gap: 6px; padding: 9px; align-items: stretch; }
.app-panel.locked .q-btn,
.app-panel.locked .q-field { filter: grayscale(1); opacity: 0.4; }
.app-overlay { 
    position: absolute;
    inset: 0;
    background-color: rgba(0, 0, 0, 0.9);
    z-index: 5;
    }
.panel-content {
    width: 100%; flex: 1 1 auto; min-height: 300px;
    border-color: #777b79;
}
.app-panel .q-field__native, .app-panel .q-field__input { color: #ece8df; }
.app-panel .q-field__native::placeholder { color: #bcb9af; opacity: 1; }
.app-panel .q-field__control:before { border-color: #8a8f8f; }
.chat-placeholder { color: #888; padding: 6px; }
.app-status { padding: 2px 9px; font-size: 12px; }
.build-button {
    position: relative; 
    z-index: 10;
    width: 120px; height: 120px; border-radius: 60px !important;
    border: 3px solid #d5b879;
    color: white; font-size: 16px; font-weight: bold; white-space: pre-line;
}
@media (min-width: 768px) {
    .build-button { position: absolute; left: 50%; top: 33%; transform: translate(-50%, -50%); z-index: 10; }
}
"""


def disable_with_opacity(button):
    """Disable a button without fading its appearance."""
    button.disable()
    button.style("opacity: 1 !important")


def set_button_red(button):
    """Override NiceGUI's default button color."""
    button.style('background-color: #420D09 !important; color: white !important')


@ui.page("/")
def index():
    ui.add_css(BUILD_BUTTON_CSS)
    #One army per tab; lost on reload
    army = Army()

    def status(message):
        ui.notify(message, position="bottom", timeout=5000)

    def send_message():
        message = message_input.value.strip()
        if message:
            placeholder.visible = False
            with chat_history:
                ui.chat_message(message, name="You", sent=True)
            message_input.value = ""
            status("AI chat is not connected yet.")

    def start_app():
        overlay.visible = False

        for panel in (chat_panel, army_panel):
            panel.classes(remove="locked")
        for control in (message_input, send_button, add_unit_button):
            control.enable()

        disable_with_opacity(build_button)
        status("Ready to build your army.")

    @ui.refreshable
    def army_list():
        if not army.units:
            ui.label("No units yet. Click Add unit.").classes("chat-placeholder")
        for unit_id, count in army.units.items():
            unit = CATALOG[unit_id]
            with ui.row().classes("w-full items-center no-wrap"):
                ui.label(f"{count} x {unit.name}").classes("flex-1")
                ui.label(f"{unit.points * count} pts")
                ui.button(icon="remove", on_click=lambda unit_id=unit_id: remove_unit(unit_id)) \
                    .props("flat dense round size=sm")
        totals_label.text = f"{army.format_name}  Points: {army.total_points}/{army.points_limit}"

    def add_unit():
        try:
            army.add_unit(unit_select.value, int(count_input.value or 1))
        except ValueError as error:
            status(str(error))
            return
        add_unit_dialog.close()
        army_list.refresh()

    def change_points_limit(event):
        try:
            army.set_points_limit(event.value)
        except ValueError as error:
            status(str(error))
            points_toggle.set_value(army.points_limit)  # snap back to the current format
            return
        army_list.refresh()

    def remove_unit(unit_id):
        army.remove_unit(unit_id)
        army_list.refresh()

    with ui.element("div").classes("relative w-full flex flex-col md:flex-row app-layout"):
        with ui.column().classes("flex-1 min-w-0 app-panel locked") as chat_panel:
            ui.label("Army assistant")
            with ui.scroll_area().classes("panel-content border"):
                chat_history = ui.column().classes("w-full")
                placeholder = ui.label("Chat messages will appear here.").classes("chat-placeholder")
            with ui.row().classes("w-full no-wrap"):
                message_input = ui.input(placeholder="Describe your army...").classes("flex-1 message-input")
                message_input.disable()
                message_input.on("keydown.enter", send_message)
                send_button = ui.button("Send", on_click=send_message)
                set_button_red(send_button)
                send_button.disable()

        build_button = ui.button("Build\nArmy", on_click=start_app) \
            .classes("build-button self-center").props("unelevated")
        set_button_red(build_button)

        with ui.column().classes("flex-1 min-w-0 app-panel locked") as army_panel:
            ui.label("Army workspace")
            points_toggle = ui.toggle({points: f"{points} ({name})" for points, name in POINTS_FORMATS.items()},
                                      value=army.points_limit, on_change=change_points_limit)
            army_area = ui.column().classes("panel-content border p-2")
            add_unit_button = ui.button("Add unit", on_click=lambda: add_unit_dialog.open())
            set_button_red(add_unit_button)
            add_unit_button.disable()
            totals_label = ui.label().style("white-space: pre")
            with army_area:
                army_list()
        overlay = ui.element("div").classes("app-overlay")

    with ui.dialog() as add_unit_dialog, ui.card().classes("min-w-[320px]"):
        ui.label("Add unit").classes("text-lg")
        unit_select = ui.select({unit.id: f"{unit.name} ({unit.faction}, {unit.points} pts)"
                                 for unit in CATALOG.values()},
                                label="Unit", with_input=True).classes("w-full")
        count_input = ui.number("Copies", value=1, min=1, max=6, precision=0).classes("w-full")
        with ui.row().classes("w-full justify-end"):
            ui.button("Cancel", on_click=add_unit_dialog.close).props("flat")
            ui.button("Add", on_click=add_unit)
