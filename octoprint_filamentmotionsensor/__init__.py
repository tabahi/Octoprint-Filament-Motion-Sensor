# coding=utf-8
from __future__ import absolute_import
import octoprint.plugin
from octoprint.events import Events
#import RPi.GPIO as GPIO
#import gpiod
#from datetime import datetime
import time
import flask
from .SensorGPIOThread import MotionSensorGPIOThread
from .SensorGPIOThread import plugin_check_rpi_gpio
from .data import FilamentMotionSensorDetectionData
import os.path
_debug_in_terminal = False # send debug messages in Gcode terminal

gcode_file_path = os.path.join(os.path.dirname(os.path.realpath(__file__)), "data", "custom_ending.gcode")

status_flags = {
                "PRINTER_ERROR": -10,
                "PAUSED_HEATERS_OFF": -6,
                "PAUSED_HEATERS_UNSURE": -5,
                "PAUSED_EXTRINSIC": -4,
                "PAUSED_ON_RESUME_T0_LOW": -3,
                "PAUSED_JAMMED": -2,
                "OFF": -1,
                "PAUSED": 0,
                "WAITING_Z_MOVE": 4,
                "WAITING_E_MOVE": 6,
                "WAITING_START_DELAY": 9,
                "MONITORING": 10,
                "ANTICIPATING_JAM": 11,
                "TIMEOUT_10S_LEFT": 12,
                "DIST_REACHED_GRACE_PERIOD": 20,
                "TIMEOUT_10S_LEFT_DIST_REACHED": 22,
                "DIST_REACHED_STOP_ASAP": 25,
                "MAX_TIMEOUT_STOP_ASAP": 26,
                "JAMMED_AWAITING_MOTION": 30,
}

class FilamentMotionSensor(octoprint.plugin.StartupPlugin,
                                 octoprint.plugin.EventHandlerPlugin,
                                 octoprint.plugin.TemplatePlugin,
                                 octoprint.plugin.SettingsPlugin,
                                 octoprint.plugin.AssetPlugin,
                                 octoprint.plugin.SimpleApiPlugin):

    def initialize(self):
        
        self.last_movement_time = time.time()
        self.lastE = -1
        self.currentE = -1
        self.START_DISTANCE_OFFSET = 7
        self.print_start_time = 0
        self.print_pause_time = 0
        self.last_pause_t0 = -255
        self.code_sent = False
        self.trigger_custom_gcode = False
        self.t0_temp = -255
        self.last_temp_time = 0
        self.hook_it = True
        
        self._data = FilamentMotionSensorDetectionData(self.motion_sensor_detection_distance, True, self.updateToUi)
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


# Addess features in V2
    @property
    def motion_sensor_max_not_moving_after_dist(self):
        return int(self._settings.get(["motion_sensor_max_not_moving_after_dist"]))


    @property
    def initial_delay(self):
        return int(self._settings.get(["initial_delay"]))
    
    @property
    def heaters_timeout(self):
        return int(self._settings.get(["heaters_timeout"]))
        
        


#General Properties
    @property
    def mode(self):
        return int(self._settings.get(["mode"]))

    #@property
    #def send_gcode_only_once(self):
    #    return self._settings.get_boolean(["send_gcode_only_once"])

# Initialization methods
    def _setup_sensor(self):
        
        self._logger.info("Using BCM Mode ONLY")
        
        if self.motion_sensor_enabled == False:
            self._logger.info("Motion sensor is deactivated")

        self._data.filament_moving = False
        self.motion_sensor_thread = None

        self.load_filament_sensor_data()


    def load_filament_sensor_data(self):
        self._data.remaining_distance = self.motion_sensor_detection_distance

    def on_after_startup(self):
        self._logger.info("Filament Motion Sensor started")
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
            motion_sensor_max_not_moving=20,  # Maximum time no movement is detected - default continously
            motion_sensor_max_not_moving_after_dist=10,   # Maximum grace time after extrusion distance limit reached
            initial_delay = 60,
            heaters_timeout = 20,
            pause_command="@pause",
            #send_gcode_only_once=False,  # Default set to False for backward compatibility
        )

    def on_settings_save(self, data):
        octoprint.plugin.SettingsPlugin.on_settings_save(self, data)
        self._setup_sensor()

    def get_template_configs(self):
        return [dict(type="settings", custom_bindings=True)]

    def get_assets(self):
        return dict(js=["js/filamentmotionsensor_sidebar.js", "js/filamentmotionsensor_settings.js"])

