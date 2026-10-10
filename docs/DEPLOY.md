# 🌍 Putting the Assistant Online

This guide publishes the chatbot as a **public website** that anyone can open, and that people can **install on their phone like an app**.

**Recommended host: [Render](https://render.com) free tier.** The app was slimmed down to fit it: embeddings run as ONNX (no PyTorch), so the server uses about **400 MB of RAM** (measured: 283 MB at start, ~440 MB after several questions) against Render's free 512 MB.

> Hosting offers change often. In mid-2026 Hugging Face started requiring a paid plan for Docker Spaces, which is why this guide moved to Render. Check the current free-tier terms when you sign up.

When you are done you will have:

- a public link such as `https://disability-schemes-assistant.onrender.com`
- an **"Install app"** button (Android, Chrome, Edge) and **Add to Home Screen** (iPhone)
- automatic updates: Render rebuilds on every push to GitHub, including the monthly scraper's commits

---

## 1. Put the code on GitHub

Render deploys from your GitHub repository, so all changes must be committed and pushed to `main` first.

## 2. Create the service on Render

1. Sign up at <https://render.com> using **Sign in with GitHub**. At the time of writing the free tier does not ask for a card, but confirm on the signup page.
2. In the dashboard choose **New → Blueprint**, and pick the `disability-schemes-chatbot` repository.
3. Render reads [`render.yaml`](../render.yaml) and shows one free web service in the **Singapore** region (the closest to India).
4. It asks for **`GROQ_API_KEY`**: paste your Groq key (the same one as in `.env`). It is stored by Render, never in git.
5. Click **Apply**.

## 3. Wait for the build, then share

The first build takes **about 5–10 minutes** (it installs the libraries and bakes in the two small search models). Watch the **Logs** tab. When the service shows **Live**, open its `.onrender.com` link and ask a question.

Share the link anywhere: WhatsApp, a QR code on a poster, your project report.

## 4. Installing it on a phone

- **Android (Chrome):** open the link and tap **Install app** at the top, or ⋮ menu → **Add to Home screen**.
- **iPhone (Safari):** open the link, tap **Share** → **Add to Home Screen**.

It then opens full-screen with its own icon. Chats stay on the phone.

---

## ⚠️ What the free tier means for users

**Sleeping.** A free Render service sleeps after about 15 minutes without visitors. The next visitor waits roughly a minute while it wakes up and loads its models; after that it is fast. Render's free allowance (750 instance-hours a month at the time of writing) is enough for one service running all month, so a free uptime monitor that opens `/api/health` every 10 minutes can keep it awake. Check Render's current terms before relying on that.

**Groq's free tier is the real capacity limit.** Each question uses about 4–5 AI calls. On the free tier a few people at once can hit Groq's per-minute limit, and users then see *"The assistant is getting too many questions right now"*. For real public use, upgrade the Groq account to the pay-as-you-go **Developer** plan (roughly a fraction of a rupee per question for `gpt-oss-20b`; check <https://console.groq.com/settings/billing>).

**Built-in protection.** `server/guard.py` limits each visitor to 20 questions per 10 minutes and caps message, upload (5 MB) and voice-recording sizes, so one person or bot cannot use up the shared quota.

**It says what it is.** The home screen states that this is an independent project, not a government website, and that answers should be confirmed on the official portal.

---

## Other ways to host it

All of these use the same [`Dockerfile`](../Dockerfile); set `GROQ_API_KEY` on the host.

| Option | Cost | Good for | Notes |
|---|---|---|---|
| **Render free** (above) | Free | Public link, low traffic | Sleeps when idle; 512 MB RAM |
| **Azure for Students** | Free $100 credit a year, no card | Always-on service | Needs a university email. Use Azure Container Apps or App Service with the Dockerfile. |
| **Your own PC + Cloudflare Tunnel** | Free | Project demo / evaluation day | Run the server as usual, then `cloudflared tunnel --url http://localhost:8000` gives a public `trycloudflare.com` link. The PC must stay on. |
| **Hugging Face Space (Docker)** | PRO plan, about $9/month | If you already have PRO | `python scripts/deploy_space.py <user>/<space>` uploads everything; add `GROQ_API_KEY` as a Space secret. |
| **Render paid / Google Cloud Run / a VPS** | Paid (Cloud Run needs a card) | Heavier traffic | No sleeping; more RAM. |

## Own domain (optional)

Buy a domain (e.g. `divyangsahayak.in`, about ₹500–1,000 a year) from any registrar. In Render open the service → **Settings → Custom Domains**, add it, and create the DNS record Render shows. Render issues the HTTPS certificate.

## Play Store listing (optional)

The site is already an installable web app, so tools such as [PWABuilder](https://www.pwabuilder.com/) can package it for the Play Store (a Google Play developer account has a one-time fee).

## Troubleshooting

| What you see | What to do |
|---|---|
| Build fails | Open the service's **Logs**; the last lines name the problem. |
| Service restarts with "out of memory" | The free 512 MB was exceeded. Use Render's next instance size, or Azure. |
| "The assistant's AI model isn't available" | Groq retired the model. Change `GROQ_MODEL` in Render's **Environment** tab to a model from <https://console.groq.com/docs/models>. |
| "Its AI service key was rejected" | `GROQ_API_KEY` missing or wrong in Render's **Environment** tab. |
| "Too many questions right now" | Groq's rate limit; see the Groq note above. |
| First page load takes about a minute | The free service was asleep; see *Sleeping* above. |
