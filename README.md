# Safe Agent Verification Chat App

A Flask web application that integrates with a large language model (LLM) via the Ollama API to verify a user’s identity for Safe key recovery. Once verified, the app automatically triggers a multisig owner switch on a Gnosis Safe using the safe‑eth‑py library.


## Table of Contents

- [Overview](#overview)
- [Features](#features)
- [Architecture](#architecture)
- [Prerequisites](#prerequisites)
- [Installation](#installation)
- [Configuration](#configuration)
- [Running the App](#running-the-app)
- [Endpoints](#endpoints)
- [Client-Side Interface](#client-side-interface)
- [Usage Example](#usage-example)
- [Troubleshooting](#troubleshooting)
- [License](#license)



## Overview

The Safe Agent Verification Chat App is designed to simulate a secure verification process for users trying to recover or switch out their Safe key. The application uses a conversation-based interface to interact with the user. It leverages:

- **LLM Integration:** Communicates with an Ollama API endpoint using the `llama3.2-vision:11b` model.
- **Image & Chat Support:** Users can send text and photos; if an image is provided, the agent briefly describes its contents.
- **Automatic Trigger:** Once the agent confirms verification (e.g. a response containing "Verified"), the app automatically triggers an owner switch on a Gnosis Safe.
- **Safe Integration:** Uses the `safe-eth-py` library along with an Ethereum client to build, sign, and execute a multisig transaction that calls the `swapOwner` function on the Safe contract.


## Features

- **Chat Interface:** An interactive chat window where users can type messages and attach images.
- **LLM Verification:** Integrates with the LLM to simulate an identity verification process.
- **Automatic Owner Switch:** Automatically triggers the Safe owner switch once the agent confirms verification.
- **Image Upload:** Downsizes and encodes images for processing.
- **Polished UI:** A modern, clean design with centered elements and subtle shadows.
- **Dual Endpoints:** Includes both a verification-based owner switch endpoint and a direct owner switch endpoint.

## Architecture

- **Backend:** Flask application handling REST endpoints.
- **LLM Integration:** Sends conversation payloads to the Ollama API.
- **Safe Integration:** Utilizes the `safe-eth-py` library and an Ethereum client to interact with a Gnosis Safe contract.
- **Frontend:** A simple HTML/JavaScript interface providing a chat window and an owner switch section.



## Prerequisites

- Python 3.8 or later
- Flask
- Pillow (PIL)
- Requests
- Web3.py (version 6.x)
- safe-eth-py (installed via pip)
- A working RPC endpoint for the Gnosis Chain (e.g., `https://rpc.gnosischain.com`)
- An Ollama API endpoint running locally (or adjust the URL accordingly)
- A configured `private_key.json` file containing the agent’s private key and address.
- A configured `abi.json` file for the Safe contract ABI.


## Installation

1. **Clone the repository:**

   ```bash
   git clone https://github.com/yourusername/safe-agent-verification.git
   cd safe-agent-verification
   ```

2. **Create and activate a virtual environment:**

   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install required packages:**

   ```bash
   pip install -r requirements.txt
   ```

   *(Ensure that `safe-eth-py`, `Flask`, `Pillow`, and `Web3` are listed in your requirements.txt.)*


## Configuration

1. **private_key.json:** Create a JSON file named `private_key.json` in the project root with the following structure:

   ```json
   {
     "private_key": "YOUR_AGENT_PRIVATE_KEY",
     "address": "YOUR_AGENT_ADDRESS"
   }
   ```

2. **abi.json:** Place the ABI of the Safe contract in a file named `abi.json` in the project root.

3. **RPC Endpoint & Model Settings:**  
   - The RPC endpoint is set to `https://rpc.gnosischain.com` in the code. Modify it if needed.
   - The Ollama API URL and model are defined at the top of the code; adjust if required.


## Running the App

Start the Flask server:

```bash
python app.py
```

The app will run in debug mode and be accessible at `http://127.0.0.1:5000/`.

---

## Endpoints

- **GET /**  
  Serves the main HTML page.

- **POST /api/chat**  
  Accepts a JSON payload with a conversation array and returns the agent’s response from the LLM.

- **POST /api/upload_image**  
  Accepts an image file and returns the downsized image in base64 encoding.

- **POST /api/verify_and_switch_owner**  
  Accepts a JSON payload with `conversation` and `new_address`. Checks if any agent message in the conversation contains "verified" and, if so, triggers the owner switch transaction on the Safe contract.

- **POST /api/switch_owner**  
  A direct endpoint to trigger the owner switch without chat verification.


## Client-Side Interface

The HTML page (`static/index.html`) features:
- A chat window for interactive conversation.
- A form to submit text messages (and optionally, images).
- A switch owner section where the user enters the new owner address.  
  When the agent’s response includes "verified," the switch is automatically triggered.

The UI is styled with CSS for a modern, clean appearance.


## Usage Example

1. **Start a Conversation:**  
   The user types messages (and may attach an image) into the chat window. The conversation is sent to the LLM, which responds with verification steps.

2. **Verification Process:**  
   After a few exchanges, if the user provides sufficient information (e.g., a specific phrase or a photo), the agent responds with "Verified." or a message including that term.

3. **Owner Switch Trigger:**  
   Once the agent's response indicates verification, the client-side script automatically calls the `/api/verify_and_switch_owner` endpoint with the full conversation and the new owner address provided.

4. **Transaction Execution:**  
   The server builds and executes a multisig transaction to call `swapOwner` on the Safe contract, and returns a transaction hash which is displayed on the UI.


## Troubleshooting

- **LLM Not Verifying:**  
  If the agent never responds with "verified," adjust the conversation or the prompt in the LLM configuration.

- **Transaction Failures:**  
  Ensure that the agent’s private key and address are correctly set in `private_key.json`, and that the Safe contract’s ABI is correctly provided in `abi.json`.

- **RPC Connection Issues:**  
  Verify the RPC endpoint URL is correct and accessible.

- **Dependencies:**  
  Make sure all required Python packages are installed in your virtual environment.


## License

This project is licensed under the MIT License.


