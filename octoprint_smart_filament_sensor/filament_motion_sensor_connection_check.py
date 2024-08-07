#!/usr/bin/python3
######################
##                  ##
##  Instructions    ##
##                  ##
######################
##
##  - Run this script on the OctoPi
##  - python3 filament_motion_sensor_connection_check.py
##  - To save some filament you can unload the filament
##      before and move it manually in the sensor

import RPi.GPIO as GPIO
import time

#CONST
# Configure your GPIO pin
USED_PIN = 11
GPIO.setmode(GPIO.BOARD)
#GPIO.setmode(GPIO.BCM)
# Time in seconds
max_not_moving_time = 2
# Set up the GPIO channels - one input and one output
GPIO.setup(USED_PIN, GPIO.IN)

lastValue = GPIO.input(USED_PIN)
# Get current time in seconds
lastMotion = time.time()

def main():
	try: 
		GPIO.add_event_detect(USED_PIN, GPIO.BOTH, callback=motion)

		while True:
			timespan = (time.time() - lastMotion)

			if (timespan > max_not_moving_time):
				print("No motion detected")
			else:
				print ("Moving")

			time.sleep(0.250)
		
		GPIO.remove_event_detect(USED_PIN)
	except KeyboardInterrupt:
		print ("Done")
		pass


def motion(pPin):
	global lastMotion
	lastMotion = time.time()
	print("Motion detected at " + str(lastMotion))

main()