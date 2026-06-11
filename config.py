import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
CELO_RPC = os.getenv("CELO_RPC", "https://forno.celo.org")
PLATFORM_PRIVATE_KEY = os.getenv("PLATFORM_PRIVATE_KEY")
PLATFORM_WALLET = os.getenv("PLATFORM_WALLET")
CUSD_CONTRACT = os.getenv("CUSD_CONTRACT", "0x765DE816845861e75A25fCA122bb6898B8B1282a")
ERC8004_REGISTRY = os.getenv("ERC8004_REGISTRY")
DASHBOARD_URL = os.getenv("DASHBOARD_URL", "https://circlo.opsfera.xyz")
DB_PATH = os.getenv("DB_PATH", "./circlo.db")

# Platform fee: 1% of each contribution goes to platform wallet
PLATFORM_FEE_PCT = 0.01

# Penalty: 10% of contribution amount for missing deadline
PENALTY_PCT = 0.10

# Reminder hours before deadline
REMINDER_HOURS = [24, 6, 1]
