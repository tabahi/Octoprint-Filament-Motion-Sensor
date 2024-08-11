$(function(){
    function FilamentMotionSensorSettingsViewModel(parameters){
        var self = this;
        self.settingsViewModel = parameters[0];
        self.printerStateViewModel = parameters[1];
        self.connectionTestDialog = undefined;
        self.customGCodeDialog = undefined;
        self.filamentmotionsensor_custom_gcode = undefined;
        self.filamentmotionsensor_save_gcode = undefined;

        self.remainingDistance = ko.observable(undefined);
        self.lastMotionDetected = ko.observable(undefined);
        self.isFilamentMoving = ko.observable(undefined);
        self.isConnectionTestRunning = ko.observable(false);

        self.onStartup = function() {
            self.connectionTestDialog = $("#settings_plugin_filamentmotionsensor_connectiontest");
            self.customGCodeDialog = $("#settings_plugin_filamentmotionsensor_customGCodeDialog");

            
            self.filamentmotionsensor_custom_gcode = $("#filamentmotionsensor_custom_gcode");
            self.filamentmotionsensor_save_gcode = $("#filamentmotionsensor_save_gcode");
            self.filamentmotionsensor_test_gcode = $("#filamentmotionsensor_test_gcode");
            self.filamentmotionsensor_custom_gcode.prop('disabled', true);
            self.filamentmotionsensor_save_gcode.prop('disabled', true);
            self.filamentmotionsensor_test_gcode.prop('disabled', true);
        };
        
        self.showConnectionTest = function() {
            self.connectionTestDialog.modal({
                show: true
            });
        };

        self.showGCodeEditor = function() {
            console.log("showGCodeEditor");
            self.filamentmotionsensor_custom_gcode.prop('disabled', true);
            self.filamentmotionsensor_save_gcode.prop('disabled', true);


            $.ajax({
                url: API_BASEURL + "plugin/filamentmotionsensor",
                type: "POST",
                dataType: "text",
                data: JSON.stringify({ "command": "loadEndingGcode" }),
                contentType: "application/json"
              }).then(function (response) {
                
                if (response !== undefined)
                    filamentmotionsensor_custom_gcode.value = response;
                
                self.filamentmotionsensor_custom_gcode.prop('disabled', false);
                self.filamentmotionsensor_save_gcode.prop('disabled', false);

              }).fail(function (jqXhr, status, error) {
                    alert("Unable to load the custom GCode.");
                    console.error(error);
                    self.filamentmotionsensor_custom_gcode.prop('disabled', false);
                    self.filamentmotionsensor_save_gcode.prop('disabled', false);
              });



            self.customGCodeDialog.modal({
                show: true
            });
            
        };

        
        self.save_custom_gcode = function() {
            console.log("Saving custom Gcode");
            self.filamentmotionsensor_custom_gcode.prop('disabled', true);
            self.filamentmotionsensor_save_gcode.prop('disabled', true);

            $.ajax({
                url: API_BASEURL + "plugin/filamentmotionsensor",
                type: "POST",
                dataType: "json",
                data: JSON.stringify({ "command": "saveEndingGcode" , "gcode_edited": filamentmotionsensor_custom_gcode.value}),
                contentType: "application/json"
              }).then(function (response) {
                
                if (response !== undefined)
                    console.log("Got respone:");
                    console.log(response);
                
                self.filamentmotionsensor_custom_gcode.prop('disabled', false);
                self.filamentmotionsensor_save_gcode.prop('disabled', false);

              }).fail(function (jqXhr, status, error) {
                    alert("Unable to save the custom GCode.");
                    console.error(error);
                    self.filamentmotionsensor_custom_gcode.prop('disabled', false);
                    self.filamentmotionsensor_save_gcode.prop('disabled', false);
              });
        };

        
        self.test_custom_gcode = function() {
            console.log("Testing custom Gcode");
            if (!confirm("Are you sure about runing these commands on your printer right now?")) return;
            self.filamentmotionsensor_custom_gcode.prop('disabled', false);
            self.filamentmotionsensor_test_gcode.prop('disabled', true);

            $.ajax({
                url: API_BASEURL + "plugin/filamentmotionsensor",
                type: "POST",
                dataType: "json",
                data: JSON.stringify({ "command": "testEndingGcode" , "gcode_edited": filamentmotionsensor_custom_gcode.value}),
                contentType: "application/json"
              }).then(function (response) {
                
                if (response !== undefined)
                    console.log("Got respone:");
                    console.log(response);
                
                self.filamentmotionsensor_test_gcode.prop('disabled', false);

              }).fail(function (jqXhr, status, error) {
                    alert("Unable to test the custom GCode.");
                    console.error(error);
                    self.filamentmotionsensor_test_gcode.prop('disabled', false);
              });
        };


        self.dummy = function() {
            alert("dummy");
        };

        self.onDataUpdaterPluginMessage = function(plugin, data){
            if(plugin !== "filamentmotionsensor"){
                return;
            }
            
            var message = JSON.parse(data);
            self.remainingDistance(message["_remaining_distance"]);
            self.lastMotionDetected(message["_last_motion_detected"]);
            self.isConnectionTestRunning(message["_connection_test_running"]);

            if(message["_filament_moving"] == true){
                self.isFilamentMoving("Movement detected");
            }
            else{
                self.isFilamentMoving("Not moving");
            }
        };


        self.enableCriticalSettings = ko.pureComputed(function() {
            return !self.printerStateViewModel.isBusy();
        });


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
        construct: FilamentMotionSensorSettingsViewModel,
        name: "FilamentMotionSensorSettingsViewModel",
        dependencies: ["settingsViewModel", "printerStateViewModel"],
        elements: ["#settings_plugin_filamentmotionsensor"]
    });
});
