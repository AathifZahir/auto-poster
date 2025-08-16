import os
import logging
from datetime import datetime
from dotenv import load_dotenv
import dropbox
from instagrapi import Client
import tempfile
import requests
import time
from plyer import notification
import urllib.request
import tkinter as tk
from tkinter import messagebox
import ttkbootstrap as ttk
from ttkbootstrap.constants import *
from PIL import Image, ImageTk
import json

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Global variables for the GUI
root = None
current_image_label = None
status_label = None
current_image_path = None
current_image_number = 1  # Initialize current image number
MAX_IMAGES = 72  # Total number of images

# File to store progress
PROGRESS_FILE = "progress.json"

# Color scheme using ttkbootstrap constants
COLORS = {
    "primary": PRIMARY,
    "secondary": SECONDARY,
    "success": SUCCESS,
    "warning": WARNING,
    "danger": DANGER,
    "info": INFO,
    "light": LIGHT,
    "dark": DARK,
}


def save_progress():
    """Save current progress to local file"""
    try:
        progress_data = {
            "current_image_number": current_image_number,
            "last_updated": datetime.now().isoformat(),
        }
        with open(PROGRESS_FILE, "w") as f:
            json.dump(progress_data, f, indent=2)
        logger.info(f"Progress saved: Image #{current_image_number}")
    except Exception as e:
        logger.error(f"Failed to save progress: {e}")


def load_progress():
    """Load progress from local file"""
    global current_image_number
    try:
        if os.path.exists(PROGRESS_FILE):
            with open(PROGRESS_FILE, "r") as f:
                progress_data = json.load(f)
                current_image_number = progress_data.get("current_image_number", 1)
                logger.info(f"Progress loaded: Image #{current_image_number}")
                return True
        else:
            logger.info("No progress file found, starting from image 1")
            return False
    except Exception as e:
        logger.error(f"Failed to load progress: {e}")
        current_image_number = 1
        return False


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


def check_internet_connection():
    """Check if internet connection is available"""
    try:
        urllib.request.urlopen("http://www.google.com", timeout=3)
        return True
    except Exception:
        return False


def show_notification(title, message, timeout=10):
    """Show Windows notification"""
    try:
        notification.notify(
            title=title, message=message, timeout=timeout, app_icon=None
        )
    except Exception as e:
        logger.warning(f"Could not show notification: {e}")


def ask_permission_for_posting():
    """Ask user permission before posting"""
    show_notification(
        "Instagram Auto Poster",
        f"Ready to post image #{current_image_number}. Click to allow posting.",
        timeout=30,
    )

    # For now, we'll auto-approve after a delay
    # In a real implementation, you could use a GUI dialog
    time.sleep(5)  # Give user 5 seconds to see notification
    return True


# Global variable to track current image number
current_image_number = 1
MAX_IMAGES = 72


