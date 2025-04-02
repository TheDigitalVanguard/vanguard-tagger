import boto3
import json
import tensorflow as tf
import tensorflow_hub as hub
import numpy as np
import joblib
import os
import tempfile
from io import BytesIO
import time

# AWS S3 bucket details
BUCKET_NAME = "the-digital-vanguard"
MODEL_S3_KEY = "models/tagging_model.h5"
MLB_S3_KEY = "models/mlb_labels.pkl"

# S3 client
s3 = boto3.client("s3")

def load_model_from_s3(bucket, key):
    """Download a TensorFlow model from S3 into a temporary file and load it."""
    model_stream = BytesIO()
    s3.download_fileobj(bucket, key, model_stream)
    model_stream.seek(0)  # Reset stream position

    with tempfile.NamedTemporaryFile(delete=False, suffix=".h5") as temp_model_file:
        temp_model_file.write(model_stream.read())
        temp_model_path = temp_model_file.name
    
    model = tf.keras.models.load_model(temp_model_path)
    os.unlink(temp_model_path)  # Clean up temporary file
    return model

def load_labels_from_s3(bucket, key):
    """Load a pickle file directly from S3 into memory."""
    label_stream = BytesIO()
    s3.download_fileobj(bucket, key, label_stream)
    label_stream.seek(0)
    return joblib.load(label_stream)

# Load models from S3 into memory
embed = hub.load("https://tfhub.dev/google/universal-sentence-encoder/4")
tagging_model = load_model_from_s3(BUCKET_NAME, MODEL_S3_KEY)
mlb = load_labels_from_s3(BUCKET_NAME, MLB_S3_KEY)

def get_embedding(text):
    """Generate an embedding for the input text."""
    return embed([text]).numpy()[0]

def generate_tags(text):
    """Generate tags based on model predictions."""
    input_embedding = get_embedding(text)
    predictions = tagging_model.predict(np.array([input_embedding]))[0]
    
    # Set threshold to filter tags
    threshold = 0.001
    tag_indexes = np.where(predictions > threshold)[0]
    return [mlb.classes_[i] for i in tag_indexes]

def lambda_handler(event, context):
    """AWS Lambda function handler."""
    try:
        body = json.loads(event["body"])
        text = body.get("text", "")
        
        if not text:
            return {"statusCode": 400, "body": json.dumps({"error": "Text input required"})}
        
        tags = generate_tags(text)
        return {
            "statusCode": 200,
            "body": json.dumps({"tags": tags})
        }
    
    except Exception as e:
        return {"statusCode": 500, "body": json.dumps({"error": str(e)})}
