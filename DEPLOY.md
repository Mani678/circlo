# Circlo — Deployment Guide

## 1. Upload project to server

From your local machine (PowerShell), run one at a time:
```
scp -r circlo ubuntu@15.237.188.130:~/circlo
```

## 2. SSH into server
```
ssh ubuntu@15.237.188.130
```

## 3. Install dependencies
```
cd ~/circlo
pip install -r requirements.txt --break-system-packages
```

## 4. Generate platform wallet
```
python scripts/keygen.py
```
Copy the output and add to your .env file:
```
nano .env
```
Fill in:
- PLATFORM_WALLET=
- PLATFORM_PRIVATE_KEY=
- FERNET_KEY=

## 5. Fund platform wallet
- Send at least 1 CELO to PLATFORM_WALLET for gas
- Send at least 10 cUSD to PLATFORM_WALLET as initial liquidity buffer
- Get CELO from: https://app.uniswap.org or any CEX that supports Celo

## 6. Test Celo connection
```
python -c "from wallet import is_connected; print('Connected:', is_connected())"
```

## 7. Setup nginx

Copy nginx config:
```
sudo cp circlo.nginx.conf /etc/nginx/sites-available/circlo
sudo ln -s /etc/nginx/sites-available/circlo /etc/nginx/sites-enabled/
```

Point your domain circlo.opsfera.xyz to 15.237.188.130 (DNS A record).

Then get SSL cert:
```
sudo certbot --nginx -d circlo.opsfera.xyz
```

Test and reload nginx:
```
sudo nginx -t
sudo systemctl reload nginx
```

## 8. Start the bot
```
screen -S circlo
cd ~/circlo
python bot.py
```
Detach: Ctrl+A then D

## 9. Start the API server
```
screen -S circlo-api
cd ~/circlo
python api.py
```
Detach: Ctrl+A then D

## 10. Register on ERC-8004
First get the real registry address from https://8004scan.io/docs then update erc8004.py:
```
python erc8004.py
```
Save the agentId and transaction hash — you need this for your hackathon tweet and submission.

## 11. Hackathon registration tweet
Post this on X from @Mani_chukk:

```
I am building for the @CeloDevs Agent Hackathon 🟡

Working on: Circlo — The onchain rotating savings circle agent

Groups commit cUSD every cycle. Agent enforces deadlines, applies penalties onchain, rotates the pool to one member per round. No trust needed.

Registered onchain → [ERC-8004 link from 8004scan]

#CeloAgents @Celo
```

## 12. Join hackathon Telegram
https://t.me/celodevs (join with your new account for updates)

## 13. Submit project (opens June 8)
https://build.celo.org (submit via Celo Builders platform)

---

## Screen session management
```
screen -ls                    # list sessions
screen -r circlo              # reattach bot
screen -r circlo-api          # reattach API
```

## Useful commands
```
# Check bot logs
screen -r circlo

# Check API health
curl http://localhost:5050/api/health

# Check dashboard data
curl http://localhost:5050/api/dashboard

# View DB
sqlite3 circlo.db ".tables"
sqlite3 circlo.db "SELECT * FROM circles;"
```
