# Model Limitations

## Current Model Setup

The `.h5` model is an image classifier. It identifies the likely animal species in an image crop, but it does not find locations by itself.

YOLOv8 provides bounding boxes for animal-like objects. The classifier then predicts the species from each crop.

## Accuracy Limits

- YOLO pretrained COCO models only detect broad classes such as `bear`, `elephant`, `cow`, or `dog`.
- Species such as tiger, leopard, hyena, crocodile, snake, boar, rhinoceros, and hippopotamus may depend heavily on the classifier crop result.
- Poor lighting, motion blur, small animals, partial animals, and night footage can reduce accuracy.
- Testing on the current sample videos showed classifier confusion labels such as `ragno`, `gallina`, `Owl`, `Jaguar`, and non-English `elefante`.
- The app normalizes known raw labels for display, for example `ragno` becomes `Spider` and `elefante` becomes `Elephant`.
- During the demo, non-dangerous classifier labels that would be confusing can defer to the YOLO label in the UI. The raw classifier label is still preserved in JSON and Markdown reports.
- Current normalization map includes `elefante -> Elephant`, `cane -> Dog`, `cavallo -> Horse`, `gallina -> Chicken`, `gatto -> Cat`, `mucca -> Cow`, `pecora -> Sheep`, `ragno -> Spider`, `farfalla -> Butterfly`, and `scoiattolo -> Squirrel`.
- Bounding boxes are from YOLO, while species names can come from the classifier. If YOLO detects a broad animal class incorrectly, the box can still be useful even when the label needs manual interpretation.
- The evidence panel intentionally shows the latest confirmed alert, not necessarily the current detection.
- A wrong classifier label on a YOLO crop can create a wrong danger decision, so the chosen demo clip still needs manual review in the UI before presentation.
- This project is a demo-ready prototype, not a certified safety system.

## Future Upgrade

Train or fine-tune a YOLO detection model on local wildlife classes. That would provide exact species-specific bounding boxes instead of broad animal boxes plus classifier crops.
