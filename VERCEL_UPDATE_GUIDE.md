# Update Your Existing Vercel Project

## Step 1: Find Your Existing Project
```bash
cd frontend
npx vercel ls
```

This will show all your Vercel projects. Look for your original `trade-yantra` or `trade-yantra-pwa` project.

## Step 2: Link to Your Existing Project
```bash
# Unlink the accidentally created project
npx vercel unlink

# Link to your existing project
npx vercel link
# When prompted:
# - Select your team/account: bhagtanibhavesh1979-oss
# - Link to existing project? YES
# - What's your project's name? [YOUR_EXISTING_PROJECT_NAME]
```

## Step 3: Deploy to Production
```bash
npx vercel --prod
```

## Step 4: Get the Production URL
The command will output something like:
```
✅  Production: https://your-existing-project.vercel.app
```

## Step 5: Update Google Cloud CORS
Copy that URL and run:
```bash
cd ..
gcloud run services update trade-yantra-api `
  --region us-central1 `
  --update-env-vars CORS_ORIGINS=https://your-existing-project.vercel.app,http://localhost:5173
```

## Step 6: Delete the Accidental Project (Optional)
```bash
npx vercel rm frontend-eight-chi-33
```

---

## Alternative: Use the New Project

If you prefer to use the new Vercel project, just run:

```bash
gcloud run services update trade-yantra-api `
  --region us-central1 `
  --update-env-vars CORS_ORIGINS=https://frontend-eight-chi-33.vercel.app,http://localhost:5173
```

Then update your Vercel project name to something cleaner:
```bash
cd frontend
npx vercel alias set frontend-eight-chi-33.vercel.app trade-yantra.vercel.app
```
