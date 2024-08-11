# coding=utf-8
from __future__ import absolute_import
import octoprint.plugin
from octoprint.events import Events
#import RPi.GPIO as GPIO
import gpiod
from time import sleep
from datetime import datetime
import flask
import json
from octoprint_smart_filament_sensor.SensorGPIOThread import SmartFilamentSensorGPIOThread
from octoprint_smart_filament_sensor.data import SmartFilamentSensorDetectionData

class SmartFilamentSensor(octoprint.plugin.StartupPlugin,
                                 octoprint.plugin.EventHandlerPlugin,
                                 octoprint.plugin.TemplatePlugin,
                                 octoprint.plugin.SettingsPlugin,
                                 octoprint.plugin.AssetPlugin,
                                 octoprint.plugin.SimpleApiPlugin):

    def initialize(self):
        ''' depreciated
        self._logger.info("Running RPi.GPIO version '{0}'".format(GPIO.VERSION))
        if GPIO.VERSION < "0.6":       # Need at least 0.6 for edge detection
            raise Exception("RPi.GPIO must be greater than 0.6")
        GPIO.setwarnings(False)        # Disable GPIO warnings
        '''
        ###self.print_status_flag = -1
        self.last_movement_time = datetime.now()
        self.lastE = -1
        self.currentE = -1
        self.START_DISTANCE_OFFSET = 7
        self.code_sent = False
        self._data = SmartFilamentSensorDetectionData(self.motion_sensor_detection_distance, True, self.updateToUi)

#Properties
    @property
    def motion_sensor_pin(self):
        return int(self._settings.get(["motion_sensor_pin"]))

    @property
    def motion_sensor_pause_print(self):
        return self._settings.get_boolean(["motion_sensor_pause_print"])

    @property
    def detection_method(self):
        return int(self._settings.get(["detection_method"]))

    @property
    def motion_sensor_enabled(self):
        return self._settings.get_boolean(["motion_sensor_enabled"])

    @property
    def pause_command(self):
        return self._settings.get(["pause_command"])

#Distance detection
    @property
    def motion_sensor_detection_distance(self):
        return int(self._settings.get(["motion_sensor_detection_distance"]))

#Timeout detection regardless of extrusion
    @property
    def motion_sensor_max_not_moving(self):
        return int(self._settings.get(["motion_sensor_max_not_moving"]))

#Timeout after extrusion distance limit reached
    @property
    def motion_sensor_max_not_moving_after_dist(self):
        return int(self._settings.get(["motion_sensor_max_not_moving_after_dist"]))

#General Properties
    @property
    def mode(self):
        return int(self._settings.get(["mode"]))

    #@property
    #def send_gcode_only_once(self):
    #    return self._settings.get_boolean(["send_gcode_only_once"])

# Initialization methods
    def _setup_sensor(self):
        # Clean up before intializing again, because ports could already be in use

        #if(self.mode == 0):
        #    self._logger.info("Using Board Mode")
        #    #GPIO.setmode(GPIO.BOARD)
        #else:
        self._logger.info("Using BCM Mode ONLY")
        #GPIO.setmode(GPIO.BCM)

        #GPIO.setup(self.motion_sensor_pin, GPIO.IN)


        #self.detection_method = 0 ### CURRENTLY only timeout method
        '''
         Add reset_distance if detection_method is distance_detection
        if (self.detection_method == 1):
            # Remove event first, because it might been in use already
            try:
                GPIO.remove_event_detect(self.motion_sensor_pin)
            except:
                self._logger.warn("Pin " + str(self.motion_sensor_pin) + " not used before")

            GPIO.add_event_detect(self.motion_sensor_pin, GPIO.BOTH, callback=self.reset_distance)
        '''
        if self.motion_sensor_enabled == False:
            self._logger.info("Motion sensor is deactivated")

        self._data.filament_moving = False
        self.motion_sensor_thread = None

        self.load_smart_filament_sensor_data()


    def load_smart_filament_sensor_data(self):
        self._data.remaining_distance = self.motion_sensor_detection_distance

    def on_after_startup(self):
        self._logger.info("Smart Filament Sensor started")
        self._setup_sensor()

    def get_settings_defaults(self):
        return dict(
            #Motion sensor
            mode=0,    # Board Mode
            motion_sensor_enabled = True, #Sensor detection is enabled by default
            motion_sensor_pin=-1,  # Default is no pin
            detection_method = 0, # 0 = timeout detection, 1 = distance detection

            # Distance detection
            motion_sensor_detection_distance = 7, # Recommended detection distance from Marlin would be 7

            # Timeout detection
            motion_sensor_max_not_moving=120,  # Maximum time no movement is detected - default continously
            motion_sensor_max_not_moving_after_dist=20,   # Maximum grace time after extrusion distance limit reached
            pause_command="@pause",
            #send_gcode_only_once=False,  # Default set to False for backward compatibility
        )

    def on_settings_save(self, data):
        octoprint.plugin.SettingsPlugin.on_settings_save(self, data)
        self._setup_sensor()

    def get_template_configs(self):
        return [dict(type="settings", custom_bindings=True)]

    def get_assets(self):
        return dict(js=["js/smartfilamentsensor_sidebar.js", "js/smartfilamentsensor_settings.js"])

