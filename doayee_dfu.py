import wx
import sys
import threading
import serial.tools.list_ports
import os
import esptool
from tkinter import *
from tkinter.ttk import *
from tkinter import filedialog
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

class FloowerUpgrader(Frame):

    ################################################################
    #                         INIT TASKS                           #
    ################################################################
    def __init__(self):
        super().__init__()

        self.firmwareFilename = StringVar()
        self.initFlags()
        self.initUI()

        print('Flooware Flasher')
        print('--------------------------------------------')

    def initFlags(self):
        '''Initialises the flags used to control the program flow'''
        self.ESPTOOL_BUSY = False

        self.ESPTOOLARG_SERIALPORT = 'Automatic'
        self.ESPTOOLARG_BAUD = '921600'
        self.ESPTOOLARG_APPPATH = None
        self.ESPTOOLARG_APPFLASH = True

        self.APPFILE_SELECTED = False

        self.ESPTOOLMODE_FLASH = False

    def initUI(self):
        '''Runs on application start to build the GUI'''

        self.master.title("Floower Upgrader")
        self.pack(fill=BOTH, expand=True)

        self.columnconfigure(0, pad=20)
        self.columnconfigure(1, weight=1)
        self.columnconfigure(2, pad=20)
        #self.rowconfigure(5, weight=1)
        self.rowconfigure(0, pad=10)
        self.rowconfigure(1, pad=10)

        ################################################################
        #                      FIRMWARE FILE NAME                      #
        ################################################################
        labelFirmware = Label(self, text="Flooware File:")
        labelFirmware.grid(row=0, column=0, sticky=W)
        firmwareFilenameEntry = Entry(self, textvariable=self.firmwareFilename, background="white", state="readonly")
        firmwareFilenameEntry.grid(row=0, column=1, sticky=E + W)
        buttonBrowse = Button(self, text="Browse", command=self.onBrowseFile)
        buttonBrowse.grid(row=0, column=2)

        ################################################################
        #                      SERIAL PORT                             #
        ################################################################
        labelSerial = Label(self, text="Serial Port:")
        labelSerial.grid(row=1, column=0, sticky=W)
        self.serialPortsCombo = Combobox(self, state="readonly", postcommand=self.onSerialPortSelect)
        self.serialPortsCombo.grid(row=1, column=1, sticky=E + W)
        self.updateSerialPortsValues()
        buttonBrowse = Button(self, text="Scan Ports", command=self.onSerialScan)
        buttonBrowse.grid(row=1, column=2)

        return

        area = Text(self)
        area.grid(row=1, column=0, columnspan=2, rowspan=4, padx=5, sticky=E + W + S + N)

        abtn = Button(self, text="Activate")
        abtn.grid(row=1, column=3)

        cbtn = Button(self, text="Close")
        cbtn.grid(row=2, column=3, pady=4)

        hbtn = Button(self, text="Help")
        hbtn.grid(row=5, column=0, padx=5)

        obtn = Button(self, text="OK")
        obtn.grid(row=5, column=3)


        self.mainPanel = wx.Panel(self)
        vbox = wx.BoxSizer(wx.VERTICAL)
        ################################################################
        #                   BEGIN APP DFU FILE GUI                     #
        ################################################################
        self.appDFUpanel = wx.Panel(self.mainPanel)
        hbox = wx.BoxSizer(wx.HORIZONTAL)

        self.firmwareText = wx.StaticText(self.appDFUpanel, label="Flooware File:", style=wx.ALIGN_LEFT)
        hbox.Add(self.firmwareText, 1, wx.ALL|wx.ALIGN_CENTER_VERTICAL, 0)

        self.appPathText = wx.TextCtrl(self.appDFUpanel, style=wx.TE_READONLY)
        self.appPathText.SetBackgroundColour('white')
        hbox.Add(self.appPathText,5,wx.ALL|wx.ALIGN_CENTER_VERTICAL,20)

        self.browseButton = wx.Button(parent=self.appDFUpanel, label='Browse...')
        self.browseButton.Bind(wx.EVT_BUTTON, self.on_app_browse_button)
        hbox.Add(self.browseButton, 1, wx.ALIGN_CENTER_VERTICAL, 0)

        vbox.Add(self.appDFUpanel, 1, wx.LEFT|wx.RIGHT|wx.EXPAND, 20)
        ################################################################
        #                   BEGIN SERIAL OPTIONS GUI                   #
        ################################################################
        self.serialPanel = wx.Panel(self.mainPanel)
        serialhbox = wx.BoxSizer(wx.HORIZONTAL)

        self.serialtext = wx.StaticText(self.serialPanel,label = "Serial Port:", style = wx.ALIGN_LEFT)
        serialhbox.Add(self.serialtext,1,wx.ALL|wx.ALIGN_CENTER_VERTICAL,0)

        self.serialChoice = wx.Choice(self.serialPanel)
        self.serialChoice.Bind(wx.EVT_CHOICE, self.on_serial_list_select)
        serialhbox.Add(self.serialChoice,5,wx.ALL|wx.ALIGN_CENTER_VERTICAL,20)
        self.populate_serial_choice()

        w = Combobox(self, values=['GB', 'UK'])
        w.pack();

        self.scanButton = wx.Button(parent=self.serialPanel, label='Rescan Ports')
        self.scanButton.Bind(wx.EVT_BUTTON, self.on_serial_scan_request)
        serialhbox.Add(self.scanButton,1,wx.ALL|wx.ALIGN_CENTER_VERTICAL,0)

        vbox.Add(self.serialPanel,1, wx.LEFT|wx.RIGHT|wx.EXPAND, 20)
        ################################################################
        #                   BEGIN FLASH BUTTON GUI                     #
        ################################################################
        self.actionPanel = wx.Panel(self.mainPanel)
        abox = wx.BoxSizer(wx.HORIZONTAL)

        self.flashButton = wx.Button(parent=self.actionPanel, label='Upgrade')
        self.flashButton.Bind(wx.EVT_BUTTON, self.on_flash_button)
        abox.Add(self.flashButton, 1, wx.ALL|wx.ALIGN_CENTER_VERTICAL, 10)

        self.browseButton = wx.Button(parent=self.actionPanel, label='Browse...')
        self.browseButton.Bind(wx.EVT_BUTTON, self.on_app_browse_button)
        abox.Add(self.browseButton, 1, wx.ALL | wx.ALIGN_CENTER_VERTICAL, 10)

        vbox.Add(self.actionPanel, 1, wx.LEFT|wx.RIGHT|wx.EXPAND, 20)
        ################################################################
        #                   BEGIN CONSOLE OUTPUT GUI                   #
        ################################################################
        self.consolePanel = wx.TextCtrl(self.mainPanel, style=wx.TE_MULTILINE|wx.TE_READONLY)
        self.consolePanel.SetBackgroundColour('black')
        self.consolePanel.SetForegroundColour('white')
        sys.stdout = RedirectText(self.consolePanel)

        vbox.Add(self.consolePanel, 5, wx.ALL|wx.EXPAND, 20)
        ################################################################
        #                ASSOCIATE PANELS TO SIZERS                    #
        ################################################################
        self.appDFUpanel.SetSizer(hbox)
        self.serialPanel.SetSizer(serialhbox)
        self.actionPanel.SetSizer(abox)
        self.mainPanel.SetSizer(vbox)

    ################################################################
    #                      UI EVENT HANDLERS                       #
    ################################################################
    def onSerialScan(self, event):
        # repopulate the serial port choices and update the selected port
        print('rescanning serial ports...')
        self.populate_serial_choice()
        print('serial choices updated')

    def updateSerialPortsValues(self):
        devices = self.list_serial_devices()
        devices.append('Automatic')

        self.serialPortsCombo["values"] = devices;
        for id, device in enumerate(devices, start=0):
            if device == self.ESPTOOLARG_SERIALPORT:
                self.serialPortsCombo.current(id)

    def onSerialPortSelect(self, event):
        print(event)
        #port = self.serialChoice.GetString(self.serialChoice.GetSelection())
        #self.ESPTOOLARG_SERIALPORT = self.serialChoice.GetString(self.serialChoice.GetSelection())
        #print('you chose '+port)

    def onBrowseFile(self):
        filename = filedialog.askopenfilename(title="Select a File", filetypes=(("Flooware files","*.bin"), ("all files","*.*")))
        if filename != "":
            self.APPFILE_SELECTED = True
            self.firmwareFilename.set(os.path.basename(filename))
            self.ESPTOOLARG_APPPATH = os.path.abspath(filename)
            print(self.ESPTOOLARG_APPPATH)

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
        except Exception as e:
            print(e)
            print('unexpected error, maybe you chose invalid files, or files which overlap')
            pass

        self.ESPTOOL_BUSY = False
        self.ESPTOOLMODE_FLASH = False


def main():
    window = Tk()
    window.title("Floower Upgrader")
    window.geometry('500x500')
    app = FloowerUpgrader()
    app.pack(padx=10, pady=10)
    window.mainloop()

    #app = wx.App()
    #window = dfuTool(None, title='Floower Upgrader')
    #window.Show()

    #app.MainLoop()

if __name__ == '__main__':
    main()
