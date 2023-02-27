import os

# noinspection DuplicatedCode
model_dir = os.getenv('SM_MODEL_DIR', '/opt/ml/model')
model_path = os.path.join(model_dir, 'model.pth')

# put your training code here
print(f"Training the model {model_path}...")

with open(model_path, 'wb') as f:
    f.write(b"42")  # save your model here

print("model-accuracy=1.000")

print("Training complete.")