# Sensor methods
    # Connection tests
    def stop_connection_test(self):
        try:
            if(self.motion_sensor_thread is None): self.motion_sensor_thread = None
        except: self.motion_sensor_thread  = None

        if (self.motion_sensor_thread is not None and self.motion_sensor_thread.name == "ConnectionTest"):
            self.motion_sensor_thread.keepRunning = False
            self.motion_sensor_thread = None
            self._data.connection_test_running = False
            self._logger.info("Connection test stopped")
        else:
            self._logger.info("Connection test is not running")

    def start_connection_test(self):
        CONNECTION_TEST_TIME = 2
        try:
            if(self.motion_sensor_thread is None): self.motion_sensor_thread = None
        except: self.motion_sensor_thread  = None
        
        if(self.motion_sensor_thread is None):
            self.motion_sensor_thread = SmartFilamentSensorGPIOThread(1, "ConnectionTest", self.motion_sensor_pin,
                CONNECTION_TEST_TIME, self._logger, self._data, pCallback=self.connectionTestCallback)
            self.motion_sensor_thread.start()
            self._data.connection_test_running = True
            self._logger.info("Connection test started")

    # Starts the motion sensor if the sensors are enabled
    def motion_sensor_start(self):
        self._logger.debug("Sensor enabled: " + str(self.motion_sensor_enabled))

        try:
            if(self.motion_sensor_thread is None): self.motion_sensor_thread = None
        except: self.motion_sensor_thread  = None

        if self.motion_sensor_enabled and (self.motion_sensor_pin>=0):
            #if (self.mode == 0):
            #    self._logger.debug("GPIO mode: Board Mode")
            #else:
            self._logger.debug("GPIO mode: BCM Mode ONLY")
            self._logger.debug("GPIO pin: " + str(self.motion_sensor_pin))

            # Distance detection
            #if (self.detection_method == 1):
            self._logger.info("Motion sensor started")
            self._logger.debug("Distance: " + str(self.motion_sensor_detection_distance))
            self.reset_distance()
            # Timeout detection
            #elif (self.detection_method == 0):
                
            if self.motion_sensor_thread == None:
                self._logger.debug("Max Timeout: " + str(self.motion_sensor_max_not_moving))

                # Start Timeout_Detection thread
                self.motion_sensor_thread = SmartFilamentSensorGPIOThread(1, "MotionSensorTimeoutDetectionThread", self.motion_sensor_pin,
                    self.motion_sensor_max_not_moving, self._logger, self._data, pCallback=self.sensor_event_callback)
                self.motion_sensor_thread.start()
                

            self.code_sent = False
            self._data.filament_moving = True
        else:
            self.motion_sensor_enabled = False
            self._data.print_status_flag = -1
        
    # Stop the motion_sensor thread
    def motion_sensor_stop_thread(self):
        try:
            if(self.motion_sensor_thread is None): self.motion_sensor_thread = None
        except: self.motion_sensor_thread  = None
        
        if(self.motion_sensor_thread != None):
            self.motion_sensor_thread.keepRunning = False
            self.motion_sensor_thread = None
            self._logger.info("Motion sensor stopped")

