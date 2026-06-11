# Circlo — Onchain Rotating Savings Circle Agent

> A trustless, agent-powered savings circle built on Celo. Groups commit cUSD every cycle. The agent enforces deadlines, applies penalties onchain, and rotates the full pool to one member per round — no human intermediary needed.

Built for the [Celo Onchain Agents Hackathon](https://celoplatform.notion.site/Onchain-Agents-Hackathon) · May–June 2026

---

## The Problem

Rotating savings circles (known as ajo in Nigeria, susu in Ghana, chama in Kenya, tanda in Latin America) move billions of dollars globally every year through informal trust networks. They work — until they don't. A missed contribution, a coordinator who disappears with the pool, no transparency on who paid — these failures are common and the losses are real.

Existing fintech solutions either require centralized custodians or don't serve the communities that need this most.

## The Solution

Circlo is a Telegram-native onchain agent that runs savings circles entirely on Celo. Every contribution, penalty, and payout is a real cUSD transaction on Celo mainnet. The agent enforces the rules automatically — no human coordinator holds funds or makes decisions.

**How it works:**

1. A group admin creates a circle in a Telegram group — sets the contribution amount, member count, and cycle length
2. Each member runs `/join` and receives a custodial Celo wallet
3. Members fund their wallets with cUSD and run `/pay` each round
4. The agent monitors deadlines and sends reminders at 24h, 6h, and 1h before cutoff
5. At the deadline, penalties are automatically deducted from wallets of late members
6. The full pool rotates to the next member in the payout order — settled onchain instantly

---

## Features

- **Fully onchain settlement** — every transaction on Celo mainnet, verifiable on CeloScan
- **Automatic deadline enforcement** — no human discretion, no exceptions
- **Onchain penalty execution** — late contributors lose a % automatically
- **Rotating payout order** — randomized at circle start, transparent to all members
- **Custodial wallets per member** — generated and managed by the agent
- **Live transparency dashboard** — public web dashboard showing all circles, contributions, and payouts in real time
- **ERC-8004 registered** — Circlo is a registered onchain agent with a verifiable identity on 8004scan

---

## Tech Stack

- **Chain:** Celo Mainnet (Ethereum L2)
- **Token:** cUSD (Celo Dollar stablecoin)
- **Interface:** Telegram Bot (python-telegram-bot)
- **Backend:** Python, Flask
- **Database:** SQLite
- **Infrastructure:** AWS Lightsail (Ubuntu)
- **Dashboard:** Static HTML served via nginx with HTTPS
- **Agent Standard:** ERC-8004 onchain agent registry

---

## Commands

| Command | Description |
|---|---|
| `/start` | Introduction and command list |
| `/create <name> <amount> <members> [days]` | Create a new savings circle (admin) |
| `/join` | Join the circle and get your wallet |
| `/pay` | Submit your contribution for the current round |
| `/status` | See who has paid and who owes this round |
| `/balance` | Check your wallet cUSD balance |
| `/wallet` | Get your deposit address |
| `/history` | View past rounds and payouts |
| `/payout` | Manually trigger payout (admin only) |

---

## Architecture

```
Telegram Bot (bot.py)
    ├── pool.py         — contribution logic, penalty execution, payout rotation
    ├── wallet.py       — custodial Celo wallet generation and cUSD transfers
    ├── scheduler.py    — background loop: reminders and deadline enforcement
    ├── db.py           — SQLite schema and queries
    └── api.py          — Flask API serving the public dashboard

Dashboard (dashboard/index.html)
    └── Served via nginx on circlo.opsfera.xyz

ERC-8004 Registration (erc8004.py)
    └── Registers Circlo as a verified onchain agent on Celo
```

---

## Deployment

See [DEPLOY.md](./DEPLOY.md) for full step-by-step deployment instructions.

---

## Live

- **Bot:** [@CircloBot](https://t.me/CircloBot)
- **Dashboard:** [circlo.zndra.xyz](https://circlo.zndra.xyz/)
- **Agent Registry:** [8004scan.io](https://8004scan.io)
- **Built by:** [Opsfera](https://opsfera.xyz) · [@Mani_chukk](https://x.com/Mani_chukk)