# Sensor methods
    # Connection tests
    def stop_secondary_thread(self):
        try:
            if(self.motion_sensor_thread is None): self.motion_sensor_thread = None
        except: self.motion_sensor_thread  = None

        if (self.motion_sensor_thread is not None and (self.motion_sensor_thread.name == "ConnectionTest")):
            self.motion_sensor_thread.keepRunning = False
            self.motion_sensor_thread = None
            self._data.connection_test_running = False
            self._logger.info("stop_secondary_thread stopped")
            self._data.flag = status_flags["OFF"]
            
            if (_debug_in_terminal): self._printer.commands("echo: [Fsensor] stop_secondary_thread.")
        else:
            self._logger.info("stop_secondary_thread thread is not running")
            self._data.connection_test_running = False

    def start_connection_test(self):
        CONNECTION_TEST_TIME = 5
        try:
            if(self.motion_sensor_thread is None): self.motion_sensor_thread = None
        except: self.motion_sensor_thread  = None
        
        if(self.motion_sensor_thread is None):
            self.motion_sensor_thread = MotionSensorGPIOThread(1, "ConnectionTest", self.motion_sensor_pin,
                CONNECTION_TEST_TIME, self._logger, self._data, pCallback=self.connectionTestCallback)
            self.motion_sensor_thread.start()
            self._data.connection_test_running = True
            self._logger.info("Connection test monitor started. Thread name:" + str(self.motion_sensor_thread.name ))
    
   
            


    # Starts the motion sensor if the sensors are enabled
    def motion_sensor_start(self):
        self._logger.debug("Sensor enabled: " + str(self.motion_sensor_enabled))

        try:
            if(self.motion_sensor_thread is None): self.motion_sensor_thread = None
        except: self.motion_sensor_thread  = None

        if self.motion_sensor_enabled and (self.motion_sensor_pin>=0):
           
            self._logger.debug("GPIO mode: BCM Mode ONLY")
            self._logger.debug("GPIO pin: " + str(self.motion_sensor_pin))
            self.reset_distance()
            self._data.last_motion_detected = time.time()
            
            self._logger.info("Motion sensor started. dist:" +str(self.motion_sensor_detection_distance) + " time:" + str(self._data.last_motion_detected))
            self._logger.debug("Distance: " + str(self.motion_sensor_detection_distance))
            
            not_moving_return_seconds = 1
            if self.motion_sensor_thread == None:
                self._logger.debug("Max Timeout: " + str(self.motion_sensor_max_not_moving))

                
                self.motion_sensor_thread = MotionSensorGPIOThread(1, "MotionSensorTimeoutDetectionThread", self.motion_sensor_pin,
                    not_moving_return_seconds, self._logger, self._data, pCallback=self.sensor_event_callback)
                # Start Timeout_Detection thread
                self.motion_sensor_thread.start()
                

            self.code_sent = False
            self.trigger_custom_gcode = False
        else:
            self.motion_sensor_enabled = False
            if self.motion_sensor_thread is not None:
                self.motion_sensor_stop_thread()
        
    # Stop the motion_sensor thread
    def motion_sensor_stop_thread(self):
        try:
            if(self.motion_sensor_thread is None): self.motion_sensor_thread = None
        except: self.motion_sensor_thread  = None
        
        if(self.motion_sensor_thread is not None):
            if (_debug_in_terminal): self._printer.commands("echo: [Fsensor] motion_sensor_stop_thread.")
            self.motion_sensor_thread.keepRunning = False
            self.motion_sensor_thread = None
            self._logger.info("Motion sensor stopped")
        
        if (self._data.flag > status_flags["OFF"]):
            
            self._data.flag = status_flags["OFF"]


