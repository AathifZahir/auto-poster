# Instagram Auto Poster

A Flask-based web service that automatically posts images from Dropbox to Instagram at 6-hour intervals. Perfect for maintaining a consistent social media presence.

## Features

- **Automated Posting**: Posts images every 6 hours automatically
- **Dropbox Integration**: Downloads images directly from your Dropbox
- **Sequential Naming**: Works with images named 1.jpg, 2.jpg, 3.jpg, etc.
- **Web Interface**: Monitor status and manually trigger posts
- **Render Hosting**: Ready to deploy on Render cloud platform
- **Error Handling**: Robust error handling and logging

## Prerequisites

Before setting up this service, you'll need:

1. **Dropbox Account** with API access
2. **Instagram Account** (username and password)
3. **Render Account** for hosting (free tier available)

## Setup Instructions

### 1. Dropbox API Setup

1. Go to [Dropbox App Console](https://www.dropbox.com/developers/apps)
2. Click "Create app"
3. Choose "Scoped access" and "Full Dropbox access"
4. Give your app a name (e.g., "Instagram Auto Poster")
5. Copy the generated access token

### 2. Instagram Account

- Use your Instagram username and password
- **Important**: Consider using a dedicated Instagram account for automation
- Enable 2FA if you have it (you may need to generate an app password)

### 3. Image Preparation

1. Upload your images to Dropbox root folder
2. Name them sequentially: `1.jpg`, `2.jpg`, `3.jpg`, ..., `72.jpg`
3. Ensure images are in JPG format
4. Recommended image dimensions: 1080x1080 pixels (Instagram square format)

### 4. Environment Variables

Create a `.env` file in your project root with:

```bash
DROPBOX_ACCESS_TOKEN=your_dropbox_access_token_here
IG_USERNAME=your_instagram_username
IG_PASSWORD=your_instagram_password
POSTING_INTERVAL=6
MAX_IMAGES=72
```

### 5. Local Testing

1. Install dependencies:

   ```bash
   pip install -r requirements.txt
   ```

2. Run the service:

   ```bash
   python app.py
   ```

3. Visit `http://localhost:5000` to see the service status

## Deployment on Render

### Option 1: Using render.yaml (Recommended)

1. Push your code to a GitHub repository
2. Connect your GitHub repo to Render
3. Render will automatically detect the `render.yaml` file
4. Set your environment variables in Render dashboard
5. Deploy!

### Option 2: Manual Setup

1. Create a new Web Service on Render
2. Connect your GitHub repository
3. Set build command: `pip install -r requirements.txt`
4. Set start command: `gunicorn app:app`
5. Add environment variables in Render dashboard
6. Deploy

## API Endpoints

- **`/`** - Service status and information
- **`/health`** - Health check for Render
- **`/status`** - Detailed status information
- **`/post-now`** - Manually trigger a post immediately

## How It Works

1. **Service Start**: Posts the first image immediately
2. **Scheduled Posts**: Every 6 hours, downloads the next image from Dropbox
3. **Sequential Order**: Posts images in order (1.jpg, 2.jpg, 3.jpg, etc.)
4. **Loop Back**: After posting image 72.jpg, starts over with 1.jpg
5. **Error Handling**: If an image fails to post, moves to the next one

## Monitoring

- Check the service status at your Render URL
- View logs in Render dashboard
- Use `/status` endpoint for detailed information
- Monitor Instagram account for successful posts

## Troubleshooting

### Common Issues

1. **Dropbox API Error**: Verify your access token and app permissions
2. **Instagram Login Failed**: Check credentials and 2FA settings
3. **Image Not Found**: Ensure images are in Dropbox root with correct naming
4. **Service Not Starting**: Check Render logs for Python dependency issues

### Logs

- All operations are logged with timestamps
- Check Render logs for detailed error information
- Use the web interface to monitor service status

## Security Considerations

- **Never commit** your `.env` file to version control
- Use environment variables in production
- Consider using Instagram app passwords if 2FA is enabled
- Regularly rotate your Dropbox access token

## Customization

- **Posting Interval**: Change `POSTING_INTERVAL` environment variable
- **Image Count**: Modify `MAX_IMAGES` environment variable
- **Caption Format**: Edit the caption template in `app.py`
- **Image Format**: Modify the file extension handling in the code

## Support

If you encounter issues:

1. Check the logs in Render dashboard
2. Verify all environment variables are set correctly
3. Test locally first to isolate issues
4. Ensure your Dropbox and Instagram credentials are valid

## License

This project is open source and available under the MIT License.