# Sensor callbacks
    # Send configured pause command to the printer to interrupt the print
    def sensor_event_callback (self, pMoving=False):
        # Check if stop signal was already sent
        self._data.filament_moving = pMoving
        if (pMoving): self.reset_distance()

        if(not self.code_sent) and (not pMoving) and (self._data.print_status_flag>=3):
            self._logger.error("Motion sensor detected no movement")
            self._logger.info("Pause command: " + self.pause_command)
            self._printer.commands(self.pause_command)
            self.code_sent = True
            self._data.filament_moving = False
            self.lastE = -1 # Set to -1 so it ignores the first test then continues

    # Reset the distance, if the remaining distance is smaller than the new value
    def reset_distance (self):
        self._logger.info("Motion sensor reset_distance")
        self.code_sent = False
        self.last_movement_time = datetime.now()
        if(self._data.remaining_distance < self.motion_sensor_detection_distance):
            self._data.remaining_distance = self.motion_sensor_detection_distance
            self._data.filament_moving = True

    # Initialize the distance detection values
    def init_distance_detection(self):
        self.lastE = float(-1)
        self.currentE = float(0)
        self.reset_remainin_distance()

    # Reset the remaining distance on start or resume
    # START_DISTANCE_OFFSET is used for the (re-)start sequence
    def reset_remainin_distance(self):
        self._data.remaining_distance = (float(self.motion_sensor_detection_distance) + self.START_DISTANCE_OFFSET)

    # Calculate the remaining distance
    def calc_distance(self, pE):
        #if (self.detection_method == 1):

        # First check if need continue after last move
        if(self._data.remaining_distance > 0):

            # Calculate deltaDistance if absolute extrusion
            if (self._data.absolut_extrusion):
                # LastE is not used and set to the same value as currentE. Occurs on first run or after resuming
                if (self.lastE < 0):
                    self._logger.info(f"Ignoring run with a negative value. Setting LastE to PE: {self.lastE} = {pE}")
                    self.lastE = pE
                else:
                    self.lastE = self.currentE

                self.currentE = pE

                deltaDistance = self.currentE - self.lastE
                self._logger.debug( f"CurrentE: {self.currentE} - LastE: {self.lastE} = { round(deltaDistance,3) }" )

            # deltaDistance is just position if relative extrusion
            else:
                deltaDistance = float(pE)
                self._logger.debug( f"Relative Extrusion = { round(deltaDistance,3) }" )

            if(deltaDistance > self.motion_sensor_detection_distance):
                # Calculate the deltaDistance modulo the motion_sensor_detection_distance
                # Sometimes the polling of M114 is inaccurate so that with the next poll
                # very high distances are put back followed by zero distance changes

                #deltaDistance=deltaDistance / self.motion_sensor_detection_distance REMAINDER
                deltaDistance = deltaDistance % self.motion_sensor_detection_distance

            self._logger.debug(
                f"Remaining: {self._data.remaining_distance} - Extruded: {deltaDistance} = {self._data.remaining_distance - deltaDistance}"
            )
            self._data.remaining_distance = (self._data.remaining_distance - deltaDistance)
            if (self._data.print_status_flag > 3): self._data.print_status_flag = 3

        else:
            self._data.filament_moving = False
            # Only pause the print if its been over 5 seconds since the last movement. Stops pausing when the CPU gets hung up.
            if (datetime.now() - self.last_movement_time).total_seconds() > self.motion_sensor_max_not_moving_after_dist:
                self._logger.info("Filament sensor didn't move enough to account for extrusion")
                self.sensor_event_callback(False)
            else:
                self._data.print_status_flag = 4
                self._logger.debug("Ignored pause command due to 5 second rule")

    def updateToUi(self):
        self._plugin_manager.send_plugin_message(self._identifier, self._data.toJSON())

    def connectionTestCallback(self, pMoving=False):
        self._data.filament_moving = pMoving

    # Remove motion sensor thread if the print is paused
    def print_paused(self, pEvent=""):
        
        self._logger.info("%s: Pausing filament sensors." % (pEvent))
        if self.motion_sensor_enabled:# and self.detection_method == 0:
            self.motion_sensor_stop_thread()
            

# Events
    def on_event(self, event, payload):
        if event is Events.PRINT_STARTED:
            self.stop_connection_test()
            if (self.motion_sensor_enabled) and (self.motion_sensor_pin>=0):
                self._data.print_status_flag = 1
                #if(self.detection_method == 1):
            self.init_distance_detection()

        elif event is Events.PRINT_RESUMED:
            if (self.motion_sensor_enabled) and (self.motion_sensor_pin>=0):
                self._data.print_status_flag = 1

            # If distance detection is used reset the remaining distance, because otherwise the print is not resuming anymore
            #if(self.detection_method == 1):
            self.reset_remainin_distance()

            #self.motion_sensor_start()

        # Start motion sensor on first G1 command
        elif event is Events.Z_CHANGE:
            if(self._data.print_status_flag==1):
                #self.motion_sensor_start() # changed to begin after first extrusion
                self._data.print_status_flag = 2

        # Disable sensor
        elif event in (
            Events.PRINT_DONE,
            Events.PRINT_FAILED,
            Events.PRINT_CANCELLED,
            Events.ERROR
        ):
            self._logger.info("%s: Disabling filament sensors." % (event))
            self._data.print_status_flag = -1
            if self.motion_sensor_enabled:# and self.detection_method == 0:
                self.motion_sensor_stop_thread()

        # Disable motion sensor if paused
        elif event is Events.PRINT_PAUSED:
            if(self._data.print_status_flag>0):
                self._data.print_status_flag = 0
            self.print_paused(event)

        elif event is Events.USER_LOGGED_IN:
            self.updateToUi()