# Sensor callbacks - this is where the stopping conditions are coded.
# It is called when: 1) when sensor senses movement. [IO interrupt event]  2) when extruder extrudes more than it should [hooked event]
    def sensor_event_callback (self, pMoving=False):
        if (self._data.flag<status_flags["PAUSED"]):
            try:
                self.motion_sensor_thread.keepRunning = False
            except: pass
            self._data.filament_moving = False
            return
        self._data.filament_moving = pMoving
        
        if (not pMoving) and (self._data.flag>=status_flags["MONITORING"]) and (self._data.flag<status_flags["JAMMED_AWAITING_MOTION"]):
            calc_dur_no_move = (time.time() - self.last_movement_time)

            if ( ((self._data.flag==status_flags["DIST_REACHED_GRACE_PERIOD"] or self._data.flag==status_flags["TIMEOUT_10S_LEFT_DIST_REACHED"]) and (calc_dur_no_move > self.motion_sensor_max_not_moving_after_dist))):
                self._logger.info("DIST_REACHED_STOP_ASAP, last state: " + str(self._data.flag))
                self._data.flag = status_flags["DIST_REACHED_STOP_ASAP"]

            elif (calc_dur_no_move > self.motion_sensor_max_not_moving) and (self._data.flag < status_flags["MAX_TIMEOUT_STOP_ASAP"]):
                self._logger.info("MAX_TIMEOUT_STOP_ASAP, last state: " + str(self._data.flag))
                self._data.flag = status_flags["MAX_TIMEOUT_STOP_ASAP"]

            # 10 seconds to timeout
            elif (self._data.flag>=status_flags["MONITORING"]) and (self.motion_sensor_max_not_moving>=20) and (self._data.flag!=status_flags["TIMEOUT_10S_LEFT"] or self._data.flag!=status_flags["TIMEOUT_10S_LEFT_DIST_REACHED"]) and ( self.motion_sensor_max_not_moving - calc_dur_no_move <=11) and (self._data.flag < status_flags["MAX_TIMEOUT_STOP_ASAP"]):
                self._logger.info("10s to TIMEOUT, last state: " + str(self._data.flag))
                if (_debug_in_terminal): self._printer.commands("echo: [Fsensor] 10s to max timeout")
                if (self._data.flag==status_flags["DIST_REACHED_GRACE_PERIOD"]):
                    self._data.flag = status_flags["TIMEOUT_10S_LEFT_DIST_REACHED"]
                elif (self._data.flag==status_flags["MONITORING"]): self._data.flag = status_flags["TIMEOUT_10S_LEFT"]


            if(not self.code_sent) and ((self._data.flag == status_flags["DIST_REACHED_STOP_ASAP"]) or (self._data.flag == status_flags["MAX_TIMEOUT_STOP_ASAP"])):
                
                
                self._logger.info("Requesting Pause command: " + self.pause_command + " due to state: " + str(self._data.flag))
                self.code_sent = True
                self.lastE = -1 # Set to -1 so it ignores the first test then continues

                if (self.pause_command==";"): # only gcode WITHOUT octopause or cancel
                    if (_debug_in_terminal): self._printer.commands("echo: [Fsensor] gcode-only on clog.")
                    self._logger.info("JAMMED_AWAITING_MOTION, last state: " + str(self._data.flag))
                    self._data.flag = status_flags["JAMMED_AWAITING_MOTION"]
                    self.trigger_custom_gcode = False
                    self.send_custom_gcode_afterpause()
                else:
                    self._printer.commands(self.pause_command)
                    if (_debug_in_terminal):
                        self._printer.commands("echo: [Fsensor] pause command sent. State: " + str(self._data.flag))
                    #send_custom_gcode_afterpause() gcode will be sent after the pause event is confirmed
                    self.trigger_custom_gcode = True
                    self._logger.info("pause cmd sent, last state: " + str(self._data.flag))

        elif (pMoving):
            self.reset_distance() #self.code_sent = False
            if (self.code_sent):
                if (self._data.flag==status_flags["JAMMED_AWAITING_MOTION"]):
                    self.code_sent = False
                    self._data.flag = status_flags["WAITING_Z_MOVE"]
            elif (self._data.flag >= status_flags["ANTICIPATING_JAM"]):
                self._data.flag = status_flags["MONITORING"]
        '''
        # 10 seconds of no movement
        elif  (calc_dur_no_move >= 10) and (calc_dur_no_move<14):
            if (_debug_in_terminal): self._printer.commands("echo: [Fsensor] No movement for 10 seconds")
        
        # 60 seconds of no movement
        elif  (calc_dur_no_move >= 59) and (calc_dur_no_move<62):
            if (_debug_in_terminal): self._printer.commands("echo: [Fsensor] No movement for 60 seconds")
        '''

    # Reset the distance, if the remaining distance is smaller than the new value
    def reset_distance (self):
        
        self.code_sent = False
        self.last_movement_time = time.time()
        if(self._data.remaining_distance < self.motion_sensor_detection_distance):
            self._data.remaining_distance = self.motion_sensor_detection_distance
        elif(self._data.remaining_distance > self.motion_sensor_detection_distance*5): ## probably due to extrusion meter reset
            self._data.remaining_distance = self.motion_sensor_detection_distance

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

        # First check if need continue after last move
        if(self._data.remaining_distance > 0):

            # Calculate deltaDistance if absolute extrusion
            if (self._data.absolut_extrusion):
                # LastE is not used and set to the same value as currentE. Occurs on first run or after resuming
                if (self.lastE < 0):
                    self._logger.debug(f"Ignoring run with a negative value. Setting LastE to PE: {self.lastE} = {pE}")
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

            elif (deltaDistance < (self.motion_sensor_detection_distance*-1)):
                deltaDistance = 0
            '''
            self._logger.debug(
                f"Remaining: {self._data.remaining_distance} - Extruded: {deltaDistance} = {self._data.remaining_distance - deltaDistance}"
            )
            '''
            self._data.remaining_distance = (self._data.remaining_distance - deltaDistance)
            if (self._data.flag == status_flags["DIST_REACHED_GRACE_PERIOD"] or self._data.flag==status_flags["TIMEOUT_10S_LEFT_DIST_REACHED"]):
                self._data.flag = status_flags["MONITORING"]
                if (_debug_in_terminal): self._printer.commands("echo: [Fsensor] Filament distance top-up. Could be retractions.")
                self.sensor_event_callback(True)
        else:
            
            if (self._data.flag>status_flags["WAITING_START_DELAY"]): ## skip during initial delay
                ## this condition is redundant in sensor_event_callback
                if (time.time() - self.last_movement_time) > self.motion_sensor_max_not_moving_after_dist:
                    if (self._data.flag<status_flags["DIST_REACHED_STOP_ASAP"]):
                        if (_debug_in_terminal): self._printer.commands("echo: [Fsensor] Distance limit reached. Grace period timeout.")
                        self._data.flag = status_flags["DIST_REACHED_STOP_ASAP"]
                    self.sensor_event_callback(False)
                else:
                    if (self._data.flag>=status_flags["MONITORING"]) and (self._data.flag<status_flags["DIST_REACHED_GRACE_PERIOD"]):
                        if (_debug_in_terminal): self._printer.commands("echo: [Fsensor] Distance limit reached. Waiting for grace period. State:" +str(self._data.flag) )
                        self._data.flag = status_flags["DIST_REACHED_GRACE_PERIOD"]

    def updateToUi(self):
        self._plugin_manager.send_plugin_message(self._identifier, self._data.toJSON())

    def connectionTestCallback(self, pMoving=False):
        self._data.filament_moving = pMoving


    # Remove motion sensor thread if the print is paused
    def main_thread_cleanup(self, pEvent=""):
        
        if self.motion_sensor_enabled or (self.motion_sensor_thread is not None):
            self._logger.info("%s: Motion sensor cleanup." % (pEvent))
            try:
                self.motion_sensor_thread.keepRunning = False
            except: pass

            self.motion_sensor_stop_thread()
            self._data.filament_moving = False
    
