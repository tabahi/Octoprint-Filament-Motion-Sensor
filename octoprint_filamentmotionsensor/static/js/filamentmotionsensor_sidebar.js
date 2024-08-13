$(function(){
    function FilamentMotionSensorSidebarViewModel(parameters){
        var self = this;

        self.settingsViewModel = parameters[0];

        self.remainingDistance = ko.observable(undefined);
        self.StatusFlag = ko.observable(undefined);
        self.StatusFlagText = ko.observable(undefined);
        self.lastMotionDetected = ko.observable(undefined);
        self.isFilamentMoving = ko.observable(undefined);
        self.isConnectionTestRunningBool = ko.observable(undefined);

        //Returns the value in Yes/No if the Sensor is enabled 
        self.isSensorEnabled = function(){
            return self.settingsViewModel.settings.plugins.filamentmotionsensor.motion_sensor_enabled();
        };
        



var status_flags = {
    "PRINTER ERROR": -10,
    "PAUSED. HEATERS OFF": -6,
    "PAUSED. HEATERS UNSURE": -5,
    "PAUSED. EXTRINSIC": -4,
    "PAUSED ON RESUME. T0 LOW": -3,
    "PAUSED. JAMMED.": -2,
    "OFF": -1,
    "PAUSED": 0,
    "WAITING Z MOVE": 4,
    "WAITING E MOVE": 6,
    "WAITING START DELAY": 9,
    "MONITORING": 10,
    "ANTICIPATING_JAM": 11,
    "TIMEOUT 10s LEFT": 12,
    "DIST REACHED. GRACE PERIOD": 20,
    "DIST REACHED. TIMEOUT 10s ": 22,
    "DIST REACHED. STOP ASAP.": 25,
    "MAX TIMEOUT. STOP ASAP.": 26,
    "JAMMED. AWAITING MOTION": 30,
};

;

        self.onDataUpdaterPluginMessage = function(plugin, data){
            if(plugin !== "filamentmotionsensor"){
                return;
            }
            
            var message = JSON.parse(data);
            self.remainingDistance( String(Math.round(message["_remaining_distance"])) + "mm" );
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
            else self.lastMotionDetected(seconds_gone_by.toString() + "s ago");

            if(message["_filament_moving"] == true){
                self.isFilamentMoving(true);
            }
            else{
                self.isFilamentMoving(false);
            }

            if(message["_connection_test_running"] == true){
                
                self.isConnectionTestRunningBool(true);
            }
            else{
                
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