def post_image_to_instagram():
    """Post the next image from Dropbox to Instagram"""
    global current_image_number

    try:
        # Check internet connection first
        if not check_internet_connection():
            show_notification(
                "Instagram Auto Poster - No Internet",
                "Please connect to the internet to post images.",
                timeout=15,
            )
            logger.warning("No internet connection available")
            return

        # Check if we've reached the end of images
        if current_image_number > MAX_IMAGES:
            logger.info("All images have been posted. Resetting to image 1.")
            current_image_number = 1
            show_notification(
                "Instagram Auto Poster",
                "All images posted! Starting over from image 1.",
                timeout=10,
            )

        # Ask for permission before posting
        if not ask_permission_for_posting():
            logger.info("User denied permission to post")
            show_notification(
                "Instagram Auto Poster", "Posting cancelled by user.", timeout=5
            )
            return

        # Construct the image path in Dropbox
        image_path = f"/quotes/{current_image_number}.jpg"

        # Download the image from Dropbox
        logger.info(f"Downloading image {current_image_number}.jpg from Dropbox...")
        show_notification(
            "Instagram Auto Poster",
            f"Downloading image #{current_image_number} from Dropbox...",
            timeout=5,
        )

        try:
            # Get fresh Dropbox client (with token refresh if needed)
            dbx_client = get_dropbox_client()
            metadata, response = dbx_client.files_download(image_path)
        except dropbox.exceptions.ApiError as e:
            error_msg = f"Error downloading {image_path}: {e}"
            logger.error(error_msg)
            show_notification(
                "Instagram Auto Poster - Dropbox Error", error_msg, timeout=15
            )
            current_image_number += 1
            return
        except Exception as e:
            error_msg = f"Unexpected error with Dropbox: {e}"
            logger.error(error_msg)
            show_notification("Instagram Auto Poster - Error", error_msg, timeout=15)
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

            # Show success notification
            show_notification(
                "Instagram Auto Poster - Success!",
                f"Image #{current_image_number} posted successfully to Instagram!",
                timeout=10,
            )

            # Increment the image number for next time
            current_image_number += 1

            # Save progress
            save_progress()

        except Exception as e:
            error_msg = f"Error posting to Instagram: {e}"
            logger.error(error_msg)
            show_notification(
                "Instagram Auto Poster - Instagram Error", error_msg, timeout=15
            )
        finally:
            # Clean up temporary file
            if os.path.exists(temp_file_path):
                os.unlink(temp_file_path)

    except Exception as e:
        logger.error(f"Unexpected error in post_image_to_instagram: {e}")


def get_image_from_dropbox():
    """Get the next image from Dropbox and display it"""
    global current_image_path, current_image_number

    logger.info(f"Getting image #{current_image_number} from Dropbox...")

    try:
        # Check internet connection first
        if not check_internet_connection():
            messagebox.showerror("Error", "No internet connection available")
            return

        # Check if we've reached the end of images
        if current_image_number > MAX_IMAGES:
            current_image_number = 1

        # Construct the image path in Dropbox
        image_path = f"/quotes/{current_image_number}.jpg"

        # Download the image from Dropbox
        logger.info(f"Downloading image {current_image_number}.jpg from Dropbox...")
        show_notification(
            "Instagram Auto Poster",
            f"Downloading image #{current_image_number} from Dropbox...",
            timeout=5,
        )

        try:
            # Get fresh Dropbox client (with token refresh if needed)
            dbx_client = get_dropbox_client()
            metadata, response = dbx_client.files_download(image_path)
        except dropbox.exceptions.ApiError as e:
            error_msg = f"Error downloading {image_path}: {e}"
            logger.error(error_msg)
            show_notification(
                "Instagram Auto Poster - Dropbox Error", error_msg, timeout=15
            )
            messagebox.showerror("Dropbox Error", error_msg)
            return
        except Exception as e:
            error_msg = f"Unexpected error with Dropbox: {e}"
            logger.error(error_msg)
            show_notification("Instagram Auto Poster - Error", error_msg, timeout=15)
            messagebox.showerror("Error", error_msg)
            return

        # Save the image to a temporary file
        with tempfile.NamedTemporaryFile(delete=False, suffix=".jpg") as temp_file:
            temp_file.write(response.content)
            current_image_path = temp_file.name

        # Display the image in the GUI
        try:
            image = Image.open(current_image_path)
            # Resize image to fit in the GUI (max 400x400)
            image.thumbnail((400, 400), Image.Resampling.LANCZOS)
            photo = ImageTk.PhotoImage(image)

            current_image_label.configure(image=photo)
            current_image_label.image = photo  # Keep a reference

            status_label.config(
                text=f"Image #{current_image_number} loaded successfully"
            )

            # Update info display
            update_info_display()

        except Exception as e:
            error_msg = f"Error displaying image: {e}"
            logger.error(error_msg)
            show_notification(
                "Instagram Auto Poster - Display Error", error_msg, timeout=15
            )
            messagebox.showerror("Display Error", error_msg)

    except Exception as e:
        logger.error(f"Unexpected error in get_image_from_dropbox: {e}")
        show_notification(
            "Instagram Auto Poster - Error", f"Unexpected error: {e}", timeout=15
        )
        messagebox.showerror("Error", f"Unexpected error: {e}")


