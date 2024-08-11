$(function(){
    function FilamentMotionSensorSidebarViewModel(parameters){
        var self = this;

        self.settingsViewModel = parameters[0];

        self.isSensorEnabled = ko.observable(undefined);
        self.remainingDistance = ko.observable(undefined);
        self.StatusFlag = ko.observable(undefined);
        self.StatusFlagText = ko.observable(undefined);
        self.lastMotionDetected = ko.observable(undefined);
        self.isFilamentMoving = ko.observable(undefined);
        self.isConnectionTestRunning = ko.observable(false);
        self.isConnectionTestRunningBool = ko.observable(undefined);

        //Returns the value in Yes/No if the Sensor is enabled 
        self.getSensorEnabledString = function(){
            var sensorEnabled = self.settingsViewModel.settings.plugins.filamentmotionsensor.motion_sensor_enabled();

            if(sensorEnabled){
                return "Yes";
            }
            else{
                return "No";
            }
        };
        



var status_flags = {
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
};

;

        self.onDataUpdaterPluginMessage = function(plugin, data){
            if(plugin !== "filamentmotionsensor"){
                return;
            }
            
            var message = JSON.parse(data);
            self.remainingDistance( Math.round(message["_remaining_distance"]) );
            if (message["_flag"] !== undefined) 
                {
                    var status_int = message["_flag"];
                    self.StatusFlag( status_int);
                    const key = Object.keys(status_flags).find(key => status_flags[key] === status_int);
                    self.StatusFlagText(String(key));
                }
            var seconds_gone_by = Math.round((new Date() - (new Date((message["_last_motion_detected"] * 1000)))) / 1000);
            if (seconds_gone_by<0) seconds_gone_by = 0;
            if (seconds_gone_by>99999)  self.lastMotionDetected("Never");
            else self.lastMotionDetected(seconds_gone_by.toString() + "s");

            if(message["_filament_moving"] == true){
                self.isFilamentMoving("Yes");
            }
            else{
                self.isFilamentMoving("No");
            }

            if(message["_connection_test_running"] == true){
                self.isConnectionTestRunning("Running");
                
                self.isConnectionTestRunningBool(true);
            }
            else{
                self.isConnectionTestRunning("Stopped");
                
                self.isConnectionTestRunningBool(false);
            }
        };

        self.startConnectionTest = function(){
            $.ajax({
                url: API_BASEURL + "plugin/filamentmotionsensor",
                type: "POST",
                dataType: "json",
                data: JSON.stringify({ "command": "startConnectionTest" }),
                contentType: "application/json",
                success: self.RestSuccess
            });
        };

        self.stopConnectionTest = function(){
            $.ajax({
                url: API_BASEURL + "plugin/filamentmotionsensor",
                type: "POST",
                dataType: "json",
                data: JSON.stringify({ "command": "stopConnectionTest" }),
                contentType: "application/json",
                success: self.RestSuccess
            });
        };

        self.RestSuccess = function(response){
            return;
        }
    }

    OCTOPRINT_VIEWMODELS.push({
        construct: FilamentMotionSensorSidebarViewModel,
        name: "FilamentMotionSensorSidebarViewModel",
        dependencies: ["settingsViewModel"],
        elements: ["#sidebar_plugin_filamentmotionsensor"]
    });
});
