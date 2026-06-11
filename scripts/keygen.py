"""
Generate the Circlo platform wallet.
Run once: python scripts/keygen.py
Save the output to your .env file.
"""

from eth_account import Account
from cryptography.fernet import Fernet


def generate():
    # Platform wallet (receives fees, holds pool, executes payouts)
    account = Account.create()
    print("\n=== CIRCLO PLATFORM WALLET ===")
    print(f"Address:     {account.address}")
    print(f"Private Key: {account.key.hex()}")

    # Fernet key for encrypting member wallets
    fernet_key = Fernet.generate_key().decode()
    print(f"\n=== FERNET ENCRYPTION KEY ===")
    print(f"FERNET_KEY:  {fernet_key}")

    print("\n=== ADD TO .env ===")
    print(f"PLATFORM_WALLET={account.address}")
    print(f"PLATFORM_PRIVATE_KEY={account.key.hex()}")
    print(f"FERNET_KEY={fernet_key}")
    print("\n⚠️  NEVER share your private key or fernet key. Back them up securely.")
    print("⚠️  Fund the platform wallet with CELO (for gas) and some cUSD before going live.")


if __name__ == "__main__":
    generate()
