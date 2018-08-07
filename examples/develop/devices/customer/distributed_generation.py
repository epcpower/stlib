__copyright__ = 'Copyright 2017, EPC Power Corp.'
__license__ = 'GPLv2+'


def referenced_files(raw_dict):
    return ()

class ReferenceSource:
    def __init__(self, frames, cmd, meas):
        self.frames = frames
        self.cmd = cmd
        self.meas = meas
        
def get_frame(widget):
    return widget.ui.command.signal_object.frame

class DeviceExtension:
    def __init__(self, device):
        self.device = device()

        self.dash = None
        self.combo = None
        self.command = None
        self.measured = None
        self.pump_reset_controller_signal = None
        self.ref_sources = {}
    
    def post(self):
        self.dash = self.device.ui.tabs.widget(0)
        self.setup = self.device.ui.tabs.widget(1)
        
        d = self.dash
        
        self.combo = d.power_current_combo
        self.command = d.stacked_command
        self.measured = d.stacked_measured
        
        self.ref_sources = {
            'Power':ReferenceSource(
                frames = (
                    get_frame(d.real_power_command), 
                    get_frame(d.reactive_power_command),
                ), 
                cmd=d.cmd_power, 
                meas=d.meas_current,
            ), 
            'Current':ReferenceSource(
                frames = (
                    get_frame(d.real_current_command),
                    get_frame(d.reactive_current_command),
                ), 
                cmd=d.cmd_current, 
                meas=d.meas_power,
            ), 
            'DC Control':ReferenceSource(
                frames = (
                    get_frame(d.dc_current_limit_command), 
                    get_frame(d.dc_voltage_limit_command),
                ), 
                cmd=d.cmd_dclink, 
                meas=d.meas_power,
            ), 
            'Voltage':ReferenceSource(
                frames = (d.voltage_droop_mode.ui.signal_object.frame,),
                cmd=d.cmd_power, 
                meas=d.meas_current,
            )
        }
        
        d.voltage_droop_mode.ui.setVisible(False)
        
        self.combo.currentTextChanged.connect(self.combo_changed)
        
        for r in self.ref_sources:
            self.combo.addItem(r)

        self.setup.pump_reset_button.value.pressed.connect(
            self.setup.pump_reset_controller_button.pressed
        )
        self.setup.pump_reset_button.value.released.connect(
            self.setup.pump_reset_controller_button.released
        )

    def combo_changed(self, text):
        active_ref = self.ref_sources[text]
        self.command.setCurrentWidget(active_ref.cmd)
        self.measured.setCurrentWidget(active_ref.meas)
        for k, v in self.ref_sources.items():
            for frame in v.frames:
                frame.block_cyclic = text != k

        show_power_cmd = (text != 'Voltage')
        for widget in (self.dash.real_power_command, 
                       self.dash.reactive_power_command):
            widget.ui.command.setVisible(show_power_cmd)
            widget.ui.echo.setVisible(show_power_cmd)

