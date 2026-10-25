# Futures Radar cloud server

A small Linux server in Germany that does background jobs GitHub can't: Binance, Bybit and the SEC refuse GitHub's US servers.
The app itself stays on GitHub Pages (free). The server only makes outgoing requests and publishes results to data branches
in this repo, the same way the GitHub jobs do.

**Status: not created. Waiting for the owner's approval of the cost below (ROADMAP rule 5). Only the owner can approve.**

## Cost (for the owner's approval)

| | |
|---|---|
| What | DigitalOcean "Basic" Droplet, 1 GB memory, 1 vCPU, 25 GB disk, Frankfurt (FRA1), Ubuntu 24.04 |
| Price | **US$6.00 a month, about US$72 a year.** Public IP address and 1,000 GB of outgoing data included (we use well under 1 GB a month). |
| Billing | Charged by the second, never more than $6.00 in a month. Billed monthly to the card on the account. |
| Optional extras | Backups (+$1.20/mo) are **not needed**: everything important is in GitHub. Nothing else is required. |
| To stop paying | Delete the Droplet in the DigitalOcean dashboard. Billing stops the same moment. A switched-off Droplet still costs money, so delete it, don't just power it off. |
| If a bill isn't paid | DigitalOcean suspends the account and later removes the server. The app keeps working on GitHub Pages; only the server jobs stop. |
| Price check | https://www.digitalocean.com/pricing/droplets (read 25 Oct 2026). |

Why DigitalOcean and not Hetzner (cheaper on paper): in October 2026 Hetzner's cheapest plans showed as unavailable and new accounts could be capped
or asked for ID or an advance payment, so its real cheapest option was about €6.49/month with more sign-up friction.
Germany is used because Binance blocks servers in the US, Canada, the Netherlands and Malaysia. Bybit blocks some cloud companies'
address ranges whatever the country, so the first job is a reach check: if Bybit refuses this server, delete it the same day (a few cents) and try another provider.

## What it does

- Every 5 minutes it updates its read-only copy of this repo and runs the jobs in `server/jobs/` that are due.
  Each job's first lines say how often it runs (`# every: 60` = once an hour).
- First job: `reach.sh` checks once an hour that Binance, Bybit, Gate and the SEC answer from the server, and publishes
  `server-status.json` to the `server-data` branch (also a heartbeat: if it stops updating, the server is down).
- Next jobs (built by later runs, each one only after the reach check shows the source works): the public track record on Binance,
  Bybit and Gate; the nightly backtest on all three exchanges; the stock Picks data from the SEC; push alerts.

## Safety

- **No incoming connections at all**: the firewall blocks everything coming in and the remote-login service (SSH) is switched off.
  The server only reaches out (to exchanges and GitHub).
- Jobs run as a user with no admin rights, in a locked-down service. Security updates install daily; the server restarts at
  4am Jamaica time when an update needs it.
- No passwords, API keys or exchange accounts are on it. Its only key is a GitHub **deploy key** made on the server, for this one
  repository. The private half never leaves the server; if the server is lost, delete the key on GitHub and it's useless.
- The deploy key can write to the repo. `publish.sh` only writes data branches and refuses `main`, but a fully broken-into server could
  still push to `main`. Optional extra protection the owner can switch on (a repo setting only he should change): GitHub → repo
  Settings → Rules → New branch ruleset for `main` → "Restrict updates" with only himself allowed. Claude never changes repo settings.
- Whatever is pushed to `main` runs on the server (as the no-rights user). That is the same trust as the website itself.

## Owner steps (about 15 minutes, works on a phone)

1. Go to **digitalocean.com** → Sign up (email, then a payment card; this is where the $6/month starts once a Droplet exists).
2. **Create → Droplets.**
   - Region: **Frankfurt** (FRA1).
   - Image: **Ubuntu 24.04 (LTS)**.
   - Size: **Basic → Regular → $6/mo** (1 GB / 1 CPU).
   - Authentication: **Password**. Make a long one and keep it in your password manager (only needed for the emergency console).
   - **Advanced options → Add initialization scripts**: paste the whole of `server/cloud-init.yaml` from this repo.
   - Hostname: `futures-radar`. Leave backups and other add-ons off. **Create Droplet.**
3. Wait about 5 minutes, then open the Droplet → **Access → Launch Recovery Console**. The screen shows a line starting
   `ssh-ed25519 …futures-radar server`. Copy that whole line (or take a screenshot and send it to Claude to type out).
4. On GitHub: **876lab/futures-radar → Settings → Deploy keys → Add deploy key.** Title `cloud server`, paste the line,
   tick **Allow write access**, **Add key**.
5. Done. Within 10 minutes a `server-data` branch appears with the first reach check. Tell Claude, who checks it and builds the next job.

To remove everything: delete the Droplet in DigitalOcean, and delete the deploy key on GitHub.
