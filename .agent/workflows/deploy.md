---
description: Deploy Gojo Trip Planner to Render
---

# Deploy to Render

This workflow guides you through deploying the Gojo Trip Planner to Render.

## Prerequisites
- GitHub account with repository access
- Render account (sign up at https://render.com)

## Steps

### 1. Commit and Push Changes
```bash
git add .
git commit -m "Add Render deployment configuration"
git push origin main
```

### 2. Deploy to Render
1. Go to https://render.com and sign in
2. Click "New +" → "Blueprint"
3. Connect your GitHub repository
4. Select the `Gojo_V2` repository
5. Render will auto-detect `render.yaml`
6. Click "Apply" to deploy

### 3. Wait for Deployment
- Initial deployment takes 2-5 minutes
- Watch build logs in Render Dashboard
- Green checkmark = successful deployment ✓

### 4. Access Your Site
- Click the URL in Render Dashboard
- Default: `https://gojo-trip-planner.onrender.com`
- Update `SITE_URL` environment variable with actual URL

### 5. Verify Deployment
- [ ] Homepage loads correctly
- [ ] Register a new user account
- [ ] Create a test trip
- [ ] Upload a photo
- [ ] View trip on map
- [ ] Test chat functionality
- [ ] Export trip to PDF

## Troubleshooting
- **Build fails**: Check build logs for missing dependencies
- **Database errors**: Verify PostgreSQL database is active
- **Static files 404**: Ensure `app/static` directory exists
- **Slow first load**: Free tier spins down after 15min (30-60s cold start)

## Performance Tips
- Upgrade to paid plan ($7/month) to eliminate cold starts
- Use UptimeRobot to ping site every 10 minutes (keeps it active)
- Consider persistent disk for file uploads ($1/GB/month)

For detailed instructions, see [DEPLOYMENT.md](file:///f:/Gojo_V2/DEPLOYMENT.md)
