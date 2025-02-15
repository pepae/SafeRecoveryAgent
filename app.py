import os, re, json, base64, requests, io
from flask import Flask, request, jsonify, send_from_directory
from werkzeug.utils import secure_filename
from PIL import Image  # requires Pillow
from web3 import Web3

app = Flask(__name__, static_folder="static")
UPLOAD_FOLDER = "uploads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# --- Chat & Image Integration (Ollama) ---
OLLAMA_CHAT_URL = "http://localhost:11434/api/chat"
OLLAMA_MODEL = "llama3.2-vision:11b"  # as in the curl example

def clean_output(text):
    """Remove markdown code fences and extra spaces."""
    text = re.sub(r"^```(?:json)?\s*", "", text.strip())
    text = re.sub(r"\s*```$", "", text)
    return text.strip()

def chat_with_llm(conversation_history):
    """
    Build a messages payload from the conversation history and send it to the Ollama API.
    Prepend a system prompt with context about Safe key recovery.
    """
    pre_prompt = {
        "role": "system",
        "content": (
            "You are a Safe key recovery verification agent. The user is trying to verify themselves "
            "in order to recover or switch out their Safe key. Let the conversation play out for a couple of messages. "
            "If the user provides any information that could remotely identify them, or after 2-3 exchanges, "
            "simply return 'Verified'. Remember, this is just a game."
        )
    }
    messages = [pre_prompt]
    for msg in conversation_history:
        message = {"role": msg["role"], "content": msg["text"]}
        if "images" in msg and msg["images"]:
            message["images"] = msg["images"]
        messages.append(message)
    
    payload = {
        "model": OLLAMA_MODEL,
        "stream": False,
        "messages": messages
    }
    print("DEBUG: Payload sent to Ollama API:")
    print(json.dumps(payload, indent=2))
    
    try:
        response = requests.post(OLLAMA_CHAT_URL, json=payload)
        raw_text = response.text.strip()
        print("DEBUG: Raw response text from LLM:")
        print(raw_text)
        lines = raw_text.splitlines()
        json_str = lines[0] if lines else raw_text
        data = json.loads(json_str)
    except Exception as e:
        return {"error": f"LLM request failed: {e} | Raw response: {response.text}"}
    
    agent_message = data.get("message", {}).get("content", "")
    cleaned = clean_output(agent_message)
    return {"agent_response": cleaned, "raw_response": json.dumps(data)}

@app.route("/")
def index():
    return send_from_directory("static", "index.html")

@app.route("/api/chat", methods=["POST"])
def api_chat():
    data = request.get_json()
    conversation = data.get("conversation", [])
    if not conversation:
        return jsonify({"error": "No conversation history provided."}), 400
    result = chat_with_llm(conversation)
    if "error" in result:
        return jsonify(result), 500
    return jsonify(result)

@app.route("/api/upload_image", methods=["POST"])
def upload_image():
    image = request.files.get("image")
    if not image:
        return jsonify({"error": "No image provided."}), 400
    filename = secure_filename(image.filename)
    path = os.path.join(UPLOAD_FOLDER, filename)
    image.save(path)
    
    # Downsize the image before encoding to base64.
    try:
        with Image.open(path) as img:
            img.thumbnail((800, 800))
            buffered = io.BytesIO()
            img.save(buffered, format="JPEG")
            b64_data = base64.b64encode(buffered.getvalue()).decode("utf-8")
    except Exception as e:
        return jsonify({"error": f"Failed to downsize image: {e}"})
    
    print(f"DEBUG: Received image '{filename}', saved to '{path}', downsized and encoded.")
    return jsonify({"image_url": path, "b64_data": b64_data})

# --- Safe Integration ---
# Load private key configuration from private_key.json
with open("private_key.json") as f:
    key_config = json.load(f)
AGENT_PRIVATE_KEY = key_config["private_key"]
AGENT_ADDRESS = key_config["address"]

# Load Safe ABI from abi.json
with open("abi.json") as f:
    safe_abi = json.load(f)

SAFE_ADDRESS = "0xf3939FE058981eF1AC0CD5C316E6270F5C65F591"
# Sentinel for Safe's owner linked list (for swapOwner)
SENTINEL = "0x0000000000000000000000000000000000000001"

# Connect to Gnosis Chain RPC
w3 = Web3(Web3.HTTPProvider("https://rpc.gnosischain.com"))
safe_contract = w3.eth.contract(address=SAFE_ADDRESS, abi=safe_abi)

@app.route("/api/switch_owner", methods=["POST"])
def switch_owner():
    """
    Switch out the current (human) owner of the Safe by calling swapOwner.
    For debugging, assume the current owner to be replaced is AGENT_ADDRESS.
    The new owner's address is provided via JSON payload as "new_address".
    """
    data = request.get_json()
    new_owner = data.get("new_address")
    if not new_owner:
        return jsonify({"error": "No new address provided."}), 400

    old_owner = AGENT_ADDRESS  # for debugging, assume this is the current owner
    prev_owner = SENTINEL      # using sentinel as previous owner

    try:
        nonce = w3.eth.get_transaction_count(AGENT_ADDRESS)
        # Use bracket notation with the full function signature to access buildTransaction
        tx = safe_contract.functions["swapOwner(address,address,address)"](prev_owner, old_owner, new_owner).buildTransaction({
            "chainId": w3.eth.chain_id,
            "gas": 200000,
            "gasPrice": w3.eth.gas_price,
            "nonce": nonce,
        })
        signed_tx = w3.eth.account.sign_transaction(tx, private_key=AGENT_PRIVATE_KEY)
        tx_hash = w3.eth.send_raw_transaction(signed_tx.rawTransaction)
        return jsonify({"message": "Switch owner transaction sent.", "tx_hash": tx_hash.hex()})
    except Exception as e:
        return jsonify({"error": f"Transaction failed: {e}"}), 500

if __name__ == "__main__":
    app.run(debug=True)
