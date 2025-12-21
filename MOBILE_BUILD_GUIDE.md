# Mobile Build Guide for Trade Yantra

This guide explains how to build your Flet application into an Android APK using GitHub Actions.

## 1. Code Changes for Mobile Compatibility

I have updated `main.py` to ensure it runs smoothly on mobile devices:

*   **Configuration Storage:** Instead of writing to a local `config.json` file (which might be read-only on mobile), the app now uses `page.client_storage`. This is the standard way to persist data like API keys on mobile apps.
*   **Scrip Master Cache:** The `scripmaster.json` file is now saved to a temporary directory (`tempfile.gettempdir()`) instead of the application folder. This ensures the app has permission to write this large file.

## 2. GitHub Actions Workflow

I have created a workflow file at `.github/workflows/build_apk.yml`. This file tells GitHub to automatically build your app whenever you push code.

**What it does:**
1.  Sets up a Python environment.
2.  Installs your dependencies from `requirements.txt`.
3.  Sets up the Flutter environment (required for Flet builds).
4.  Runs `flet build apk` to compile your Python code into an Android app.
5.  Uploads the resulting `.apk` file as an artifact you can download.

## 3. How to Build (Using GitHub Website)

Since you prefer to upload files manually via the browser, follow these steps:

### Step 1: Create a Repository
1.  Log in to your GitHub account.
2.  Click the **+** icon in the top-right corner and select **New repository**.
3.  Name it `trade-yantra` (or anything you like).
4.  Select **Public** or **Private**.
5.  Click **Create repository**.

### Step 2: Upload Application Files
1.  On your new repository page, click the link that says **uploading an existing file**.
2.  Drag and drop (or select) the following files from your computer:
    *   `main.py`
    *   `requirements.txt`
    *   `scripmaster.json` (optional, app will download it if missing)
    *   `config.json` (optional, but better to enter keys in the app)
3.  Commit changes (click the green **Commit changes** button).

### Step 3: Create the Workflow File (Crucial Step)
The build automation requires a specific file in a specific folder. It's easiest to create this directly on GitHub:

1.  In your repository, click **Add file** > **Create new file**.
2.  In the "Name your file..." box, type exactly: `.github/workflows/build_apk.yml`
    *   *Note: You must type the slashes `/` to create the folders.*
3.  Paste the content below into the large text area:

```yaml
name: Build Android APK

on:
  push:
    branches:
      - main
  workflow_dispatch:

jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3

      - name: Setup Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.11'

      - name: Install Dependencies
        run: |
          pip install -r requirements.txt
          pip install flet

      - name: Setup Flutter
        uses: subosito/flutter-action@v2
        with:
          flutter-version: '3.19.0'
          channel: 'stable'

      - name: Build APK
        run: |
          flet build apk --verbose

      - name: Upload APK
        uses: actions/upload-artifact@v4
        with:
          name: trade-yantra-apk
          path: build/apk/*.apk
```

4.  Click **Commit changes** > **Commit changes**.

### Step 4: Monitor the Build
1.  Click on the **Actions** tab at the top of your repository.
2.  You should see a workflow run named "Build Android APK" starting up (triggered by the commit you just made).
3.  Click on it to watch the progress.

### Step 5: Download the APK
1.  When the build finishes (green checkmark), click on the workflow run title.
2.  Scroll down to the **Artifacts** section.
3.  Click on `trade-yantra-apk` to download the zip file.
4.  Extract it and install the APK on your phone.