# Events
    def on_event(self, event, payload):
        
        if event is Events.PRINT_STARTED:
            
            self.stop_secondary_thread()
            if (self._data.flag!=status_flags["OFF"]): self.main_thread_cleanup(event)
            if (self.motion_sensor_enabled) and (self.motion_sensor_pin>=0):
                self.reset_distance()
                self._data.flag = status_flags["WAITING_Z_MOVE"]
                
                self.init_distance_detection()
                self.print_start_time = time.time()
                self.print_pause_time = 0
                self.last_pause_t0 = -255
        elif event is Events.PRINT_RESUMED:
            if (self._data.connection_test_running): self.stop_secondary_thread()
            if (self.motion_sensor_enabled) and (self.motion_sensor_pin>=0):
                
                # check T0 before resuming after a pause
                if (self.t0_temp==-255) or ((self.last_pause_t0 > 0) and (self.t0_temp > (self.last_pause_t0-10))) or ((self.last_pause_t0 ==-255) and (self.t0_temp > 175) or (self._data.flag == status_flags["PAUSED_EXTRINSIC"]) or (self.pause_command!="@pause")):
                    self.main_thread_cleanup(event)
                    self.reset_distance()
                    self.init_distance_detection()
                    self._data.flag = status_flags["WAITING_E_MOVE"]
                else:
                    self._logger.info("Paused on resume because temperature too low: " + self.pause_command)
                    self._printer.commands(self.pause_command)
                    if (_debug_in_terminal):
                        self._printer.commands("echo: [Fsensor] print paused because temperature too low.")
                    self._data.flag = status_flags["PAUSED_ON_RESUME_T0_LOW"]
                # If distance detection is used reset the remaining distance, because otherwise the print is not resuming anymore
                #if(self.detection_method == 1):
                self.reset_remainin_distance()
                self.trigger_custom_gcode = False
        

        # Start motion sensor on first G1 command
        elif event is Events.Z_CHANGE:
            if(self._data.flag==status_flags["WAITING_Z_MOVE"]):
                self.main_thread_cleanup(event)
                self.reset_distance()
                self._data.flag = status_flags["WAITING_E_MOVE"]
        
        # Cancel or stop events
        elif event in (
            Events.PRINT_DONE,
            Events.PRINT_FAILED,
            Events.PRINT_CANCELLED,
            Events.PRINT_CANCELLING,
            Events.E_STOP,
        ):
            if (_debug_in_terminal): self._printer.commands("echo: [Fsensor] Print-end event " + str(event))
            
            self._logger.info("Print-end event. last state: " + str(self._data.flag))
            
            if self.motion_sensor_enabled and (self.motion_sensor_pin>=0):
                if (self._data.flag>status_flags["ANTICIPATING_JAM"]) and (self.trigger_custom_gcode):
                    self.trigger_custom_gcode = False
                    self.send_custom_gcode_afterpause()
                self.main_thread_cleanup(event)
                if (self._data.connection_test_running): self.stop_secondary_thread()
                
                self.updateToUi()
            self._data.flag = status_flags["OFF"]
            self.main_thread_cleanup(event)

        # Pause event detected
        elif (event is Events.PRINT_PAUSED) or (event is Events.FILAMENT_CHANGE):
            if (_debug_in_terminal): self._printer.commands("echo: [Fsensor] pause command ACK. State: " + str(self._data.flag))
            self._logger.info("Pause command ACK. last state: " + str(self._data.flag))

            if self.motion_sensor_enabled and (self.motion_sensor_pin>=0):
                if (self._data.flag!=status_flags["JAMMED_AWAITING_MOTION"]) and (self._data.flag>status_flags["ANTICIPATING_JAM"]):
                    # JAMMED_AWAITING_MOTION is when there is only-gcode, no octopause, in that case gcode has been already sent
                    if (self.trigger_custom_gcode):
                        self.trigger_custom_gcode = False
                        self.send_custom_gcode_afterpause()
                    enable_heaters_timeout = False
                    if(self._data.flag>=status_flags["PAUSED_JAMMED"]):
                        if (self.t0_temp > 100) or (self.t0_temp==-255):
                            enable_heaters_timeout = True
                        self._data.flag = status_flags["PAUSED_JAMMED"]
                    self.print_pause_time = time.time()
                    self.last_pause_t0 = self.t0_temp if (self.t0_temp > 180) else -255
                    if (enable_heaters_timeout):
                        self._data.flag = status_flags["PAUSED_JAMMED"]
                    elif (self._data.flag!=status_flags["PAUSED_ON_RESUME_T0_LOW"]):
                        if (_debug_in_terminal): self._printer.commands("echo: [Fsensor] Heaters unsure State: " + str(self._data.flag))
                        self._data.flag = status_flags["PAUSED_HEATERS_UNSURE"]
                else:
                    if (self._data.flag!=status_flags["PAUSED_ON_RESUME_T0_LOW"]):
                        self._data.flag = status_flags["PAUSED_EXTRINSIC"]
                    self.main_thread_cleanup(event)
            else:
                self.main_thread_cleanup(event)

        elif event is Events.USER_LOGGED_IN:
            if not (self.motion_sensor_enabled and (self.motion_sensor_pin>=0)): self.main_thread_cleanup(event)
            self.updateToUi()

        elif event in (
            Events.DISCONNECTED,
            Events.ERROR
        ): #critial errors. Try to turn off heaters after timeout if possible
            #if self.motion_sensor_enabled:
            self._logger.info("Printer disconnect or error. last state: " + str(self._data.flag))
            self._data.flag = status_flags["PRINTER_ERROR"]
            self.main_thread_cleanup(event)
            

    def send_custom_gcode_afterpause(self):
        
        self._logger.info("Sending custom GCODE. last state: " + str(self._data.flag))
        if (os.path.exists(gcode_file_path)):
            gcode_f = open(gcode_file_path, "r")
            gcode_Lines = gcode_f.readlines()
            if (_debug_in_terminal): self._printer.commands("echo: [Fsensor] sending custom Gcode commands. Total lines: " + str(len(gcode_Lines)))
            for line in gcode_Lines:
                if (len(line)>0):
                    self._printer.commands(line)
        else:
            self._logger.info("Custom GCODE not available")

    def test_custom_gcode_commands(self, gcode_Lines):
       
        if (_debug_in_terminal): self._printer.commands("echo: [Fsensor] TESTING custom Gcode commands. Total lines: " + str(len(gcode_Lines)))
        for line in gcode_Lines:
            if (len(line)>0):
                self._printer.commands(line)


