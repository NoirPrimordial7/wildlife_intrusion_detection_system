# What changed

The original desktop application, trained classifier, YOLO pipeline, danger rules, evidence files, and provider options remain in place.

- Forest-green palette with lime actions, clearer typography, a larger feed, and a confidence meter.
- Inspector tabs for Overview, Evidence, Messages, and Settings. Sidebar links actually navigate to the corresponding tab.
- Playback controls fit a 1120×700 window, display the correct loaded/playing/paused/finished state, and retain SMS/cooldown status.
- Readable detection bookmarks jump to their frame. Preview images resize with the window.
- Guided demo runs an illustrated, scripted elephant intrusion locally. It never sends SMS/calls, sounds an alarm, or adds real evidence/history.
- Video inference runs separately from playback, with one prediction at a time. Stopped or superseded work is discarded. Tk updates use a queue on the main thread.
- Invalid settings show feedback. Duplicate recipient numbers are rejected. Switching sources clears the previous preview.
- Provider credentials can be edited in the app and saved locally. Credential values stay out of Git and the shared ZIP.
- Optional Twilio voice alerts and Test Call, alongside the existing SMS options. Requests share the confirmed-alert cooldown. Provider acceptance is distinct from answered/delivered.
- Snapshot/report actions and notification exports remain available. Reports include voice-call status. JSON saves are atomic, and concurrent notification results are preserved.
- `START.bat` handles first-time setup and subsequent launches. `QUICKSTART.md` gives short copy-and-paste instructions. Tested direct dependency versions are pinned.

## Verification

Verified on Windows with Python 3.12.10:

- 12 automated checks covering launcher retry/cache/verification behavior, notification disabled states, credential persistence, mocked SMS/voice requests and failure handling, concurrent logs, alert confirmation/cooldown, snapshot/report output, real video decoding, playback controls during slow inference, invalid sources, and simulation metadata.
- A desktop integration check covering the 1120×700 layout, sidebar navigation, settings validation/save, provider-credential editor, recipient save, mocked SMS/Call button dispatch, guided threat transitions, playback controls, still-image upload, report export, and shutdown.
- TensorFlow 2.17.1 loads the existing 142-class model; a smoke prediction produces a 142-value result.
- YOLOv8n loads successfully; the real hybrid pipeline correctly reports no animal on a blank frame.

No real phone message or call was sent. End-to-end delivery needs the owner's configured provider account and recipient phone. A physical webcam and macOS/Linux launch were not verified here. The guided demo is a UI walkthrough; it does not measure AI accuracy. Detection accuracy remains limited by the original model and broad YOLO classes.

See [Twilio's call API](https://www.twilio.com/docs/voice/api/call-resource) for voice-call request semantics. YOLO weights in the ZIP come from the [Ultralytics assets release](https://github.com/ultralytics/assets/releases/tag/v8.4.0).

Fresh-PC Windows setup now uses `SETUP.bat`: compatible Python discovery, automatic Python/runtime installation when missing, signed-download fallback, package/model verification, retryable failures, logs, and a desktop shortcut. The prerequisite-check mode and installer branches were verified; a blank Windows installation was not available for end-to-end testing.
