"""Regression tests use temporary files and mocked providers; no real notifications."""
from pathlib import Path
import tempfile
import threading
import time
import unittest
from unittest.mock import MagicMock, patch

import cv2
import numpy as np

from app.core.alert_service import AlertService
from app.core.demo_service import DemoService
from app.core.notification_service import NotificationService
from app.core.report_service import ReportService
from app.core.snapshot_service import SnapshotService
from app.core.video_service import VideoService


class Notifications(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.paths = patch.multiple("app.core.notification_service",
            REGISTERED_USERS_PATH=self.root / "users.json", NOTIFICATION_LOG_PATH=self.root / "notifications.json",
            SMS_CONFIG_PATH=self.root / "sms.json", SMS_CONFIG_EXAMPLE_PATH=self.root / "example.json")
        self.paths.start()
        self.addCleanup(self.paths.stop)
        self.service = NotificationService()
        self.user = {"name": "Test Guard", "phone": "+12025550123", "enabled": True}

    def configure(self):
        self.service.save_sms_config({"enabled": True, "voice_enabled": True,
            "twilio": {"account_sid": "AC-test-secret", "auth_token": "test-token-secret", "from_number": "+12025550124"}})

    def test_disabled_channels_do_not_contact_provider(self):
        with patch("twilio.rest.Client") as client:
            self.assertEqual(self.service.send_test_sms(self.user)["status"], "disabled")
            self.assertEqual(self.service.send_test_call(self.user)["status"], "disabled")
            client.assert_not_called()

    def test_credentials_persist_and_sms_request_uses_them(self):
        self.configure()
        with patch("twilio.rest.Client") as client:
            client.return_value.messages.create.return_value.sid = "SM-test"
            result = self.service.send_test_sms(self.user)
            self.assertEqual(result["message_sid"], "SM-test")
            self.assertEqual(result["status"], "sent")
            client.return_value.messages.create.assert_called_once()
            self.assertEqual(client.return_value.messages.create.call_args.kwargs["to"], self.user["phone"])
        self.service.save_sms_config({"provider": "fast2sms", "fast2sms": {"api_key": "sample-key"}})
        config = self.service.load_sms_config()
        self.assertEqual(config["fast2sms"]["api_key"], "sample-key")
        self.assertEqual(config["twilio"]["auth_token"], "test-token-secret")

    def test_voice_request_is_escaped_and_logged_as_queued(self):
        self.configure()
        with patch("twilio.rest.Client") as client:
            client.return_value.calls.create.return_value.sid = "CA-test"
            client.return_value.calls.create.return_value.status = "queued"
            result = self.service.send_voice_call(self.user, "Tiger & bear <near> the village")
            self.assertEqual((result["status"], result["channel"]), ("queued", "voice"))
            request = client.return_value.calls.create.call_args.kwargs
            self.assertIn("Tiger &amp; bear &lt;near&gt;", request["twiml"])
            self.assertEqual(request["to"], self.user["phone"])

    def test_provider_failures_redact_secrets(self):
        self.configure()
        with patch("twilio.rest.Client") as client:
            client.return_value.calls.create.side_effect = RuntimeError("test-token-secret AC-test-secret +12025550123")
            result = self.service.send_test_call(self.user)
            self.assertEqual(result["status"], "failed")
            self.assertNotIn("test-token-secret", result["error"])
            self.assertNotIn(self.user["phone"], result["error"])

    def test_concurrent_notification_results_are_not_lost(self):
        threads = [threading.Thread(target=self.service.send_test_sms, args=(self.user,)) for _ in range(8)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        self.assertEqual(len(self.service.load_notification_log()), 8)


class AlertWorkflow(unittest.TestCase):
    def test_confirmation_cooldown_snapshot_report_and_both_channels(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            with patch.multiple("app.core.alert_service", ALERT_CONFIG_PATH=root / "config.json", ALERT_EVENTS_PATH=root / "events.json"):
                notifications = MagicMock()
                notifications.send_alert_to_registered_users.return_value = [{"status": "disabled"}]
                notifications.send_alert_calls.return_value = [{"status": "queued", "channel": "voice"}]
                service = AlertService(SnapshotService(root / "snapshots"), notifications)
                service.update_config({"required_repeated_detections": 2, "alert_cooldown_seconds": 120})
                frame = np.zeros((240, 320, 3), dtype=np.uint8)
                elephant = {"label": "Elephant", "confidence": .94}
                self.assertFalse(service.evaluate_detection({"label": "Elephant", "confidence": .2}, frame.copy(), "video")["alert_triggered"])
                self.assertFalse(service.evaluate_detection(elephant, frame.copy(), "video")["alert_triggered"])
                decision = service.evaluate_detection(elephant, frame.copy(), "video")
                self.assertTrue(decision["alert_triggered"])
                event = decision["event"]
                self.assertTrue(Path(event["snapshot_path"]).exists())
                self.assertFalse(event["notification_sent"])
                self.assertEqual(event["call_status"], "queued")
                service.evaluate_detection(elephant, frame.copy(), "video")
                again = service.evaluate_detection(elephant, frame.copy(), "video")
                self.assertFalse(again["alert_triggered"])
                self.assertIn("cooldown", again["reason"])
                notifications.send_alert_to_registered_users.assert_called_once()
                notifications.send_alert_calls.assert_called_once()
                report = ReportService(service.events_path, root / "reports").export_alert_report()
                self.assertIn("Elephant", Path(report).read_text())
                self.assertEqual(len(service.load_events()), 1)


class Playback(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.video = str(Path(self.temp.name) / "fixture.avi")
        writer = cv2.VideoWriter(self.video, cv2.VideoWriter_fourcc(*"MJPG"), 20, (160, 120))
        if not writer.isOpened():
            self.fail("Test codec MJPG is unavailable")
        for index in range(60):
            writer.write(np.full((120, 160, 3), index, dtype=np.uint8))
        writer.release()

    def test_video_controls_remain_responsive_during_slow_inference(self):
        started, release = threading.Event(), threading.Event()
        def slow(_frame):
            started.set()
            release.wait(3)
            return {"label": "Elephant", "confidence": .94}
        detector = MagicMock(predict_frame=slow)
        frames, predictions, progress, errors = [], [], [], []
        service = VideoService(detector, lambda frame, metadata: frames.append(metadata),
                               lambda *args: predictions.append(args), progress.append, errors.append)
        self.assertTrue(service.open_video(self.video))
        self.assertEqual(progress[-1]["state"], "loaded")
        service.start()
        self.assertTrue(started.wait(2))
        time.sleep(.2)
        self.assertGreater(service.current_frame_index, 1)
        service.pause()
        time.sleep(.08)
        index = service.current_frame_index
        time.sleep(.08)
        self.assertEqual(service.current_frame_index, index)
        service.seek_percent(50)
        self.assertAlmostEqual(service.current_frame_index, 29, delta=1)
        self.assertEqual(progress[-1]["state"], "paused")
        service.resume()
        service.set_speed(2)
        before = time.monotonic()
        service.stop(wait=True, reset=False)
        self.assertLess(time.monotonic() - before, .5)
        release.set()
        service._prediction_thread.join(2)
        self.assertFalse(predictions, "Stopped inference must not deliver old detections")
        self.assertFalse(errors)

    def test_invalid_video_clears_previous_source(self):
        service = VideoService(MagicMock(), lambda *args: None, lambda *args: None, lambda *args: None, lambda *args: None)
        self.assertTrue(service.open_video(self.video))
        self.assertFalse(service.open_video(str(Path(self.temp.name) / "missing.mp4")))
        self.assertIsNone(service.video_path)

    def test_demo_has_explicit_simulation_metadata_and_seekable_events(self):
        results, frames, progress = [], [], []
        service = DemoService(lambda *args: frames.append(args), lambda *args: results.append(args), progress.append)
        service.seek_seconds(6)
        self.assertTrue(results[-1][2]["simulation"])
        self.assertEqual(results[-1][0]["label"], "Elephant")
        service.seek_percent(99)
        self.assertEqual(results[-1][0]["label"], "No animal detected")
        self.assertEqual(frames[-1][0].shape, (480, 800, 3))


if __name__ == "__main__":
    unittest.main()