# API commands
    def get_api_commands(self):
        return dict(
            startConnectionTest=[],
            stopConnectionTest=[],
            loadEndingGcode=[],
            testEndingGcode=[],
            saveEndingGcode=[],
        )

    def on_api_command(self, command, data):
        self._logger.info("API: " + command)
        if(command == "startConnectionTest"):
            self.start_connection_test()
            return flask.make_response("Started connection test", 204)
        elif(command == "stopConnectionTest"):
            self.stop_secondary_thread()
            return flask.make_response("Stopped connection test", 204)
            
        elif(command == "loadEndingGcode"):
            if (os.path.exists(gcode_file_path)):
                gcode_f = open(gcode_file_path, "r")
                gcode_f_contents = gcode_f.read()
            else:
                default_beeps_path = os.path.join(os.path.dirname(os.path.realpath(__file__)), "default_beeps.gcode")
                if (os.path.exists(default_beeps_path)):
                    gcode_f = open(default_beeps_path, "r")
                    gcode_f_contents = gcode_f.read()
                else: gcode_f_contents = "; No Gcode\n\n"
            response = flask.make_response(gcode_f_contents, 200)
            response.mimetype = "text/plain"
            return response
        elif(command == "testEndingGcode"):
            try:
                if (data["gcode_edited"] is not None):
                    if (len(data["gcode_edited"])>1):
                        self.test_custom_gcode_commands(data["gcode_edited"].splitlines())
                return flask.make_response(flask.jsonify({"resp": "commands exec"}), 201)
            except Exception as ex:
                return flask.make_response(flask.jsonify({"resp": "testing_failed", "error": str(ex)}), 501)
            
        elif(command == "saveEndingGcode"):
            try:
                if (data["gcode_edited"] is not None):
                    with open(gcode_file_path, "w") as gcode_f:
                        gcode_f.write(data["gcode_edited"])
                return flask.make_response(flask.jsonify({"resp": "saved"}), 201)
            except Exception as ex:
                return flask.make_response(flask.jsonify({"resp": "saving_failed", "error": str(ex)}), 501)
        else:
            return flask.make_response("Not found", 404)

