$(function(){
    function SmartFilamentSensorSidebarViewModel(parameters){
        var self = this;

        self.settingsViewModel = parameters[0];
        //self.smartfilamentsensorSettings = self.settingsViewModel.settings.plugins.smartfilamentsensor;

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
            var sensorEnabled = self.settingsViewModel.settings.plugins.smartfilamentsensor.motion_sensor_enabled();

            if(sensorEnabled){
                return "Yes";
            }
            else{
                return "No";
            }
        };

        // Returns the value of detection_method as string
        self.getDetectionMethodString = function(){
            var detectionMethod = self.settingsViewModel.settings.plugins.smartfilamentsensor.detection_method();

            if(detectionMethod == 0){
                return "Timeout Detection";
            }
            else if(detectionMethod == 1){
                return "Distance Detection";
            }
        };

        self.getDetectionMethodBoolean = ko.pureComputed(function(){
            var detectionMethod = self.settingsViewModel.settings.plugins.smartfilamentsensor.detection_method();

            if(detectionMethod == 0){
                return false;
            }
            else if(detectionMethod == 1){
                return true;
            }
        });


        

        self.onDataUpdaterPluginMessage = function(plugin, data){
            if(plugin !== "smartfilamentsensor"){
                return;
            }
            
            var message = JSON.parse(data);
            self.remainingDistance( Math.round(message["_remaining_distance"]) );
            if (message["_print_status_flag"] !== undefined) 
                {
                    var status_int = message["_print_status_flag"];
                    self.StatusFlag( status_int);
                    if (status_int==-1) self.StatusFlagText("Off");
                    else if (status_int==0) self.StatusFlagText("Paused");
                    else if (status_int==1) self.StatusFlagText("Waiting for Z move");
                    else if (status_int==2) self.StatusFlagText("Waiting for extrusion");
                    else if (status_int==3) self.StatusFlagText("Monitoring");
                    else if (status_int==4) self.StatusFlagText("No motion grace period");
                }
            var seconds_gone_by = Math.round((new Date() - (new Date((message["_last_motion_detected"] * 1000)))) / 1000);
            self.lastMotionDetected(seconds_gone_by.toString() + "s");

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
                url: API_BASEURL + "plugin/smartfilamentsensor",
                type: "POST",
                dataType: "json",
                data: JSON.stringify({ "command": "startConnectionTest" }),
                contentType: "application/json",
                success: self.RestSuccess
            });
        };

        self.stopConnectionTest = function(){
            $.ajax({
                url: API_BASEURL + "plugin/smartfilamentsensor",
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
        construct: SmartFilamentSensorSidebarViewModel,
        name: "smartFilamentSensorSidebarViewModel",
        dependencies: ["settingsViewModel"],
        elements: ["#sidebar_plugin_smartfilamentsensor"]
    });
});