# API commands
    def get_api_commands(self):
        return dict(
            startConnectionTest=[],
            stopConnectionTest=[]
        )

    def on_api_command(self, command, data):
        self._logger.info("API: " + command)
        if(command == "startConnectionTest"):
            self.start_connection_test()
            return flask.make_response("Started connection test", 204)
        elif(command == "stopConnectionTest"):
            self.stop_connection_test()
            return flask.make_response("Stopped connection test", 204)
        else:
            return flask.make_response("Not found", 404)

# Plugin update methods
    def update_hook(self):
        return dict(
            smartfilamentsensor=dict(
                displayName="Smart Filament Sensor",
                displayVersion=self._plugin_version,

                # version check: github repository
                type="github_release",
                user="Royrdan",
                repo="Octoprint-Smart-Filament-Sensor",
                current=self._plugin_version,

                # stable releases
                stable_branch=dict(
					name="Stable",
					branch="master",
					comittish=["master"]
				),

				# release candidates
				prerelease_branches=[
					dict(
						name="Release Candidate",
						branch="PreRelease",
						comittish=["PreRelease"],
					)
				],

                # update method: pip
                pip="https://github.com/Royrdan/Octoprint-Smart-Filament-Sensor/archive/{target_version}.zip"
            )
        )

    # Interprete the GCode commands that are sent to the printer to print the 3D object
    # G92: Reset the distance detection values
    # G0 or G1: Caluclate the remaining distance
    def distance_detection(self, comm_instance, phase, cmd, cmd_type, gcode, *args, **kwargs):
        # Only performed if distance detection is used
        #if(self.detection_method == 1 and self.motion_sensor_enabled):
        if(self.motion_sensor_enabled):
            # G0 and G1 for linear moves and G2 and G3 for circle movements
            if(gcode == "G0" or gcode == "G1" or gcode == "G2" or gcode == "G3"):
                commands = cmd.split(" ")

                for command in commands:
                    if command.startswith("E"):
                        extruder = command[1:]
                        self._logger.debug("----- RUNNING calc_distance -----")
                        self._logger.debug("Found extrude command in '" + cmd + "' with value: " + extruder)
                        self.calc_distance(float(extruder))

                        # set flag to extrusion started
                        if (self._data.print_status_flag==2):
                            self.motion_sensor_start()
                            self._data.print_status_flag = 3

            # G92 reset extruder
            elif(gcode == "G92"):
                #if(self.detection_method == 1):
                self.init_distance_detection()
                self._logger.debug("Found G92 command in '" + cmd + "' : Reset Extruders")

            # M82 absolut extrusion mode
            elif(gcode == "M82"):
                self._data.absolut_extrusion = True
                self._logger.info("Found M82 command in '" + cmd + "' : Absolut extrusion")
                self.lastE = 0

            # M83 relative extrusion mode
            elif(gcode == "M83"):
                self._data.absolut_extrusion = False
                self._logger.info("Found M83 command in '" + cmd + "' : Relative extrusion")
                self.lastE = 0

        return cmd


__plugin_name__ = "Smart Filament Sensor V2"
__plugin_version__ = "2.1"
__plugin_pythoncompat__ = ">=2.7,<5"

def __plugin_load__():
    global __plugin_implementation__
    __plugin_implementation__ = SmartFilamentSensor()

    global __plugin_hooks__
    __plugin_hooks__ = {
        "octoprint.plugin.softwareupdate.check_config": __plugin_implementation__.update_hook,
        "octoprint.comm.protocol.gcode.sent": __plugin_implementation__.distance_detection
    }



def __plugin_check__():
    try:
        #import RPi.GPIO
        import gpiod
    except ImportError:
        return False

    return True