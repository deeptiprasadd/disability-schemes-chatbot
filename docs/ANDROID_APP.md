# 📱 Android App (APK and Play Store)

The website is already an installable web app. This guide turns it into a **real Android app** people can download: an `.apk` file offered on your website, and optionally a **Google Play Store** listing.

The app is built with **[PWABuilder](https://www.pwabuilder.com)** (free, from Microsoft). It wraps your live site in a *Trusted Web Activity*: a small Android app that opens the site full-screen, with its own icon and no browser bar. Updates to the website appear in the app automatically, so you never rebuild it for content changes.

---

## 1. Build the app (about 10 minutes)

1. Open <https://sneh-saathi.onrender.com> once first, so the free server wakes up.
2. Go to <https://www.pwabuilder.com>, paste that address, and start the check.
3. Choose **Package for stores → Android** and **Generate package**. Suggested options (PWABuilder's wording may differ slightly):
   - **Package ID:** `com.snehsaathi.app` (if you buy the domain `snehsaathi.in`, `in.snehsaathi.app` fits too). It can never change after release.
   - **App name:** `Sneh Saathi`. **Launcher name:** `Sneh Saathi`.
   - **Signing key:** **Create new**.
4. Download the zip. It contains:

| File | What it is |
|---|---|
| `*.apk` | The app, ready to install on phones |
| `*.aab` | The same app in Play Store format |
| `assetlinks.json` | Proof for Android that the app and the website belong together |
| `signing.keystore` + `signing-key-info.txt` | **Your signing key and its passwords** |

> ⚠️ **Keep `signing.keystore` and `signing-key-info.txt` safe and private** (for example in a password manager or an offline backup). Every future update must be signed with the same key: lose it and you can never update the app; leak it and someone else could publish fake updates. `.gitignore` already blocks these files from git.

## 2. Put the app on your website

Copy two files from the zip into the project, with exactly these names:

| From the zip | To |
|---|---|
| `assetlinks.json` | `frontend/android/assetlinks.json` |
| the `.apk` file | `frontend/android/sneh-saathi.apk` |

Then commit and push (see the commands at the end). After Render redeploys:

- `https://sneh-saathi.onrender.com/.well-known/assetlinks.json` returns the file, so the app opens **full-screen without a browser bar**.
- Android visitors see a **"Download Android app (APK)"** link in the *Get the app* card on the home screen.

## 3. Installing the APK on a phone

1. On the Android phone, open the website and tap **Download Android app (APK)**.
2. Open the downloaded file. Android asks to **allow installs from this source** (Chrome): allow it once.
3. Tap **Install**. Because the app is not from the Play Store, Play Protect may show a warning; choose **Install anyway**.

The app then appears on the home screen as **Sneh Saathi**.

> Many people are wary of installing APKs from outside the Play Store. The website's **Install app** button gives the same experience without any warnings, so the APK is mainly for people who expect a "real app" download, and for your project demonstration.

## 4. Google Play Store (optional)

1. Create a **Google Play Console** developer account (one-time fee, identity verification).
2. New personal developer accounts must run a **closed test with a minimum number of testers for a set period** before the app can go public (at the time of writing, 12 testers for 14 days). Check the current rule in Play Console.
3. Upload the **`.aab`** file, fill in the store listing (description, screenshots, privacy policy, content rating).
4. Play re-signs the app with its own key. In **Play Console → Setup → App integrity**, copy the **App signing key SHA-256 fingerprint** and add it to `frontend/android/assetlinks.json` (a second fingerprint in the `sha256_cert_fingerprints` list), then push. Without this, the Play Store version shows a browser bar.

## Good to know

- **The free server sleeps** after about 15 minutes without visitors, so the app's first screen can take about a minute to appear. See `docs/DEPLOY.md`.
- **The app needs the internet**: it is the website in an app shell. The app shell opens offline, but questions need a connection.
- **Changing the website address** (for example to your own domain) means rebuilding the app for the new address and publishing a new `assetlinks.json` there.
