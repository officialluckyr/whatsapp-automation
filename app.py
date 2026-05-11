import os
import requests
from flask import Flask, request, jsonify
from dotenv import load_dotenv

# Load environment variables first
load_dotenv()

# Fix for protobuf error on Python 3.14
os.environ['PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION'] = 'python'

import google.generativeai as genai

app = Flask(__name__)

# Environment variables
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
WHATSAPP_ACCESS_TOKEN = os.getenv("WHATSAPP_ACCESS_TOKEN")
WHATSAPP_PHONE_NUMBER_ID = os.getenv("WHATSAPP_PHONE_NUMBER_ID")
VERIFY_TOKEN = os.getenv("VERIFY_TOKEN", "core_memory_secret_token")

# Initialize Gemini AI
genai.configure(api_key=GEMINI_API_KEY)

# Define system instruction for the model
system_instruction = (
    "You are the professional and helpful sales assistant for Core Memory, "
    "a brand selling handmade pipe cleaner floral art and custom accessories. "
    "Answer customer questions briefly (under 50 words). Your ultimate goal is "
    "to generate curiosity and politely guide the customer toward placing an order."
)

# Initialize the Gemini 1.5 Pro model with system instructions
model = genai.GenerativeModel(
    model_name='gemini-2.5-flash',
    system_instruction=system_instruction
)

def send_whatsapp_message(phone_number, text_response):
    """
    Sends a text message back to the user via WhatsApp Cloud API.
    """
    url = f"https://graph.facebook.com/v19.0/{WHATSAPP_PHONE_NUMBER_ID}/messages"
    
    headers = {
        "Authorization": f"Bearer {WHATSAPP_ACCESS_TOKEN}",
        "Content-Type": "application/json"
    }
    
    data = {
        "messaging_product": "whatsapp",
        "to": phone_number,
        "type": "text",
        "text": {
            "body": text_response
        }
    }
    
    try:
        response = requests.post(url, headers=headers, json=data)
        response.raise_for_status()
        print(f"Message sent successfully to {phone_number}")
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"Error sending message: {e}")
        if response.content:
            print(f"Response content: {response.content}")
        return None

@app.route('/webhook', methods=['GET'])
def verify_webhook():
    """
    Handles webhook verification for Meta.
    Expects hub.mode, hub.verify_token, and hub.challenge in the query parameters.
    """
    mode = request.args.get("hub.mode")
    token = request.args.get("hub.verify_token")
    challenge = request.args.get("hub.challenge")

    if mode and token:
        if mode == "subscribe" and token == VERIFY_TOKEN:
            print("WEBHOOK_VERIFIED")
            return challenge, 200
        else:
            return "Verification token mismatch", 403
            
    return "Hello world", 200

@app.route('/webhook', methods=['POST'])
def receive_message():
    """
    Handles incoming WhatsApp messages and status updates.
    """
    body = request.get_json()

    if body:
        # Check if it's a WhatsApp status update (e.g. read/delivered receipt), and ignore it
        if body.get("entry", [{}])[0].get("changes", [{}])[0].get("value", {}).get("statuses"):
            print("Status update received and ignored.")
            return jsonify({"status": "status_update_ignored"}), 200
            
        try:
            # Extract phone number and message text
            message_info = body["entry"][0]["changes"][0]["value"]["messages"][0]
            phone_number = message_info["from"]
            message_text = message_info["text"]["body"]
            
            print(f"Received message from {phone_number}: {message_text}")
            
            # Generate response from Gemini
            response = model.generate_content(message_text)
            ai_reply = response.text
            
            print(f"AI Reply: {ai_reply}")
            
            # Send reply back via WhatsApp
            send_whatsapp_message(phone_number, ai_reply)
            
        except (KeyError, IndexError) as e:
            # Message structure is not as expected (might be an image, location, etc. instead of text)
            print(f"Unsupported message type or parsing error: {e}")
        except Exception as e:
            print(f"An error occurred: {e}")
            
        return jsonify({"status": "success"}), 200
    
    return jsonify({"status": "error"}), 404

if __name__ == '__main__':
    # Run the Flask app on port 5000
    app.run(port=5000, debug=True)