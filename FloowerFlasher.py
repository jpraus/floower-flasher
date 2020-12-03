import threading
import serial.tools.list_ports
import os
import esptool
import webbrowser
from tkinter import *
from tkinter import filedialog
from tkinter.ttk import *

global window

# this class credit marcelstoer
# See discussion at http://stackoverflow.com/q/41101897/131929
class RedirectText:
    def __init__(self, textArea):
        self.out = textArea
        self.pending_backspaces = 0

    def write(self, string):
        new_string = ""
        number_of_backspaces = 0
        for c in string:
            if c == "\b":
                number_of_backspaces += 1
            else:
                new_string += c

        self.out.configure(state=NORMAL)

        while (self.pending_backspaces > 0):
            self.pending_backspace -= 1
            self.out.delete("1.0", END)

        new_string = new_string.strip()
        if len(new_string) > 0:
            self.out.insert(END, new_string)
            self.out.insert(END, "\n") # ugly esptool log hack

        self.out.see("end")
        self.out.configure(state=DISABLED)
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

    def initFlags(self):
        '''Initialises the flags used to control the program flow'''
        self.ESPTOOL_BUSY = False

        self.ESPTOOLARG_SERIALPORT = 'Auto-Detect'
        self.ESPTOOLARG_BAUD = '921600'
        self.ESPTOOLARG_APPPATH = None
        self.ESPTOOLARG_APPFLASH = True

        self.APPFILE_SELECTED = False

    def initUI(self):
        '''Runs on application start to build the GUI'''

        self.master.title("Floower Upgrader")
        self.pack(fill=BOTH, expand=True)

        #self.columnconfigure(0, pad=20)
        self.columnconfigure(1, weight=1)
        #self.columnconfigure(2, pad=20)
        self.rowconfigure(4, weight=1)
        #self.rowconfigure(0, pad=10)
        #self.rowconfigure(1, pad=10)

        ################################################################
        #                      FIRMWARE FILE NAME                      #
        ################################################################
        labelFirmware = Label(self, text="Flooware File:")
        labelFirmware.grid(row=0, column=0, sticky=W)
        firmwareFilenameEntry = Entry(self, textvariable=self.firmwareFilename, background="white", state="readonly")
        firmwareFilenameEntry.grid(row=0, column=1, sticky=E + W + S + N, padx=10)
        self.buttonBrowse = Button(self, text="Browse", command=self.onBrowseFile)
        self.buttonBrowse.grid(row=0, column=2, sticky=E + W + S + N)
        labelDownloadLatest = Label(self, text="Download the latest version", foreground="blue", cursor="hand2")
        labelDownloadLatest.grid(row=1, column=1, sticky=W, padx=8)
        labelDownloadLatest.bind("<Button-1>", lambda e: webbrowser.open_new('https://floower.io/flooware'))

        ################################################################
        #                      SERIAL PORT                             #
        ################################################################
        labelSerial = Label(self, text="Serial Port:")
        labelSerial.grid(row=2, column=0, sticky=W)
        self.serialPortsCombo = Combobox(self, state="readonly")
        self.serialPortsCombo.grid(row=2, column=1, sticky=E + W + S + N, pady=5, padx=10)
        self.serialPortsCombo.bind("<<ComboboxSelected>>", self.onSerialPortSelect)
        self.updateSerialPortsValues()
        self.buttonRescan = Button(self, text="Rescan", command=self.onSerialScan)
        self.buttonRescan.grid(row=2, column=2, sticky=E + W + S + N, pady=4)

        ################################################################
        #                      STATUS LABEL                            #
        ################################################################
        labelStatus = Label(self, text="Status:")
        labelStatus.grid(row=3, column=0, sticky=W)
        labelStatusValue = Label(self, text="Ready", font='Helvetica 12 bold', justify=LEFT)
        labelStatusValue.grid(row=3, column=1, pady=10, sticky=W, padx=8)

        ################################################################
        #                   BEGIN CONSOLE OUTPUT GUI                   #
        ################################################################
        consoleFrame = Frame(self)
        consoleFrame.grid(row=4, column=0, columnspan=3, pady=10, sticky=E + W + S + N)
        consoleFrame.columnconfigure(0, weight=1)
        consoleFrame.rowconfigure(0, weight=1)

        console = Text(consoleFrame, state=DISABLED, wrap="none")
        console.grid(row=0, column=0, sticky=E + W + S + N)
        sys.stdout = RedirectText(console)
        consoleScrollbar = Scrollbar(consoleFrame, command=console.yview)
        console['yscrollcommand'] = consoleScrollbar.set
        consoleScrollbar.grid(row=0, column=1, sticky='nsew')

        ################################################################
        #                   ACTION BUTTONS                             #
        ################################################################
        self.buttonClose = Button(self, text="Close", command=self.onClose)
        self.buttonClose.grid(row=5, column=0, sticky=E + W + S + N, pady=4)
        labelHelp = Label(self, text="Help me", foreground="blue", cursor="hand2")
        labelHelp.grid(row=5, column=1, sticky=E, padx=8)
        labelHelp.bind("<Button-1>", lambda e: webbrowser.open_new('https://floower.io/'))
        self.buttonFlash = Button(self, text="Upgrade", command=self.onFlash, state="disabled")
        self.buttonFlash.grid(row=5, column=2, sticky=E + W + S + N, pady=4)

        return

        photo = PhotoImage(file="cat.png")
        imgLabel = Label(self, image=photo)
        imgLabel.pack(side=RIGHT)


    ################################################################
    #                      UI EVENT HANDLERS                       #
    ################################################################
    def onSerialScan(self):
        # repopulate the serial port choices and update the selected port
        print('Scanning Serial Ports ...', end=" ")
        self.updateSerialPortsValues()
        print('Done')

    def updateSerialPortsValues(self):
        devices = self.list_serial_devices()
        devices.append('Auto-Detect')

        self.serialPortsCombo["values"] = devices;
        for id, device in enumerate(devices, start=0):
            if device == self.ESPTOOLARG_SERIALPORT:
                self.serialPortsCombo.current(id)

    def onSerialPortSelect(self, event):
        self.ESPTOOLARG_SERIALPORT = self.serialPortsCombo.get()
        print('Selected port ' + self.ESPTOOLARG_SERIALPORT)

    def onBrowseFile(self):
        filename = filedialog.askopenfilename(title="Select a File", filetypes=(("Flooware files","*.bin"), ("all files","*.*")))
        if filename != "":
            self.APPFILE_SELECTED = True
            self.firmwareFilename.set(os.path.basename(filename))
            self.ESPTOOLARG_APPPATH = os.path.abspath(filename)
            print(self.ESPTOOLARG_APPPATH)
            self.buttonFlash["state"] = "enabled"

    def onClose(self):
        global window
        window.destroy()

    def onFlash(self):
        if self.ESPTOOL_BUSY:
            print('currently busy')
            return
        # handle cases where a flash has been requested but no file provided
        elif self.ESPTOOLARG_APPFLASH & ~self.APPFILE_SELECTED:
            print('no app selected for flash')
            return
        else:
            t = threading.Thread(target=self.esptoolRunner, daemon=True)
            t.start()

    def disableUI(self):
        self.buttonRescan["state"] = "disabled"
        self.buttonBrowse["state"] = "disabled"
        self.serialPortsCombo["state"] = "disabled"
        self.buttonFlash["state"] = "disabled"
        self.buttonClose["state"] = "disabled"

    def enableUI(self):
        self.buttonRescan["state"] = "enabled"
        self.buttonBrowse["state"] = "enabled"
        self.serialPortsCombo["state"] = "enabled"
        self.buttonClose["state"] = "enabled"

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

        if self.ESPTOOLARG_SERIALPORT != 'Auto-Detect':
            cmd = cmd + ['--port',self.ESPTOOLARG_SERIALPORT]

        cmd.append('write_flash')
        if self.ESPTOOLARG_APPFLASH:
            cmd.append('0x10000')
            cmd.append(self.ESPTOOLARG_APPPATH)

        return cmd

    def esptoolRunner(self):
        '''Handles the interaction with esptool'''
        self.ESPTOOL_BUSY = True
        self.disableUI()

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
        self.enableUI()
        self.buttonFlash["state"] = "enabled"


def main():
    global window

    window = Tk()
    window.title("Floower Upgrader")
    window.geometry('500x500')
    app = FloowerUpgrader()
    app.pack(padx=10, pady=10)
    window.mainloop()

if __name__ == '__main__':
    main()
