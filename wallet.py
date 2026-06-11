import os
import json
from web3 import Web3
from eth_account import Account
from cryptography.fernet import Fernet
from config import CELO_RPC, PLATFORM_PRIVATE_KEY, PLATFORM_WALLET, CUSD_CONTRACT

w3 = Web3(Web3.HTTPProvider(CELO_RPC))

# cUSD ABI - minimal ERC20
CUSD_ABI = json.loads('[{"constant":true,"inputs":[{"name":"_owner","type":"address"}],"name":"balanceOf","outputs":[{"name":"balance","type":"uint256"}],"type":"function"},{"constant":false,"inputs":[{"name":"_to","type":"address"},{"name":"_value","type":"uint256"}],"name":"transfer","outputs":[{"name":"","type":"bool"}],"type":"function"},{"constant":true,"inputs":[{"name":"_owner","type":"address"},{"name":"_spender","type":"address"}],"name":"allowance","outputs":[{"name":"","type":"uint256"}],"type":"function"}]')

cusd = w3.eth.contract(address=Web3.to_checksum_address(CUSD_CONTRACT), abi=CUSD_ABI)

# Encryption key for private keys - stored in env
FERNET_KEY = os.getenv("FERNET_KEY")
if not FERNET_KEY:
    # Generate one if not set - operator must save this
    FERNET_KEY = Fernet.generate_key().decode()
    print(f"[WALLET] Generated FERNET_KEY - save this to .env: {FERNET_KEY}")

fernet = Fernet(FERNET_KEY.encode() if isinstance(FERNET_KEY, str) else FERNET_KEY)


def generate_wallet():
    """Generate a new Celo wallet. Returns (address, encrypted_private_key)."""
    account = Account.create()
    encrypted = fernet.encrypt(account.key.hex().encode()).decode()
    return account.address, encrypted


def decrypt_key(encrypted_key: str) -> str:
    return fernet.decrypt(encrypted_key.encode()).decode()


def get_cusd_balance(address: str) -> float:
    """Returns cUSD balance as float."""
    try:
        checksum = Web3.to_checksum_address(address)
        raw = cusd.functions.balanceOf(checksum).call()
        return raw / 1e18
    except Exception as e:
        print(f"[WALLET] Balance error for {address}: {e}")
        return 0.0


def get_celo_balance(address: str) -> float:
    """Returns CELO balance as float (for gas checks)."""
    try:
        checksum = Web3.to_checksum_address(address)
        raw = w3.eth.get_balance(checksum)
        return raw / 1e18
    except Exception as e:
        print(f"[WALLET] CELO balance error: {e}")
        return 0.0


def transfer_cusd(from_encrypted_key: str, to_address: str, amount_cusd: float) -> str:
    """
    Transfer cUSD from a custodial wallet.
    Gas is paid in CELO from the same wallet (Celo allows gas in CELO).
    Returns tx_hash or raises.
    """
    private_key = decrypt_key(from_encrypted_key)
    account = Account.from_key(private_key)
    from_address = account.address

    to_checksum = Web3.to_checksum_address(to_address)
    amount_wei = int(amount_cusd * 1e18)

    nonce = w3.eth.get_transaction_count(from_address)
    gas_price = w3.eth.gas_price

    tx = cusd.functions.transfer(to_checksum, amount_wei).build_transaction({
        "from": from_address,
        "nonce": nonce,
        "gas": 100000,
        "gasPrice": gas_price,
        "chainId": 42220,  # Celo mainnet
    })

    signed = account.sign_transaction(tx)
    tx_hash = w3.eth.send_raw_transaction(signed.raw_transaction)
    receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=60)

    if receipt.status != 1:
        raise Exception(f"Transaction failed: {tx_hash.hex()}")

    return tx_hash.hex()


def platform_transfer_cusd(to_address: str, amount_cusd: float) -> str:
    """Transfer from platform wallet (for payouts funded by collected contributions)."""
    if not PLATFORM_PRIVATE_KEY:
        raise Exception("PLATFORM_PRIVATE_KEY not set")
    account = Account.from_key(PLATFORM_PRIVATE_KEY)
    to_checksum = Web3.to_checksum_address(to_address)
    amount_wei = int(amount_cusd * 1e18)

    nonce = w3.eth.get_transaction_count(account.address)
    gas_price = w3.eth.gas_price

    tx = cusd.functions.transfer(to_checksum, amount_wei).build_transaction({
        "from": account.address,
        "nonce": nonce,
        "gas": 100000,
        "gasPrice": gas_price,
        "chainId": 42220,
    })

    signed = account.sign_transaction(tx)
    tx_hash = w3.eth.send_raw_transaction(signed.raw_transaction)
    receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=60)

    if receipt.status != 1:
        raise Exception(f"Platform transfer failed: {tx_hash.hex()}")

    return tx_hash.hex()


def fund_wallet_for_gas(to_address: str, celo_amount: float = 0.01) -> str:
    """Send a small amount of CELO from platform wallet to cover gas for a member wallet."""
    if not PLATFORM_PRIVATE_KEY:
        raise Exception("PLATFORM_PRIVATE_KEY not set")
    account = Account.from_key(PLATFORM_PRIVATE_KEY)
    to_checksum = Web3.to_checksum_address(to_address)
    amount_wei = int(celo_amount * 1e18)

    nonce = w3.eth.get_transaction_count(account.address)
    gas_price = w3.eth.gas_price

    tx = {
        "from": account.address,
        "to": to_checksum,
        "value": amount_wei,
        "nonce": nonce,
        "gas": 21000,
        "gasPrice": gas_price,
        "chainId": 42220,
    }

    signed = account.sign_transaction(tx)
    tx_hash = w3.eth.send_raw_transaction(signed.raw_transaction)
    w3.eth.wait_for_transaction_receipt(tx_hash, timeout=60)
    return tx_hash.hex()


def is_connected() -> bool:
    try:
        return w3.is_connected()
    except:
        return False
