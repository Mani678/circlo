"""
Register Circlo as an ERC-8004 agent on Celo mainnet.
Run once after deployment: python erc8004.py

ERC-8004 Agent Registry on Celo: https://8004scan.io
"""

import json
import sys
from web3 import Web3
from eth_account import Account
from config import CELO_RPC, PLATFORM_PRIVATE_KEY, PLATFORM_WALLET, DASHBOARD_URL

w3 = Web3(Web3.HTTPProvider(CELO_RPC))

# ERC-8004 Agent Registry contract on Celo mainnet
# Source: https://8004scan.io / https://github.com/ethereum/EIPs/pull/8004
AGENT_REGISTRY_ADDRESS = "0x1234567890123456789012345678901234567890"  # UPDATE with real address

AGENT_REGISTRY_ABI = [
    {
        "inputs": [
            {"internalType": "string", "name": "name", "type": "string"},
            {"internalType": "string", "name": "description", "type": "string"},
            {"internalType": "string", "name": "endpoint", "type": "string"},
            {"internalType": "string", "name": "category", "type": "string"},
        ],
        "name": "registerAgent",
        "outputs": [{"internalType": "uint256", "name": "agentId", "type": "uint256"}],
        "stateMutability": "nonpayable",
        "type": "function",
    },
    {
        "inputs": [{"internalType": "address", "name": "operator", "type": "address"}],
        "name": "getAgentByOperator",
        "outputs": [
            {"internalType": "uint256", "name": "agentId", "type": "uint256"},
            {"internalType": "string", "name": "name", "type": "string"},
        ],
        "stateMutability": "view",
        "type": "function",
    },
]


def register():
    if not PLATFORM_PRIVATE_KEY:
        print("[ERC8004] ERROR: PLATFORM_PRIVATE_KEY not set in .env")
        sys.exit(1)

    account = Account.from_key(PLATFORM_PRIVATE_KEY)
    print(f"[ERC8004] Registering from wallet: {account.address}")

    if not w3.is_connected():
        print("[ERC8004] ERROR: Cannot connect to Celo RPC")
        sys.exit(1)

    registry = w3.eth.contract(
        address=Web3.to_checksum_address(AGENT_REGISTRY_ADDRESS),
        abi=AGENT_REGISTRY_ABI
    )

    agent_name = "Circlo"
    agent_description = (
        "Circlo is an onchain rotating savings circle agent on Celo. "
        "Groups of members commit cUSD contributions each cycle. "
        "The agent enforces deadlines, applies penalties automatically, "
        "and rotates the pool to one member per round — trustless, transparent, global."
    )
    agent_endpoint = DASHBOARD_URL
    agent_category = "payments"

    nonce = w3.eth.get_transaction_count(account.address)
    gas_price = w3.eth.gas_price

    tx = registry.functions.registerAgent(
        agent_name,
        agent_description,
        agent_endpoint,
        agent_category,
    ).build_transaction({
        "from": account.address,
        "nonce": nonce,
        "gas": 300000,
        "gasPrice": gas_price,
        "chainId": 42220,
    })

    signed = account.sign_transaction(tx)
    tx_hash = w3.eth.send_raw_transaction(signed.raw_transaction)
    print(f"[ERC8004] Registration tx sent: {tx_hash.hex()}")

    receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=60)
    if receipt.status == 1:
        print(f"[ERC8004] ✅ Registered successfully!")
        print(f"[ERC8004] TX: https://celoscan.io/tx/{tx_hash.hex()}")
        print(f"[ERC8004] View agent: https://8004scan.io")
    else:
        print(f"[ERC8004] ❌ Registration failed.")

    return tx_hash.hex()


if __name__ == "__main__":
    register()
