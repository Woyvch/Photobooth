#!/usr/bin/env python
"""Photobooth program"""

# Import libraries
import os
from picamera import PiCamera, Color
from PIL import Image
from time import sleep
import RPi.GPIO as GPIO
import logging
import datetime
import sys

__author__ = "Wouter Scherpereel"

# Display settings
screen_width = 1024
screen_height = 600

# Button configuration
pin_camera_button = 17
pin_arcade_led = 27

# Setup logging
logging.basicConfig(filename='photobooth.log',
                    filemode='w',
                    level=logging.INFO,
                    format='%(asctime)s %(message)s',
                    datefmt='%m/%d/%Y %I:%M:%S %p')

# Setup GPIO
GPIO.setmode(GPIO.BCM)
GPIO.setup(pin_camera_button, GPIO.IN, pull_up_down=GPIO.PUD_UP)
GPIO.setup(pin_arcade_led, GPIO.OUT, initial=GPIO.LOW)

# Quit if the button is pressed while starting up
if GPIO.input(pin_camera_button) == GPIO.LOW:
    logging.info('Exiting - the button was pressed during startup')
    raise SystemExit

# Camera properties
try:
    camera = PiCamera()
except:
    logging.error('Error initializing the camera')
    raise SystemExit
camera.rotation = 180  # rotate the image
camera.resolution = (1920, 1120)  # max resolution to evade preview issues
camera.annotate_text_size = 100
camera.annotate_background = Color('blue')
camera.annotate_foreground = Color('yellow')

# Get the path of the script to create the path of the image
script_dir = os.path.dirname(os.path.abspath(__file__))

def overlay_image(image_name, duration=0, layer=3):
    """Creates an overlay."""
    # Load the arbitrarily sized image
    img = Image.open(os.path.join(script_dir, image_name))
    # Create an image padded to the required size with mode 'RGB'
    pad = Image.new('RGB', (
        ((img.size[0] + 31) // 32) * 32,
        ((img.size[1] + 15) // 16) * 16,
    ))
    # Paste the original image into the padded one
    pad.paste(img, (0, 0))
    # Add the overlay with the padded image as the source,
    # but the originals dimensions
    o = camera.add_overlay(pad.tobytes(), size=img.size)
    # By default, the overlay is in layer 0, beneath the preview
    # which defaults to layer 2. Here we make the new overlay
    # semi-transparant, then move it above the preview
    # o.alpha = 255  # set the transparantie
    o.layer = layer
    o.id = layer
    logging.info('Created overlay ' + image_name)
    if duration > 0:
        sleep(duration)
        remove_overlay(o)
        return -1  # '-1' indicates there is no overlay
    else:
        return o  # we have an overlay, and will need to remove it later

def remove_overlay(overlay):
    """Remove the given overlay."""
    if overlay != -1:
        camera.remove_overlay(overlay)
        logging.info('Removed overlay ' + str(overlay.id))

def set_default_path():
    """Check if there is a usb drive: if so, set path to it or use default path."""
    basedir = '/media/pi/'
    photo_path = ""
    for d in os.listdir(basedir):
        photo_path = os.path.join(basedir, d) + "/photobooth/"
        # check if '/photobooth/' path exists and if not, create it
        # if creating the path generates an error, set path to "" and go for next one
        if not os.path.exists(photo_path):
            try:
                os.makedirs(photo_path)
                logging.info('creating new folder')
            except:
                photo_path = ""
                logging.info("error creating dir")
    # no photo_path set so use default
    if photo_path == "":
        photo_path = script_dir + "/photobooth/"
    logging.info('Saving to: ' + photo_path)
    return photo_path

def set_filename():
    """Create a filename based on the current timestamp."""
    filename = str(datetime.datetime.now()).split('.')[0]
    filename = filename.replace(' ', '_')
    filename = filename.replace(':', '-')
    return filename

def photo_screen(photo_number):
    """Creates the overlay screen before the pictures."""
    get_ready_image = overlay_image('Assets/get_ready_' + str(photo_number) + '.png', 2)
    remove_overlay(get_ready_image)

def take_photo(photo_number, filepath, filename_prefix):
    """Capture the image and save to file."""
    filename = filepath + filename_prefix + '_' + str(photo_number) + 'of3.jpg'
    # Countdown from 3, and display countdown on screen
    for counter in range(3, 0, -1):
        camera.annotate_text = '             ...' + str(counter)
        sleep(1)
    # Save the image to a file named image + framenumber
    camera.annotate_text = ''
    camera.capture(filename)
    logging.info('Photo ' + str(photo_number) + ' saved')

def playback(total_pics, filepath_prefix, filename_prefix):
    """Show the photos taken."""
    # Processing
    overlay_image('Assets/processing.png', 2)
    # Playback
    prev_overlay = False
    for photo_number in range(1, total_pics + 1):
        filename = filepath_prefix + filename_prefix + '_' + str(photo_number) + 'of' + str(total_pics)+'.jpg'
        this_overlay = overlay_image(filename, 0, (3 + total_pics))
        # The idea here, is only remove the previous overlay after a new overlay is added.
        if prev_overlay:
            remove_overlay(prev_overlay)
        sleep(2)
        prev_overlay = this_overlay
    remove_overlay(prev_overlay)
    # Finished
    overlay_image('Assets/all_done.png', 2, 4)

def main():
    """Main program loop."""
    logging.info('Main program started')
    # Start camera preview
    camera.start_preview()
    # Display intro screen
    intro_image_1 = overlay_image('Assets/intro_1.png', 0, 3)
    intro_image_2 = overlay_image('Assets/intro_2.png', 0, 4)
    # Show intro screens
    i = 0
    blink_speed = 10
    while True:
        # Use falling edge detection to see if button is pushed
        photo_button_pressed = GPIO.wait_for_edge(pin_camera_button, GPIO.FALLING, timeout=100)
        # Alternate between the 2 intro screens
        if photo_button_pressed is None:
            i = i+1
            if i == blink_speed:
                intro_image_2.alpha = 255
                GPIO.output(pin_arcade_led, 1)
            elif i == (2*blink_speed):
                intro_image_2.alpha = 0
                GPIO.output(pin_arcade_led, 0)
                i = 0
            # Restart loop
            sleep(0.1)
            continue
        # Button has been pressed
        logging.info('Button is pressed!')
        # Remove overlay intro screens
        remove_overlay(intro_image_1)
        remove_overlay(intro_image_2)
        # Get folder to save pictures to
        filepath = set_default_path()
        # Get filename to use
        filename = set_filename()
        # Store the current frame number
        frame = 1
        # add a loop to take three pictures
        for i in range(3):
            photo_screen(frame)
            # Take the photos
            take_photo(frame, filepath, filename)
            frame += 1
        playback(3, filepath, filename)
        # Display intro screen again
        intro_image_1 = overlay_image('Assets/intro_1.png', 0, 3)
        intro_image_2 = overlay_image('Assets/intro_2.png', 0, 4)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        logging.warning('keyboard interrupt')
    except Exception as exception:
        logging.error('Unexpected error: ' + str(exception))
    finally:
        logging.info('End of session')
        camera.stop_preview()
        GPIO.cleanup()
        sys.exit()