# Plugin update methods
    def update_hook(self):
        return dict(
            filamentmotionsensor=dict(
                displayName="Filament Motion Sensor",
                displayVersion=self._plugin_version,

                # version check: github repository
                type="github_release",
                user="tabahi",
                repo="Octoprint-Filament-Motion-Sensor ",
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
                pip="https://github.com/tabahi/Octoprint-Filament-Motion-Sensor/archive/{target_version}.zip"
            )
        )

    # Interprete the GCode commands that are sent to the printer to print the 3D object
    # G92: Reset the distance detection values
    # G0 or G1: Caluclate the remaining distance
    def distance_detection(self, comm_instance, phase, cmd, cmd_type, gcode, *args, **kwargs):
        # Only performed if distance detection is used
        #if(self.detection_method == 1 and self.motion_sensor_enabled):
        if self.motion_sensor_enabled and (self.motion_sensor_pin>=0):
            # G0 and G1 for linear moves and G2 and G3 for circle movements
            if(gcode == "G0" or gcode == "G1" or gcode == "G2" or gcode == "G3"):
                commands = cmd.split(" ")

                for command in commands:
                    if command.startswith("E"):
                        extruder = command[1:]
                        #self._logger.debug("----- RUNNING calc_distance -----")
                        #self._logger.debug("Found extrude command in '" + cmd + "' with value: " + extruder)
                        extruder_float = float(extruder)
                        #if (extruder_float < 0):
                        #    pass
                            #self._logger.info("Extruder retracted: " + str(extruder_float))
                            #if (_debug_in_terminal): self._printer.commands("echo: [Fsensor] Extruder retracted by " + str(extruder_float))
                            #extruder_float *= 0.5 # only consider 50% of the negative extrusion ammount
                        self.calc_distance(extruder_float)

                        # set flag to extrusion started
                        if (self._data.flag==status_flags["WAITING_E_MOVE"]):
                            self._data.flag = status_flags["WAITING_START_DELAY"]
                        if (self._data.flag==status_flags["WAITING_START_DELAY"]) and ((time.time() - self.print_start_time) >= self.initial_delay):
                            self._data.flag = status_flags["MONITORING"]
                            self.init_distance_detection()
                            self.motion_sensor_start()
                        elif (self._data.flag == status_flags["PAUSED"]):
                            self.motion_sensor_start()
            # G92 reset extruder
            elif(gcode == "G92") and (self._data.flag  < status_flags["MONITORING"]):
                
                self.init_distance_detection()
                self._logger.debug("Found G92 command in '" + cmd + "' : Reset Extruders")

            # M82 absolut extrusion mode
            elif(gcode == "M82"):
                self._data.absolut_extrusion = True
                self._logger.debug("Found M82 command in '" + cmd + "' : Absolut extrusion")
                self.lastE = 0

            # M83 relative extrusion mode
            elif(gcode == "M83"):
                self._data.absolut_extrusion = False
                self._logger.debug("Found M83 command in '" + cmd + "' : Relative extrusion")
                self.lastE = 0

            
        return cmd


    


    def process_temperatures(self, comm, parsed_temps):
        
        try:
            self.t0_temp = parsed_temps["T0"][0]
        except: self.t0_temp = -255
        self.last_temp_time = time.time()
        
        if (self.heaters_timeout>=0) and (self._data.flag==status_flags["PAUSED_JAMMED"]) and ((self.print_pause_time!=0)):
            if (self.t0_temp > 100) or (self.t0_temp==-255):
                paused_dur = (time.time() - self.print_pause_time)
                #self._printer.commands("echo: paused time " + str(paused_dur)  + ",  "+ str(self.print_pause_time!=0) )
                if (paused_dur > (self.heaters_timeout*60)):
                    self._printer.commands("M104 S0 ; turn off extruder heating")
                    self._printer.commands("M140 S0 ; turn off bed heating")
                    if (_debug_in_terminal):
                        self._printer.commands("echo: [Fsensor] status:" + str(self._data.flag))
                        self._printer.commands("echo: [Fsensor] Turning off heaters")
                    self._printer.commands("M104 S0 ; turn off extruder heating")
                    self._printer.commands("M140 S0 ; turn off bed heating")
                    self._data.flag = status_flags["PAUSED_HEATERS_OFF"]
            else:
                if (self._data.flag!=status_flags["PAUSED_ON_RESUME_T0_LOW"]):
                    self._data.flag = status_flags["PAUSED_HEATERS_UNSURE"]
                if (self.t0_temp > 50):
                    self._printer.commands("M104 S0 ; turn off extruder heating")
                    self._printer.commands("M140 S0 ; turn off bed heating")

        return parsed_temps


__plugin_name__ = "Filament Motion Sensor"
__plugin_version__ = "2.1"
__plugin_pythoncompat__ = ">=2.7,<4"

def __plugin_load__():
    global __plugin_implementation__
    __plugin_implementation__ = FilamentMotionSensor()

    global __plugin_hooks__
    __plugin_hooks__ = {
        "octoprint.plugin.softwareupdate.check_config": __plugin_implementation__.update_hook,
        "octoprint.comm.protocol.gcode.sent": __plugin_implementation__.distance_detection,
        "octoprint.comm.protocol.temperatures.received": __plugin_implementation__.process_temperatures
    }



def __plugin_check__():
    try:
        import gpiod
    except ImportError:
        return False

    try:
        if (plugin_check_rpi_gpio()==False): return False
    except:
        return False


    return True