def update_info_display():
    """Update the info display with current values"""
    global info_label, current_image_number
    if "info_label" in globals() and info_label is not None:
        info_text = f"Total Images: {MAX_IMAGES}\nCurrent Image: {current_image_number}\nImages Remaining: {MAX_IMAGES - current_image_number + 1}"
        info_label.config(text=info_text)

        # Update progress bar if it exists
        if "update_progress_display" in globals():
            update_progress_display()

        logger.info(
            f"Info display updated: Current Image #{current_image_number}, {MAX_IMAGES - current_image_number + 1} remaining"
        )


def change_image_number():
    """Allow user to manually change the current image number with modern dialog"""
    global current_image_number

    # Create a modern dialog for input
    dialog = ttk.Toplevel(root)
    dialog.title("Change Image Number")
    dialog.geometry("400x300")
    dialog.resizable(False, False)
    dialog.transient(root)
    dialog.grab_set()

    # Center the dialog
    dialog.geometry("+%d+%d" % (root.winfo_rootx() + 100, root.winfo_rooty() + 100))

    # Main frame
    main_dialog_frame = ttk.Frame(dialog, padding="30")
    main_dialog_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))

    # Title
    title_label = ttk.Label(
        main_dialog_frame,
        text="Change Image Number",
        font=("Segoe UI", 16, "bold"),
    )
    title_label.grid(row=0, column=0, columnspan=2, pady=(0, 25))

    # Current image info
    current_info = ttk.Label(
        main_dialog_frame,
        text=f"Current Image: #{current_image_number}",
        font=("Segoe UI", 11),
    )
    current_info.grid(row=1, column=0, columnspan=2, pady=(0, 20))

    # Input label
    input_label = ttk.Label(
        main_dialog_frame,
        text=f"New Image Number (1-{MAX_IMAGES}):",
        font=("Segoe UI", 10, "bold"),
    )
    input_label.grid(row=2, column=0, columnspan=2, pady=(0, 15))

    # Entry with modern styling
    entry_var = tk.StringVar(value=str(current_image_number))
    entry = ttk.Entry(
        main_dialog_frame, textvariable=entry_var, width=15, font=("Segoe UI", 12)
    )
    entry.grid(row=3, column=0, columnspan=2, pady=(0, 30))
    entry.focus()
    entry.select_range(0, tk.END)

    # Buttons with modern styling
    def apply_change():
        global current_image_number
        try:
            new_number = int(entry_var.get())
            if 1 <= new_number <= MAX_IMAGES:
                current_image_number = new_number
                logger.info(f"User changed image number to #{current_image_number}")
                save_progress()
                update_info_display()
                status_label.config(text=f"Changed to image #{current_image_number}")
                dialog.destroy()
            else:
                messagebox.showerror(
                    "Error", f"Image number must be between 1 and {MAX_IMAGES}"
                )
        except ValueError:
            messagebox.showerror("Error", "Please enter a valid number")

    def cancel_change():
        dialog.destroy()

    button_frame = ttk.Frame(main_dialog_frame)
    button_frame.grid(row=4, column=0, columnspan=2)

    apply_btn = ttk.Button(
        button_frame,
        text="Apply",
        command=apply_change,
        bootstyle="success",
        width=12,
    )
    apply_btn.grid(row=0, column=0, padx=(0, 15))

    cancel_btn = ttk.Button(
        button_frame,
        text="Cancel",
        command=cancel_change,
        bootstyle="secondary",
        width=12,
    )
    cancel_btn.grid(row=0, column=1)

    # Bind Enter key to apply
    entry.bind("<Return>", lambda e: apply_change())

    # Clear any existing image
    global current_image_path
    if current_image_path:
        current_image_label.configure(image="")
        current_image_label.image = None
        current_image_path = None


