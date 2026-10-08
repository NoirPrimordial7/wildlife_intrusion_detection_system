"""Exercise real Tk controls with temporary data and mocked dialogs/providers."""
from pathlib import Path
import sys
import tempfile
import time
from unittest.mock import patch
import cv2
import numpy as np
import customtkinter as ctk

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from app.ui.theme import apply_theme
from app.ui.dashboard import Dashboard
from app.core.report_service import ReportService


def pump(app, duration=.15):
    end = time.monotonic() + duration
    while time.monotonic() < end:
        app.update()
        time.sleep(.01)


def main():
    apply_theme()
    with tempfile.TemporaryDirectory() as temp:
        folder = Path(temp)
        with patch.multiple("app.core.notification_service", REGISTERED_USERS_PATH=folder / "users.json",
                            NOTIFICATION_LOG_PATH=folder / "notifications.json", SMS_CONFIG_PATH=folder / "sms.json",
                            SMS_CONFIG_EXAMPLE_PATH=folder / "example.json"), \
             patch.multiple("app.core.alert_service", ALERT_CONFIG_PATH=folder / "config.json", ALERT_EVENTS_PATH=folder / "events.json"), \
             patch("app.ui.dashboard.messagebox.showinfo") as info, \
             patch("app.ui.dashboard.messagebox.showerror") as error:
            app = Dashboard()
            callback_errors = []
            app.report_callback_exception = lambda *args: callback_errors.append(args)
            try:
                app.geometry("1120x700")
                pump(app)
                app.sidebar.buttons["settings"].invoke()
                pump(app)
                assert app.inspector.get() == "Settings"
                settings = app.settings_panel
                settings.repeat_entry.delete(0, "end")
                settings.repeat_entry.insert(0, "abc")
                settings._save()
                assert error.called, "Invalid settings must show feedback"
                error.reset_mock()
                settings.repeat_entry.delete(0, "end")
                settings.repeat_entry.insert(0, "2")
                settings._save()
                assert app.alert_service.config["required_repeated_detections"] == 2
                settings.new_name_entry.insert(0, "Test Guard")
                settings.new_phone_entry.insert(0, "+12025550123")
                settings._add_user_from_inputs()
                settings._save_registered_users()
                assert any(user["name"] == "Test Guard" for user in app.notification_service.load_registered_users())
                settings._edit_credentials()
                pump(app)
                popup = next(child for child in settings.winfo_children() if isinstance(child, ctk.CTkToplevel))
                entries = [child for child in popup.winfo_children() if isinstance(child, ctk.CTkEntry)]
                for entry, value in zip(entries, ("AC-test", "dummy-token", "+12025550124")):
                    entry.delete(0, "end")
                    entry.insert(0, value)
                next(child for child in popup.winfo_children() if isinstance(child, ctk.CTkButton)).invoke()
                assert app.notification_service.load_sms_config()["twilio"]["auth_token"] == "dummy-token"
                app.save_sms_config({"enabled": True, "voice_enabled": True})
                test_index = next(i for i, user in enumerate(settings.registered_users) if user["name"] == "Test Guard")
                with patch.object(app.notification_service, "send_test_sms", return_value={"status": "sent"}) as sms, \
                     patch.object(app.notification_service, "send_test_call", return_value={"status": "queued", "channel": "voice"}) as call:
                    settings._test_user_sms(test_index)
                    settings._test_user_call(test_index)
                    pump(app, .3)
                    sms.assert_called_once()
                    call.assert_called_once()
                app.sidebar.buttons["quick_demo"].invoke()
                pump(app, .3)
                app.camera_panel.buttons["pause"].invoke()
                pump(app)
                assert app.demo_service._paused
                app.camera_panel._on_timeline_change(55)
                pump(app)
                assert app.threat_panel.threat_value.cget("text") == "DANGER"
                assert app.camera_panel.source_label.cget("text") == "SIMULATION"
                assert not app.alert_service.load_events(), "Simulation must not create real alerts"
                assert not app.notification_service.load_notification_log(), "Simulation must not contact phones"
                for panel in (app.sidebar, app.camera_panel, app.inspector):
                    assert panel.winfo_x() + panel.winfo_width() <= app.winfo_width() + 2, "Panel extends outside window"
                for button in app.camera_panel.buttons.values():
                    assert button.winfo_rootx() + button.winfo_width() <= app.camera_panel.winfo_rootx() + app.camera_panel.winfo_width(), "Playback button is clipped"
                app.camera_panel._on_speed_change("2x")
                assert app.demo_service.speed == 2
                app.camera_panel._on_interval_change("Every 8 frames")
                assert app.demo_service.interval_label == "Every 8 frames"
                app.camera_panel.buttons["resume"].invoke()
                pump(app)
                assert not app.demo_service._paused
                app.camera_panel.buttons["stop"].invoke()
                pump(app)
                assert not app.demo_service._running
                app.camera_panel.buttons["restart"].invoke()
                pump(app)
                assert app.demo_service._running
                app.stop_monitoring()
                pump(app)
                assert app.camera_panel.source_label.cget("text") == "NO SOURCE"
                assert app.camera_panel._last_frame is None
                # Analyze a real decoded image using a predictable harmless detector result.
                image = folder / "fixture.png"
                cv2.imwrite(str(image), np.zeros((240, 320, 3), dtype=np.uint8))
                with patch("app.ui.dashboard.filedialog.askopenfilename", return_value=str(image)), \
                     patch.object(app.detector_service, "predict_frame", return_value={"label": "No animal detected", "confidence": 0, "detections": []}):
                    app.sidebar.buttons["upload_image"].invoke()
                    pump(app, .4)
                    assert app.camera_panel.source_label.cget("text") == "STILL IMAGE"
                    assert "Image analyzed" == app.camera_panel.monitoring_label.cget("text")
                app.report_service = ReportService(app.alert_service.events_path, folder / "reports")
                app.sidebar.buttons["export_report"].invoke()
                assert list((folder / "reports").glob("*.md"))
                app.sidebar.buttons["evidence"].invoke()
                assert app.inspector.get() == "Evidence"
                app.sidebar.buttons["notifications"].invoke()
                assert app.inspector.get() == "Messages"
                assert not callback_errors, callback_errors
                assert not error.called, error.call_args
                print("PASS: desktop startup, 1120x700 layout, settings navigation/validation/save, recipient save, demo threat transitions, pause/resume/stop/restart/seek/speed/interval, image upload, report export, inspector navigation, simulation isolation, clean shutdown")
            finally:
                app._on_close()


if __name__ == "__main__":
    main()
