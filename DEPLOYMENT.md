# Deploying Gojo Trip Planner to Render

This guide walks you through deploying your Gojo Trip Planner application to Render for fast, reliable cloud hosting.

## 🚀 Quick Start

### Prerequisites
- GitHub account
- Render account (free) - Sign up at [render.com](https://render.com)
- Your code pushed to a GitHub repository

### Deployment Steps

#### 1. Prepare Your Repository

Ensure all deployment files are committed and pushed to GitHub:

```bash
git add .
git commit -m "Add Render deployment configuration"
git push origin main
```

#### 2. Create Render Account

1. Go to [render.com](https://render.com)
2. Sign up with your GitHub account
3. Authorize Render to access your repositories

#### 3. Deploy Using render.yaml

1. **In Render Dashboard**, click "New +" → "Blueprint"
2. **Connect Repository**: Select your `Gojo_V2` repository
3. **Auto-Detection**: Render will automatically detect `render.yaml`
4. **Review Configuration**: 
   - Web Service: `gojo-trip-planner`
   - Database: `gojo-db` (PostgreSQL)
5. **Click "Apply"**

Render will automatically:
- Create a PostgreSQL database
- Set up environment variables
- Build and deploy your application
- Provide a live URL (e.g., `https://gojo-trip-planner.onrender.com`)

#### 4. Configure Environment Variables (Optional)

The `render.yaml` file sets most variables automatically. If you need to customize:

1. Go to your service in Render Dashboard
2. Click "Environment" tab
3. Key variables (already configured):
   - `SECRET_KEY` - Auto-generated secure key
   - `DATABASE_URL` - Auto-linked to PostgreSQL
   - `ENVIRONMENT` - Set to `production`
   - `SITE_URL` - Your Render URL

**Generate a custom SECRET_KEY** (optional):
```bash
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

#### 5. Wait for Deployment

- Initial deployment takes 2-5 minutes
- Watch the build logs in real-time
- Green checkmark = successful deployment ✓

#### 6. Access Your Application

Once deployed, click the URL at the top of your service page:
```
https://gojo-trip-planner.onrender.com
```

## 🔧 Post-Deployment Configuration

### Update SITE_URL (Important!)

After deployment, update the `SITE_URL` environment variable with your actual Render URL:

1. Go to Environment tab in Render Dashboard
2. Edit `SITE_URL` to match your deployed URL
3. Save changes (service will auto-redeploy)

### Create First User Account

1. Navigate to your deployed site
2. Click "Register" or go to `/register`
3. Create your admin account
4. Start creating trips!

## 📊 Monitoring & Logs

### View Application Logs

1. In Render Dashboard, go to your service
2. Click "Logs" tab
3. View real-time application logs
4. Filter by error level if needed

### Check Database

1. Go to your `gojo-db` database in Render
2. Click "Connect" to get connection details
3. Use a PostgreSQL client (like pgAdmin) to inspect data

## ⚡ Performance Optimization

### Free Tier Limitations

Render's free tier includes:
- ✅ 750 hours/month (enough for 24/7 uptime)
- ✅ Free PostgreSQL database (90 days, then expires)
- ⚠️ **Spins down after 15 minutes of inactivity**
- ⚠️ Cold start takes 30-60 seconds

### Keep Service Active

To prevent cold starts, consider:
1. **Upgrade to Paid Plan** ($7/month) - No spin down
2. **Use a Ping Service** (free):
   - [UptimeRobot](https://uptimerobot.com)
   - [Cron-Job.org](https://cron-job.org)
   - Ping your site every 10 minutes

### Speed Improvements

1. **Enable Compression** - Already handled by FastAPI
2. **Optimize Images** - Compress photos before upload
3. **Database Indexing** - Add indexes to frequently queried fields
4. **CDN for Static Files** - Consider Cloudinary for images

## 🗄️ Database Management

### Backup Database

```bash
# Install PostgreSQL client locally
# Get connection string from Render Dashboard

pg_dump <DATABASE_URL> > backup.sql
```

### Migrate Local Data to Production

If you have existing data in `gojo.db`:

```bash
# 1. Export SQLite data
sqlite3 gojo.db .dump > sqlite_dump.sql

# 2. Convert to PostgreSQL format (manual process)
# 3. Import to Render database using psql
```

**Note**: Schema is auto-created on first deployment via `init_db()`.

## 📁 File Upload Considerations

### Current Setup (Ephemeral Storage)

- Uploaded files stored in `uploads/` and `gallery/`
- ⚠️ **Files deleted on service restart** (free tier limitation)

### Production Solutions

#### Option 1: Render Persistent Disk ($1/GB/month)
1. In Render Dashboard → Service Settings
2. Add "Persistent Disk"
3. Mount path: `/opt/render/project/src/uploads`

#### Option 2: Cloud Storage (Recommended)
Integrate with:
- **Cloudinary** (free tier: 25GB storage, 25GB bandwidth)
- **AWS S3** (pay-as-you-go)
- **Google Cloud Storage**

Update `app/routers/gallery.py` to use cloud storage SDK.

## 🐛 Troubleshooting

### Service Won't Start

**Check build logs** for errors:
- Missing dependencies? Update `requirements.txt`
- Python version mismatch? Verify `PYTHON_VERSION` in `render.yaml`

### Database Connection Errors

1. Verify `DATABASE_URL` is set correctly
2. Check database status in Render Dashboard
3. Ensure `psycopg2-binary` is in `requirements.txt`

### Static Files Not Loading

1. Check `app/static` directory exists
2. Verify FastAPI static file mounting in `app/main.py`
3. Check browser console for 404 errors

### Application Errors

1. View logs: Render Dashboard → Logs tab
2. Check for Python exceptions
3. Verify environment variables are set correctly

### Slow Performance

1. **Cold Start**: First request after inactivity takes 30-60s
2. **Database Queries**: Add indexes for frequently accessed data
3. **Upgrade Plan**: $7/month eliminates cold starts

## 🔄 Continuous Deployment

### Auto-Deploy from GitHub

Already configured in `render.yaml`:
```yaml
autoDeploy: true
```

Every push to `main` branch triggers automatic deployment.

### Manual Deploy

1. Render Dashboard → Your Service
2. Click "Manual Deploy" → "Deploy latest commit"

### Rollback

1. Go to "Events" tab
2. Find previous successful deployment
3. Click "Rollback to this version"

## 🔐 Security Best Practices

1. ✅ **SECRET_KEY**: Auto-generated by Render
2. ✅ **HTTPS**: Automatic SSL certificate
3. ✅ **Environment Variables**: Never commit `.env` to Git
4. ⚠️ **Database Backups**: Set up regular backups
5. ⚠️ **Rate Limiting**: Consider adding for production

## 📈 Scaling

### Upgrade Options

| Plan | Price | Features |
|------|-------|----------|
| Free | $0 | 750 hrs/month, spins down after 15min |
| Starter | $7/month | Always on, 0.5GB RAM |
| Standard | $25/month | 2GB RAM, better performance |

### When to Upgrade

- High traffic (>100 daily users)
- Need persistent file storage
- Require 24/7 uptime
- Want faster response times

## 🆘 Support

- **Render Docs**: [render.com/docs](https://render.com/docs)
- **Community**: [community.render.com](https://community.render.com)
- **Status**: [status.render.com](https://status.render.com)

## ✅ Deployment Checklist

- [ ] Code pushed to GitHub
- [ ] Render account created and connected to GitHub
- [ ] Blueprint deployed from `render.yaml`
- [ ] Service is running (green status)
- [ ] Database is active
- [ ] Visited deployed URL successfully
- [ ] Registered first user account
- [ ] Created test trip
- [ ] Uploaded test photo
- [ ] Verified map functionality
- [ ] Tested chat feature
- [ ] Exported trip to PDF
- [ ] Set up uptime monitoring (optional)
- [ ] Configured custom domain (optional)

---

## 🎉 You're Live!

Your Gojo Trip Planner is now deployed and accessible worldwide. Share your URL and start planning amazing trips!

**Your Deployment URL**: `https://gojo-trip-planner.onrender.com`

*Note: The actual URL will be shown in your Render Dashboard after deployment.*