def post_current_image():
    """Post the currently loaded image to Instagram"""
    global current_image_path, current_image_number

    if not current_image_path:
        messagebox.showwarning("Warning", "Please get an image first!")
        return

    try:
        # Check internet connection first
        if not check_internet_connection():
            messagebox.showerror("Error", "No internet connection available")
            return

        # Ask for permission before posting
        if not ask_permission_for_posting():
            logger.info("User denied permission to post")
            show_notification(
                "Instagram Auto Poster", "Posting cancelled by user.", timeout=5
            )
            return

            # Post to Instagram
        logger.info(f"Posting image {current_image_number}.jpg to Instagram...")

        # Upload the photo to Instagram
        media = ig.photo_upload(
            current_image_path,
            caption="",
        )

        logger.info(
            f"Successfully posted image {current_image_number}.jpg to Instagram"
        )
        logger.info(f"Media ID: {media.id}")

        # Show success notification
        show_notification(
            "Instagram Auto Poster - Success!",
            f"Image #{current_image_number} posted successfully to Instagram!",
            timeout=10,
        )

        # Update status
        status_label.config(text=f"Image #{current_image_number} posted successfully!")

        # Clean up the temporary file
        if os.path.exists(current_image_path):
            os.unlink(current_image_path)
            current_image_path = None

            # Move to next image
        current_image_number += 1
        logger.info(
            f"Image posted successfully, moving to image #{current_image_number}"
        )

        # Save progress
        save_progress()

        # Update info display
        update_info_display()

        # Clear the image display
        current_image_label.configure(image="")
        current_image_label.image = None

    except Exception as e:
        error_msg = f"Error posting to Instagram: {e}"
        logger.error(error_msg)
        show_notification(
            "Instagram Auto Poster - Instagram Error", error_msg, timeout=15
        )
        messagebox.showerror("Instagram Error", error_msg)


