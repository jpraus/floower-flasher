import wx
import sys
import threading
import serial.tools.list_ports
import os
import esptool
from serial import SerialException
from esptool import FatalError
import argparse

# this class credit marcelstoer
# See discussion at http://stackoverflow.com/q/41101897/131929
class RedirectText:
    def __init__(self, text_ctrl):
        self.out = text_ctrl
        self.pending_backspaces = 0

    def write(self, string):
        new_string = ""
        number_of_backspaces = 0
        for c in string:
            if c == "\b":
                number_of_backspaces += 1
            else:
                new_string += c

        if self.pending_backspaces > 0:
            # current value minus pending backspaces plus new string
            new_value = self.out.GetValue()[:-1 * self.pending_backspaces] + new_string
            wx.CallAfter(self.out.SetValue, new_value)
        else:
            wx.CallAfter(self.out.AppendText, new_string)

        self.pending_backspaces = number_of_backspaces

    def flush(self):
        None

class dfuTool(wx.Frame):

    ################################################################
    #                         INIT TASKS                           #
    ################################################################
    def __init__(self, parent, title):
        super(dfuTool, self).__init__(parent, title=title)

        self.SetSize(600, 550)
        self.SetMinSize(wx.Size(600, 500))
        self.Centre()
        self.initFlags()
        self.initUI()
        print('Doayee ESP32 Firmware Flasher')
        print('--------------------------------------------')

    def initUI(self):
        '''Runs on application start to build the GUI'''

        self.mainPanel = wx.Panel(self)
        vbox = wx.BoxSizer(wx.VERTICAL)
        ################################################################
        #                   BEGIN SERIAL OPTIONS GUI                   #
        ################################################################
        self.serialPanel = wx.Panel(self.mainPanel)
        serialhbox = wx.BoxSizer(wx.HORIZONTAL)

        self.serialtext = wx.StaticText(self.serialPanel,label = "Serial Port:", style = wx.ALIGN_CENTRE)
        serialhbox.Add(self.serialtext,0.5,wx.ALL|wx.ALIGN_CENTER_VERTICAL,20)

        self.serialChoice = wx.Choice(self.serialPanel)
        self.serialChoice.Bind(wx.EVT_CHOICE, self.on_serial_list_select)
        serialhbox.Add(self.serialChoice,3,wx.ALL|wx.ALIGN_CENTER_VERTICAL,20)
        self.populate_serial_choice()

        self.scanButton = wx.Button(parent=self.serialPanel, label='Rescan Ports')
        self.scanButton.Bind(wx.EVT_BUTTON, self.on_serial_scan_request)
        serialhbox.Add(self.scanButton,2,wx.ALL|wx.ALIGN_CENTER_VERTICAL,20)

        vbox.Add(self.serialPanel,1, wx.LEFT|wx.RIGHT|wx.EXPAND, 20)
        ################################################################
        #                   BEGIN APP DFU FILE GUI                     #
        ################################################################
        self.appDFUpanel = wx.Panel(self.mainPanel)
        self.appDFUpanel.SetBackgroundColour('white')
        hbox = wx.BoxSizer(wx.HORIZONTAL)

        self.app_pathtext = wx.StaticText(self.appDFUpanel,label = "No File Selected", style = wx.ALIGN_LEFT|wx.ALIGN_CENTER_VERTICAL)
        hbox.Add(self.app_pathtext,5,wx.ALL|wx.ALIGN_CENTER_VERTICAL,10)

        self.browseButton = wx.Button(parent=self.appDFUpanel, label='Browse...')
        self.browseButton.Bind(wx.EVT_BUTTON, self.on_app_browse_button)
        hbox.Add(self.browseButton, 1, wx.ALL|wx.ALIGN_CENTER_VERTICAL, 10)

        vbox.Add(self.appDFUpanel,1,wx.LEFT|wx.RIGHT|wx.EXPAND, 20)
        ################################################################
        #                   BEGIN FLASH BUTTON GUI                     #
        ################################################################
        self.flashButton = wx.Button(parent=self.mainPanel, label='Flash')
        self.flashButton.Bind(wx.EVT_BUTTON, self.on_flash_button)

        vbox.Add(self.flashButton,1, wx.LEFT|wx.RIGHT|wx.EXPAND, 20)
        ################################################################
        #                   BEGIN CONSOLE OUTPUT GUI                   #
        ################################################################
        self.consolePanel = wx.TextCtrl(self.mainPanel, style=wx.TE_MULTILINE|wx.TE_READONLY)
        self.consolePanel.SetBackgroundColour('black')
        self.consolePanel.SetForegroundColour('white')
        sys.stdout = RedirectText(self.consolePanel)

        vbox.Add(self.consolePanel,5, wx.ALL|wx.EXPAND, 20)
        ################################################################
        #                ASSOCIATE PANELS TO SIZERS                    #
        ################################################################
        self.appDFUpanel.SetSizer(hbox)
        self.serialPanel.SetSizer(serialhbox)
        self.mainPanel.SetSizer(vbox)

    def initFlags(self):
        '''Initialises the flags used to control the program flow'''
        self.ESPTOOL_BUSY = False

        self.ESPTOOLARG_SERIALPORT = 'Automatic'
        self.ESPTOOLARG_BAUD = 921600 # this default is regrettably loaded as part of the initUI process
        self.ESPTOOLARG_APPPATH = None
        self.ESPTOOLARG_APPFLASH = True

        self.APPFILE_SELECTED = False

        self.ESPTOOLMODE_FLASH = False

    ################################################################
    #                      UI EVENT HANDLERS                       #
    ################################################################
    def on_serial_scan_request(self, event):
        # repopulate the serial port choices and update the selected port
        print('rescanning serial ports...')
        self.populate_serial_choice()
        print('serial choices updated')

    def populate_serial_choice(self):
        devices = self.list_serial_devices()
        devices.append('Automatic')

        self.serialChoice.Clear()
        for device in devices:
            self.serialChoice.Append(device)
            if device == self.ESPTOOLARG_SERIALPORT:
                self.serialChoice.SetSelection(self.serialChoice.GetCount() - 1)

    def on_serial_list_select(self,event):
        port = self.serialChoice.GetString(self.serialChoice.GetSelection())
        self.ESPTOOLARG_SERIALPORT = self.serialChoice.GetString(self.serialChoice.GetSelection())
        print('you chose '+port)

    def on_app_browse_button(self, event):
        with wx.FileDialog(self, "Open", "", "","*.bin", wx.FD_OPEN | wx.FD_FILE_MUST_EXIST) as fileDialog:

            if fileDialog.ShowModal() == wx.ID_CANCEL:
                return

            path = fileDialog.GetPath()
            self.APPFILE_SELECTED = True

        self.app_pathtext.SetLabel(os.path.basename(path))
        self.ESPTOOLARG_APPPATH=os.path.abspath(path)

    def on_flash_button(self, event):
        if self.ESPTOOL_BUSY:
            print('currently busy')
            return
        # handle cases where a flash has been requested but no file provided
        elif self.ESPTOOLARG_APPFLASH & ~self.APPFILE_SELECTED:
            print('no app selected for flash')
            return
        else:
            self.ESPTOOLMODE_FLASH = True
            t = threading.Thread(target=self.esptoolRunner, daemon=True)
            t.start()

    ################################################################
    #                      MISC FUNCTIONS                          #
    ################################################################
    def list_serial_devices(self):
        ports = serial.tools.list_ports.comports()
        ports.sort()
        devices = []
        for port in ports:
            devices.append(port.device)
        return devices

    ################################################################
    #                    ESPTOOL FUNCTIONS                         #
    ################################################################
    def esptool_cmd_builder(self):
        '''Build the command that we would give esptool on the CLI'''
        cmd = ['--baud',self.ESPTOOLARG_BAUD]

        if self.ESPTOOLARG_SERIALPORT != 'Automatic':
            cmd = cmd + ['--port',self.ESPTOOLARG_SERIALPORT]

        if self.ESPTOOLMODE_FLASH:
            cmd.append('write_flash')
            if self.ESPTOOLARG_APPFLASH:
                cmd.append('0x10000')
                cmd.append(self.ESPTOOLARG_APPPATH)

        return cmd

    def esptoolRunner(self):
        '''Handles the interaction with esptool'''
        self.ESPTOOL_BUSY = True

        cmd = self.esptool_cmd_builder()
        try:
            esptool.main(cmd)
            print('esptool execution completed')
        except esptool.FatalError as e:
            print(e)
            pass
        except serial.SerialException as e:
            print(e)
            pass
        except:
            print('unexpected error, maybe you chose invalid files, or files which overlap')
            pass

        self.ESPTOOL_BUSY = False
        self.ESPTOOLMODE_FLASH = False


def main():

    app = wx.App()
    window = dfuTool(None, title='Floower Upgrader')
    window.Show()

    app.MainLoop()

if __name__ == '__main__':
    main()
