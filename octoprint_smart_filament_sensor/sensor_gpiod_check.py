import os


import gpiod
from gpiod.line import Direction
import select

from datetime import timedelta
from gpiod.line import Bias, Edge
import time

motion_sensor_PIN = 17
runout_switch_PIN = 27


chip_address = '/dev/gpiochip4' if (os.uname().nodename=='rpi5') else '/dev/gpiochip0'
chip = gpiod.Chip(chip_address)

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



def async_watch_line_value(chip_path, line_gpio_pin):
    # Assume a button connecting the pin to ground,
    # so pull it up and provide some debounce.
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
        try:
            while True:
                # Other fds could be registered with the poll and be handled
                # separately using the return value (fd, event) from poll()
                poll.poll(250)
                
                if request.wait_edge_events(0.25):
                    for event in request.read_edge_events():
                        print(
                            "line_gpio_pin: {}  type: {:<7}  event #{}".format(
                                event.line_offset, edge_type_str(event), event.line_seqno
                            )
                        )
                
        finally:
            poll.unregister(request.fd)
try:
    async_watch_line_value(chip_address, motion_sensor_PIN)
    
except OSError as ex:
    print(ex, "\nCustomise the example configuration to suit your situation")




## simple get value:
lines_req = gpiod.request_lines('/dev/gpiochip4', consumer="sensor", config={motion_sensor_PIN: gpiod.LineSettings(direction=Direction.INPUT)},)
value = lines_req.get_value(motion_sensor_PIN)
print(value)

exit()
