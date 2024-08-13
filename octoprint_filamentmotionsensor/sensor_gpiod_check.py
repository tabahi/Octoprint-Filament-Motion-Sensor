'''
Run this script to test your filament motion sensor's input manually. Run it with the Octorprint environment:

/home/pi/oprint/bin/python3.9  /home/pi/oprint/lib/python3.9/site-packages/octoprint_filamentmotionsensor/sensor_gpiod_check.py

~oprint might be at a different path, and python3.9 could be python3.11 or some newer version.

Change the sensor pin below. Pin 17 works well with RPi 5 and zero2w.

Error fixes:
Try:
sudo apt install gpiod
Try:
/home/pi/oprint/bin/pip install gpiod
'''

import sys
import os
import gpiod
from gpiod.line import Direction
import select

from datetime import timedelta
from gpiod.line import Bias, Edge


motion_sensor_PIN = 17



def get_revision():
    """
    Returns Raspberry Pi Revision Code
    """
    with open("/proc/device-tree/system/linux,revision", "rb") as fp:
        return int.from_bytes(fp.read(4), 'big')

def processor():
    """
    Raspberry Pi SOC
    returns
        0: BCM2835
        1: BCM2836
        2: BCM2837
        3: BCM2711
        4: BCM2712
    """
    return int((get_revision()>>12)&7)

def type(rev):
    """
    Raspberry Pi Type
    returns
    0: A
    1: B
    2: A+
    3: B+
    4: 2B
    6: CM1
    8: 3B
    9: Zero
    a: CM3
    c: Zero W
    d: 3B+
    e: 3A+
    10: CM3+
    11: 4B
    12: Zero 2 W
    13: 400
    14: CM4
    15: CM4S
    17: 5
    """
    return int((rev>>4)&0xff)




def print_chip_info(chip_address):
    
    print("is_gpiochip_device:", gpiod.is_gpiochip_device(chip_address))

    with gpiod.Chip(chip_address) as chip:
        info = chip.get_info()
        print(f"{info.name} [{info.label}] ({info.num_lines} lines)")




def edge_type_str(event):
    if event.event_type is event.Type.RISING_EDGE:
        return "Rising"
    if event.event_type is event.Type.FALLING_EDGE:
        return "Falling"
    return "Unknown"


def read_pin_status(chip_path, line_gpio_pin):

    ## simple get value:
    lines_req = gpiod.request_lines(chip_path, consumer="sensor", config={line_gpio_pin: gpiod.LineSettings(direction=Direction.INPUT)},)
    value = lines_req.get_value(line_gpio_pin)
    print("Current pin status", value)




def async_watch_line_value(chip_path, line_gpio_pin):
    # Assume a button connecting the pin to ground,
    # so pull it up and provide some debounce.
    read_pin_status(chip_path, line_gpio_pin)
    with gpiod.request_lines(
        chip_path,
        consumer="async-watch-line-value",
        config={
            line_gpio_pin: gpiod.LineSettings(
                edge_detection=Edge.BOTH,
                bias=Bias.PULL_UP,
                debounce_period=timedelta(milliseconds=10),
            )
        },
    ) as request:
        
        poll = select.poll()
        poll.register(request.fd, select.POLLIN)
        print("Now polling... Looking for interrupts")
        try:
            while True:
                # Other fds could be registered with the poll and be handled
                # separately using the return value (fd, event) from poll()
                poll.poll(200)
                
                if request.wait_edge_events(0.2):
                    for event in request.read_edge_events():
                        print(
                            "line_gpio_pin: {}  type: {:<7}  event #{}".format(
                                event.line_offset, edge_type_str(event), event.line_seqno
                            )
                        )
                
        finally:
            poll.unregister(request.fd)





def main():

    rev = get_revision()
    print("Linux Revision:", f"{rev:08x}")
    
    print("Processor:", f"{processor()}")
    print("RPi Type:", f"{type(rev):02x}")
    
    rpi5_later = (int(f"{type(rev):02x}")>= int(f"{17}"))
    print("Is RPI5 or later", rpi5_later)
    
    chip_address = '/dev/gpiochip4' if (rpi5_later) else '/dev/gpiochip0'
    print("Selected gpiochip:", chip_address)

    try:
        chip = gpiod.Chip(chip_address)
    except Exception as ex:
        print(ex)
        print("Chip address wrong")

    print("Hostname:", os.uname().nodename, ", GPIO Chip:", chip_address, ", PIN:", motion_sensor_PIN)
    print_chip_info(chip_address)
    try:
        async_watch_line_value(chip_address, motion_sensor_PIN)
        
    except OSError as ex:
        print(ex, "\nCustomise the example configuration to suit your situation")
    
if __name__ == '__main__':
    main()


exit()
