import os
import logging
from datetime import datetime, timedelta
from flask import Flask, jsonify
from apscheduler.schedulers.background import BackgroundScheduler
from dotenv import load_dotenv
import dropbox
from instagrapi import Client
import tempfile
import shutil
import requests

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# Initialize Dropbox client
dropbox_access_token = os.getenv("DROPBOX_ACCESS_TOKEN")
dropbox_refresh_token = os.getenv("DROPBOX_REFRESH_TOKEN")
dropbox_app_key = os.getenv("DROPBOX_APP_KEY")
dropbox_app_secret = os.getenv("DROPBOX_APP_SECRET")

dbx = None


def get_dropbox_client():
    """Get or refresh Dropbox client with valid token"""
    global dbx, dropbox_access_token

    try:
        if dbx is None:
            dbx = dropbox.Dropbox(dropbox_access_token)

        # Test the token by making a simple API call
        dbx.users_get_current_account()
        return dbx

    except dropbox.exceptions.AuthError:
        logger.info("Dropbox token expired, attempting to refresh...")
        if refresh_dropbox_token():
            dbx = dropbox.Dropbox(dropbox_access_token)
            return dbx
        else:
            raise Exception("Failed to refresh Dropbox token")

    except Exception as e:
        logger.error(f"Error with Dropbox client: {e}")
        raise


def refresh_dropbox_token():
    """Refresh the Dropbox access token using refresh token"""
    global dropbox_access_token

    if not all([dropbox_refresh_token, dropbox_app_key, dropbox_app_secret]):
        logger.error("Missing refresh token or app credentials for token refresh")
        return False

    try:
        # Exchange refresh token for new access token
        response = requests.post(
            "https://api.dropboxapi.com/oauth2/token",
            data={
                "grant_type": "refresh_token",
                "refresh_token": dropbox_refresh_token,
                "client_id": dropbox_app_key,
                "client_secret": dropbox_app_secret,
            },
        )

        if response.status_code == 200:
            new_token_data = response.json()
            dropbox_access_token = new_token_data["access_token"]

            # Update environment variable (for current session)
            os.environ["DROPBOX_ACCESS_TOKEN"] = dropbox_access_token

            # Update the .env file with the new token
            try:
                env_file_path = ".env"
                with open(env_file_path, "r") as file:
                    lines = file.readlines()

                # Find and update the DROPBOX_ACCESS_TOKEN line
                for i, line in enumerate(lines):
                    if line.startswith("DROPBOX_ACCESS_TOKEN="):
                        lines[i] = f"DROPBOX_ACCESS_TOKEN={dropbox_access_token}\n"
                        break

                # Write the updated content back to .env file
                with open(env_file_path, "w") as file:
                    file.writelines(lines)

                logger.info("Successfully updated .env file with new access token")
            except Exception as e:
                logger.warning(f"Could not update .env file: {e}")

            logger.info("Successfully refreshed Dropbox access token")
            return True
        else:
            logger.error(
                f"Failed to refresh token: {response.status_code} - {response.text}"
            )
            return False

    except Exception as e:
        logger.error(f"Error refreshing Dropbox token: {e}")
        return False


# Initialize Instagram client
ig = Client()
ig.login(os.getenv("IG_USERNAME"), os.getenv("IG_PASSWORD"))

# Global variable to track current image number
current_image_number = 1
MAX_IMAGES = 72


def post_image_to_instagram():
    """Post the next image from Dropbox to Instagram"""
    global current_image_number

    try:
        # Check if we've reached the end of images
        if current_image_number > MAX_IMAGES:
            logger.info("All images have been posted. Resetting to image 1.")
            current_image_number = 1

        # Construct the image path in Dropbox
        image_path = f"/quotes/{current_image_number}.jpg"

        # Download the image from Dropbox
        logger.info(f"Downloading image {current_image_number}.jpg from Dropbox...")

        try:
            # Get fresh Dropbox client (with token refresh if needed)
            dbx_client = get_dropbox_client()
            metadata, response = dbx_client.files_download(image_path)
        except dropbox.exceptions.ApiError as e:
            logger.error(f"Error downloading {image_path}: {e}")
            current_image_number += 1
            return
        except Exception as e:
            logger.error(f"Unexpected error with Dropbox: {e}")
            current_image_number += 1
            return

        # Save the image to a temporary file
        with tempfile.NamedTemporaryFile(delete=False, suffix=".jpg") as temp_file:
            temp_file.write(response.content)
            temp_file_path = temp_file.name

        try:
            # Post to Instagram
            logger.info(f"Posting image {current_image_number}.jpg to Instagram...")

            # Upload the photo to Instagram
            media = ig.photo_upload(
                temp_file_path,
                caption="",
            )

            logger.info(
                f"Successfully posted image {current_image_number}.jpg to Instagram"
            )
            logger.info(f"Media ID: {media.id}")

            # Increment the image number for next time
            current_image_number += 1

        except Exception as e:
            logger.error(f"Error posting to Instagram: {e}")
        finally:
            # Clean up temporary file
            if os.path.exists(temp_file_path):
                os.unlink(temp_file_path)

    except Exception as e:
        logger.error(f"Unexpected error in post_image_to_instagram: {e}")


# Initialize scheduler
scheduler = BackgroundScheduler()
scheduler.add_job(func=post_image_to_instagram, trigger="interval", hours=6)
scheduler.start()


@app.route("/")
def home():
    """Home endpoint showing service status"""
    return jsonify(
        {
            "status": "running",
            "service": "Instagram Auto Poster",
            "next_image": current_image_number,
            "total_images": MAX_IMAGES,
            "last_run": "Check logs for details",
            "next_run": "Every 6 hours",
        }
    )


@app.route("/health")
def health():
    """Health check endpoint for Render"""
    return jsonify({"status": "healthy"})


@app.route("/post-now")
def post_now():
    """Manual trigger to post an image immediately"""
    try:
        post_image_to_instagram()
        return jsonify(
            {
                "status": "success",
                "message": f"Image {current_image_number - 1} posted successfully",
                "next_image": current_image_number,
            }
        )
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route("/status")
def status():
    """Detailed status endpoint"""
    return jsonify(
        {
            "current_image_number": current_image_number,
            "max_images": MAX_IMAGES,
            "images_remaining": MAX_IMAGES - current_image_number + 1,
            "scheduler_running": scheduler.running,
            "next_job": "Every 6 hours",
        }
    )


if __name__ == "__main__":
    # Refresh Dropbox token at startup to ensure we have a valid one
    logger.info("Service starting, refreshing Dropbox token...")
    try:
        get_dropbox_client()
        logger.info("Dropbox token refreshed successfully at startup")
    except Exception as e:
        logger.error(f"Failed to refresh Dropbox token at startup: {e}")
        logger.info("Continuing with existing token...")

    # Post first image immediately when service starts
    logger.info("Posting first image...")
    post_image_to_instagram()

    # Run the Flask app
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
