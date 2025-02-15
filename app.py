import os, re, json, base64, requests, io, sys, subprocess
from flask import Flask, request, jsonify, send_from_directory
from werkzeug.utils import secure_filename
from PIL import Image  # requires Pillow
from web3 import Web3
from eth_utils import decode_hex, to_bytes
# --- Import safe-eth-py ---
from safe_eth.safe import Safe
from safe_eth.eth import EthereumClient

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
    pre_prompt = {
        "role": "system",
        "content": (
            "You are a Safe key recovery verification agent. The user is trying to verify themselves, "
            "convincing you with text or photos in order to recover or switch out their Safe key. "
            "If the user sends a photo, briefly describe its contents. Let the conversation play out for a couple of messages. "
            "If the user provides anything remotely identifying, simply return 'Verified'. "
            "Remember, this is just a game."
        )
    }
    messages = [pre_prompt]
    for msg in conversation_history:
        # Use msg["text"] if available; otherwise fallback to msg["content"]
        content = msg.get("text") or msg.get("content", "")
        messages.append({
            "role": msg["role"],
            "content": content
        })
    
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
        return {"error": f"LLM request failed: {e}"}
    
    agent_message = data.get("message", {}).get("content", "")
    cleaned = clean_output(agent_message)
    return {"agent_response": cleaned}

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
with open("private_key.json") as f:
    key_config = json.load(f)
AGENT_PRIVATE_KEY = key_config["private_key"]
AGENT_ADDRESS = key_config["address"]

with open("abi.json") as f:
    safe_abi = json.load(f)

SAFE_ADDRESS = "0xf3939FE058981eF1AC0CD5C316E6270F5C65F591"
SENTINEL_OWNERS = "0x0000000000000000000000000000000000000001"

# For reference only:
w3 = Web3(Web3.HTTPProvider("https://rpc.gnosischain.com"))
safe_contract = w3.eth.contract(address=SAFE_ADDRESS, abi=safe_abi)

@app.route("/api/verify_and_switch_owner", methods=["POST"])
def verify_and_switch_owner():
    data = request.get_json()
    conversation = data.get("conversation", [])
    new_address = data.get("new_address")
    if not conversation:
        return jsonify({"error": "No conversation history provided."}), 400
    if not new_address:
        return jsonify({"error": "No new address provided."}), 400

    # Check if any agent message in the conversation (using "text" or "content") contains "verified"
    verified_flag = any(
        msg.get("role", "").lower() == "agent" and 
        "verified" in (msg.get("text") or msg.get("content", "")).lower()
        for msg in conversation
    )
    print("DEBUG: Verified flag:", verified_flag)
    
    if verified_flag:
        try:
            new_owner = Web3.to_checksum_address(new_address)
        except Exception as e:
            return jsonify({"error": f"Invalid new address: {e}"}), 400

        try:
            ethereum_client = EthereumClient("https://rpc.gnosischain.com")
            safe_instance = Safe(SAFE_ADDRESS, ethereum_client)
            owners = safe_instance.retrieve_owners()
            owners = [Web3.to_checksum_address(o) for o in owners]
            if len(owners) < 2:
                return jsonify({"error": "Safe must have at least 2 owners."}), 400

            agent_addr = Web3.to_checksum_address(AGENT_ADDRESS)
            if agent_addr not in owners:
                return jsonify({"error": "Agent is not an owner."}), 400

            human_owner = next((o for o in owners if o != agent_addr), None)
            if not human_owner:
                return jsonify({"error": "Human owner not found."}), 400
            if new_owner in owners:
                return jsonify({"error": "New owner is already an owner."}), 400

            idx = owners.index(human_owner)
            prev_owner = Web3.to_checksum_address(SENTINEL_OWNERS) if idx == 0 else owners[idx - 1]

            swap_owner_data = safe_instance.contract.functions.swapOwner(
                prev_owner, human_owner, new_owner
            )._encode_transaction_data()

            safe_tx = safe_instance.build_multisig_tx(
                to=SAFE_ADDRESS,
                value=0,
                data=Web3.to_bytes(hexstr=swap_owner_data),
                operation=0,
                safe_tx_gas=0,
                base_gas=0,
                gas_price=0,
                gas_token=Web3.to_checksum_address("0x0000000000000000000000000000000000000000"),
                refund_receiver=Web3.to_checksum_address("0x0000000000000000000000000000000000000000")
            )

            safe_tx.sign(AGENT_PRIVATE_KEY)
            tx_hash, _ = safe_tx.execute(tx_sender_private_key=AGENT_PRIVATE_KEY)
            return jsonify({
                "message": "Verified and transaction submitted.",
                "tx_hash": Web3.to_hex(tx_hash)
            })
        except Exception as e:
            return jsonify({"error": f"Transaction failed: {e}"}), 500
    else:
        return jsonify({
            "message": "Verification not complete.",
            "agent_response": "No agent message indicating verification was found."
        })

# Original direct switch endpoint remains.
@app.route("/api/switch_owner", methods=["POST"])
def switch_owner_route():
    data = request.get_json()
    raw_new_owner = data.get("new_address")
    if not raw_new_owner:
        return jsonify({"error": "No new address provided."}), 400

    try:
        new_owner = Web3.to_checksum_address(raw_new_owner)
    except Exception as e:
        return jsonify({"error": f"Invalid new address: {e}"}), 400

    try:
        ethereum_client = EthereumClient("https://rpc.gnosischain.com")
        safe_instance = Safe(SAFE_ADDRESS, ethereum_client)
        owners = safe_instance.retrieve_owners()
        owners = [Web3.to_checksum_address(o) for o in owners]
        if len(owners) < 2:
            return jsonify({"error": "Safe must have at least 2 owners."}), 400

        agent_addr = Web3.to_checksum_address(AGENT_ADDRESS)
        if agent_addr not in owners:
            return jsonify({"error": "Agent is not an owner."}), 400

        human_owner = next((o for o in owners if o != agent_addr), None)
        if not human_owner:
            return jsonify({"error": "Human owner not found."}), 400
        if new_owner in owners:
            return jsonify({"error": "New owner is already an owner."}), 400

        idx = owners.index(human_owner)
        prev_owner = Web3.to_checksum_address(SENTINEL_OWNERS) if idx == 0 else owners[idx - 1]

        swap_owner_data = safe_instance.contract.functions.swapOwner(
            prev_owner, human_owner, new_owner
        )._encode_transaction_data()

        safe_tx = safe_instance.build_multisig_tx(
            to=SAFE_ADDRESS,
            value=0,
            data=Web3.to_bytes(hexstr=swap_owner_data),
            operation=0,
            safe_tx_gas=0,
            base_gas=0,
            gas_price=0,
            gas_token=Web3.to_checksum_address("0x0000000000000000000000000000000000000000"),
            refund_receiver=Web3.to_checksum_address("0x0000000000000000000000000000000000000000")
        )

        safe_tx.sign(AGENT_PRIVATE_KEY)
        tx_hash, _ = safe_tx.execute(tx_sender_private_key=AGENT_PRIVATE_KEY)
        return jsonify({
            "message": "Transaction submitted.",
            "tx_hash": Web3.to_hex(tx_hash)
        })
    except Exception as e:
        return jsonify({"error": f"Transaction failed: {e}"}), 500

if __name__ == "__main__":
    app.run(debug=True)