def create_gui():
    """Create the main GUI window with modern styling"""
    global root, current_image_label, status_label

    root = ttk.Window(themename="cosmo")
    root.title("Instagram Auto Poster")
    root.geometry("600x600")
    root.resizable(False, False)

    # ttkbootstrap handles most styling automatically
    # We'll use built-in styles and colors

    # Create scrollable canvas
    canvas = tk.Canvas(root, highlightthickness=0)
    scrollbar = ttk.Scrollbar(root, orient="vertical", command=canvas.yview)
    scrollable_frame = ttk.Frame(canvas, padding="25")

    scrollable_frame.bind(
        "<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
    )

    canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
    canvas.configure(yscrollcommand=scrollbar.set)

    # Main frame with padding and background
    main_frame = scrollable_frame

    # Title with modern styling
    title_frame = ttk.Frame(main_frame)
    title_frame.grid(row=0, column=0, columnspan=2, pady=(0, 25))

    title_label = ttk.Label(
        title_frame, text="Instagram Auto Poster", font=("Segoe UI", 22, "bold")
    )
    title_label.grid(row=0, column=0)

    subtitle_label = ttk.Label(
        title_frame,
        text="Automated Instagram posting from Dropbox",
        font=("Segoe UI", 12),
    )
    subtitle_label.grid(row=1, column=0, pady=(8, 0))

    # Progress bar frame
    progress_frame = ttk.LabelFrame(main_frame, text="Progress", padding="20")
    progress_frame.grid(
        row=1, column=0, columnspan=2, pady=(0, 20), sticky=(tk.W, tk.E)
    )

    # Progress bar
    progress_var = tk.DoubleVar()
    progress_bar = ttk.Progressbar(
        progress_frame,
        variable=progress_var,
        maximum=MAX_IMAGES,
        length=450,
        mode="determinate",
        bootstyle="success-striped",
    )
    progress_bar.grid(row=0, column=0, pady=(0, 12))

    # Progress text
    progress_text = ttk.Label(
        progress_frame,
        text=f"Image {current_image_number} of {MAX_IMAGES}",
    )
    progress_text.grid(row=1, column=0)

    # Image display area with modern card design
    image_frame = ttk.LabelFrame(main_frame, text="Current Image", padding="20")
    image_frame.grid(row=2, column=0, columnspan=2, pady=(0, 20), sticky=(tk.W, tk.E))

    current_image_label = tk.Label(
        image_frame,
        text="No image loaded\n\nClick 'Get Image' to load an image from Dropbox",
        width=45,
        height=12,
        font=("Segoe UI", 10),
    )
    current_image_label.grid(row=0, column=0, pady=10)

    # Buttons frame with modern styling
    button_frame = ttk.Frame(main_frame)
    button_frame.grid(row=3, column=0, columnspan=2, pady=(0, 20))

    # Create modern buttons with ttkbootstrap styles
    get_image_btn = ttk.Button(
        button_frame,
        text="Get Image",
        command=get_image_from_dropbox,
        bootstyle="primary",
        width=18,
    )
    get_image_btn.grid(row=0, column=0, padx=(0, 15))

    post_image_btn = ttk.Button(
        button_frame,
        text="Post Image",
        command=post_current_image,
        bootstyle="success",
        width=18,
    )
    post_image_btn.grid(row=0, column=1, padx=(0, 15))

    change_image_btn = ttk.Button(
        button_frame,
        text="Change Image #",
        command=change_image_number,
        bootstyle="secondary",
        width=18,
    )
    change_image_btn.grid(row=0, column=2)

    # Status frame with modern design
    status_frame = ttk.LabelFrame(main_frame, text="Status", padding="20")
    status_frame.grid(row=4, column=0, columnspan=2, pady=(0, 20), sticky=(tk.W, tk.E))

    status_label = ttk.Label(
        status_frame,
        text="Ready to get images from Dropbox",
        wraplength=450,
    )
    status_label.grid(row=0, column=0, pady=8)

    # Info frame with statistics
    info_frame = ttk.LabelFrame(main_frame, text="Statistics", padding="20")
    info_frame.grid(row=5, column=0, columnspan=2, sticky=(tk.W, tk.E))

    global info_label
    info_text = f"Total Images: {MAX_IMAGES}\nCurrent Image: {current_image_number}\nImages Remaining: {MAX_IMAGES - current_image_number + 1}"
    info_label = ttk.Label(info_frame, text=info_text, justify=tk.LEFT)
    info_label.grid(row=0, column=0, pady=8)

    # Footer with version info
    footer_frame = ttk.Frame(main_frame)
    footer_frame.grid(row=6, column=0, columnspan=2, pady=(20, 0))

    footer_label = ttk.Label(
        footer_frame,
        text="Instagram Auto Poster v1.0",
        font=("Segoe UI", 9),
    )
    footer_label.grid(row=0, column=0)

    # Configure grid weights for responsive layout
    root.columnconfigure(0, weight=1)
    root.rowconfigure(0, weight=1)
    main_frame.columnconfigure(0, weight=1)
    main_frame.columnconfigure(1, weight=1)

    # Pack canvas and scrollbar
    canvas.grid(row=0, column=0, sticky="nsew")
    scrollbar.grid(row=0, column=1, sticky="ns")

    # Bind mouse wheel scrolling
    def _on_mousewheel(event):
        canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

    canvas.bind_all("<MouseWheel>", _on_mousewheel)

    # Update progress bar and info display after GUI is fully created
    def update_progress():
        progress_var.set(current_image_number)
        progress_text.config(text=f"Image {current_image_number} of {MAX_IMAGES}")

    # Bind the update function
    global update_progress_display
    update_progress_display = update_progress

    update_info_display()
    update_progress()

    return root


if __name__ == "__main__":
    # Load saved progress
    logger.info("Loading saved progress...")
    load_progress()

    # Refresh Dropbox token at startup to ensure we have a valid one
    logger.info("Service starting, refreshing Dropbox token...")
    try:
        get_dropbox_client()
        logger.info("Dropbox token refreshed successfully at startup")
    except Exception as e:
        logger.error(f"Failed to refresh Dropbox token at startup: {e}")
        logger.info("Continuing with existing token...")

    # Create and run the GUI
    logger.info("Creating GUI...")
    root = create_gui()

    # Start the GUI main loop
    root.mainloop()

    logger.info("GUI closed by user")
    show_notification(
        "Instagram Auto Poster",
        "Application closed.",
        timeout=5,
    )
