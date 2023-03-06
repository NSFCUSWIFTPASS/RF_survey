#!/usr/bin/env python
# (c) 2022 The Regents of the University of Colorado, a body corporate. Created by Stefan Tschimben.
# This work is licensed under the Creative Commons Attribution-NonCommercial-ShareAlike 4.0 International License.
# To view a copy of this license, visit http://creativecommons.org/licenses/by-nc-sa/4.0/ or send a letter to Creative Commons, PO Box 1866, Mountain View, CA 94042, USA.

from tkinter.constants import ANCHOR, NW, W
from pexpect import pxssh
import sys, argparse
from argparse import RawDescriptionHelpFormatter
import tkinter as tk
from tkinter import messagebox, ttk
import locale
from datetime import *
from time import strftime, localtime
import requests
import json
import random

locale.setlocale(locale.LC_ALL, "en_US.UTF-8")
class ToolTip(object):

    def __init__(self, widget):
        self.widget = widget
        self.tipwindow = None
        self.id = None
        self.x = self.y = 0

    def showtip(self, text):
        "Display text in tooltip window"
        self.text = text
        if self.tipwindow or not self.text:
            return
        x, y, cx, cy = self.widget.bbox("insert")
        x = x + cx + self.widget.winfo_rootx() + 57
        y = y + cy + self.widget.winfo_rooty() +27
        self.tipwindow = tw = tk.Toplevel(self.widget)
        tw.wm_overrideredirect(1)
        tw.wm_geometry("+%d+%d" % (x, y))
        label = tk.Label(tw, text=self.text, justify=tk.LEFT,
                      background="#000000", foreground="white", relief=tk.RAISED, borderwidth=1,
                      font=("tahoma", "12", "normal"))
        label.pack(ipadx=1)

    def hidetip(self):
        tw = self.tipwindow
        self.tipwindow = None
        if tw:
            tw.destroy()

def CreateToolTip(widget, text):
    toolTip = ToolTip(widget)
    def enter(event):
        toolTip.showtip(text)
    def leave(event):
        toolTip.hidetip()
    widget.bind('<Enter>', enter)
    widget.bind('<Leave>', leave)

class Called:
    def __init__(self, func):
        self.func = func
        self.called = False

    def __call__(self, *args, **kwargs):
        self.called = True
        self.func(*args, **kwargs)

class EntNum(tk.Entry):
    def __init__(self, master=None, **kwargs):
        self.var = tk.StringVar()
        tk.Entry.__init__(self, master, textvariable=self.var, **kwargs)
        self.old_value = ""
        self.var.trace("w", self.check)
        self.get, self.set = self.var.get, self.var.set

    def check(self, *args):
        if self.get().isdigit() or "," in self.get(): 
            # the current value is only digits; allow this
            self.set(locale.format_string("%d", int(self.get().replace(",","")), grouping=True))
        elif not self.get():
            # the field is empty; allow this
            self.old_value = self.get()
        else:
            # there's non-digit characters in the input; reject this 
            self.set(self.old_value)

class Commands(object):
    def __init__(self, center_frequency, bandwidth, length, gain, recordings, interval, org, location, last_frequency = 0, cycles = 0, random_interval = 0, samples = 0, delay = 0):
        self.center_frequency = str(center_frequency)
        self.bandwidth = str(bandwidth)
        self.length = str(length)
        self.gain = str(gain)
        self.recordings = str(recordings)
        self.interval = str(interval)
        self.org = str(org)
        self.location = str(location)
        self.last_frequency = str(last_frequency)
        self.cycles = str(cycles)
        self.random_interval = str(random_interval)
        self.samples = str(samples)
        self.delay = str(delay)

    def send_command(self, var_forever, var_delay, var_sweep, var_random):
        seed = random.randint(0,10000)
        seed = str(seed)
        valid_combos = {
            (0,0,0,0): ["nohup python3 /home/pi/rf_survey/rf_survey.py -f1 "+self.center_frequency+" -b "+self.bandwidth+" -s "+self.length+" -g "+self.gain+" -r "+self.recordings+" -t "+self.interval+" -o "+self.org+" -gcs "+self.location+" &"],
            (0,0,0,1): ["nohup python3 /home/pi/rf_survey/rf_survey.py -f1 "+self.center_frequency+" -b "+self.bandwidth+" -s "+self.length+" -g "+self.gain+" -r "+self.recordings+" -t 0 "+" -m "+self.random_interval+" -rs "+seed+" -o "+self.org+" -gcs "+self.location+" &"],
            (0,0,1,0): ["nohup python3 /home/pi/rf_survey/rf_survey.py -f1 "+self.center_frequency+" -f2 "+self.last_frequency+" -b "+self.bandwidth+" -s "+self.length+" -g "+self.gain+" -r "+self.samples+" -t "+self.interval+" -c "+self.cycles+" -o "+self.org+" -gcs "+self.location+" &"],
            (0,0,1,1): ["nohup python3 /home/pi/rf_survey/rf_survey.py -f1 "+self.center_frequency+" -f2 "+self.last_frequency+" -b "+self.bandwidth+" -s "+self.length+" -g "+self.gain+" -r "+self.samples+" -t "+self.interval+" -c "+self.cycles+" -m "+self.random_interval+" -o "+self.org+" -gcs "+self.location+" &"],
            (0,1,0,0): ["nohup python3 /home/pi/rf_survey/rf_survey.py -f1 "+self.center_frequency+" -b "+self.bandwidth+" -s "+self.length+" -g "+self.gain+" -r "+self.recordings+" -t "+self.interval+" -o "+self.org+" -gcs "+self.location+" -d "+self.delay+" &"],
            (0,1,0,1): ["nohup python3 /home/pi/rf_survey/rf_survey.py -f1 "+self.center_frequency+" -b "+self.bandwidth+" -s "+self.length+" -g "+self.gain+" -r "+self.recordings+" -t 0 "+" -m "+self.random_interval+" -rs "+seed+" -o "+self.org+" -gcs "+self.location+" -d "+self.delay+" &"],
            (0,1,1,0): ["nohup python3 /home/pi/rf_survey/rf_survey.py -f1 "+self.center_frequency+" -f2 "+self.last_frequency+" -b "+self.bandwidth+" -s "+self.length+" -g "+self.gain+" -r "+self.samples+" -t "+self.interval+" -c "+self.cycles+" -o "+self.org+" -gcs "+self.location+" -d "+self.delay+" &"],
            (0,1,1,1): ["nohup python3 /home/pi/rf_survey/rf_survey.py -f1 "+self.center_frequency+" -f2 "+self.last_frequency+" -b "+self.bandwidth+" -s "+self.length+" -g "+self.gain+" -r "+self.samples+" -t "+self.interval+" -c "+self.cycles+" -m "+self.random_interval+" -o "+self.org+" -gcs "+self.location+" -d "+self.delay+" &"],
            (1,0,0,0): ["nohup python3 /home/pi/rf_survey/rf_survey.py -f1 "+self.center_frequency+" -b "+self.bandwidth+" -s "+self.length+" -g "+self.gain+" -r "+self.recordings+" -t "+self.interval+" -c 0 "+" -o "+self.org+" -gcs "+self.location+" &"],
            (1,0,0,1): ["nohup python3 /home/pi/rf_survey/rf_survey.py -f1 "+self.center_frequency+" -b "+self.bandwidth+" -s "+self.length+" -g "+self.gain+" -r "+self.recordings+" -t 0 "+" -c 0 "+" -m "+self.random_interval+" -rs "+seed+" -o "+self.org+" -gcs "+self.location+" &"],
            (1,0,1,0): ["nohup python3 /home/pi/rf_survey/rf_survey.py -f1 "+self.center_frequency+" -f2 "+self.last_frequency+" -b "+self.bandwidth+" -s "+self.length+" -g "+self.gain+" -r "+self.samples+" -t "+self.interval+" -c 0 "+" -o "+self.org+" -gcs "+self.location+" &"],
            (1,0,1,1): ["nohup python3 /home/pi/rf_survey/rf_survey.py -f1 "+self.center_frequency+" -f2 "+self.last_frequency+" -b "+self.bandwidth+" -s "+self.length+" -g "+self.gain+" -r "+self.samples+" -t "+self.interval+" -c 0 "+" -m "+self.random_interval+" -o "+self.org+" -gcs "+self.location+" &"],
            (1,1,0,0): ["nohup python3 /home/pi/rf_survey/rf_survey.py -f1 "+self.center_frequency+" -b "+self.bandwidth+" -s "+self.length+" -g "+self.gain+" -r "+self.recordings+" -t "+self.interval+" -c 0 "+" -o "+self.org+" -gcs "+self.location+" -d "+self.delay+" &"],
            (1,1,0,1): ["nohup python3 /home/pi/rf_survey/rf_survey.py -f1 "+self.center_frequency+" -b "+self.bandwidth+" -s "+self.length+" -g "+self.gain+" -r "+self.recordings+" -t 0 "+" -c 0 "+" -m "+self.random_interval+" -rs "+seed+" -o "+self.org+" -gcs "+self.location+" -d "+self.delay+" &"],
            (1,1,1,0): ["nohup python3 /home/pi/rf_survey/rf_survey.py -f1 "+self.center_frequency+" -f2 "+self.last_frequency+" -b "+self.bandwidth+" -s "+self.length+" -g "+self.gain+" -r "+self.samples+" -t "+self.interval+" -c 0 "+" -o "+self.org+" -gcs "+self.location+" -d "+self.delay+" &"],
            (1,1,1,1): ["nohup python3 /home/pi/rf_survey/rf_survey.py -f1 "+self.center_frequency+" -f2 "+self.last_frequency+" -b "+self.bandwidth+" -s "+self.length+" -g "+self.gain+" -r "+self.samples+" -t "+self.interval+" -c 0 "+" -m "+self.random_interval+" -o "+self.org+" -gcs "+self.location+" -d "+self.delay+" &"]
        }
        return valid_combos.get((var_forever, var_delay, var_sweep, var_random),0)

def main(argv):

    def toggle_time(): # change to add UTC time instead of replacing current time
        now = (datetime.now() + timedelta(minutes=20)).strftime('%H:%M %m-%d-%Y')
        utc = (datetime.now() + (datetime.utcnow() - datetime.now())+ timedelta(minutes=20)).strftime('%H:%M %m-%d-%Y')
        if var_delay.get() == 1:
            if var_utc.get() == 1:
                delay = (datetime.now() + (datetime.utcnow() - datetime.now())+ timedelta(minutes=10)).strftime('%H:%M %m-%d-%Y')
                ent_delay.delete("0","end")
                ent_samples.delete("0","end")
                ent_delay.insert(tk.END, "%s" % (delay))
                ent_samples.insert(tk.END, "%s" % (utc))
            else:
                delay = (datetime.now() + timedelta(minutes=10)).strftime('%H:%M %m-%d-%Y')
                ent_delay.delete("0","end")
                ent_samples.delete("0","end")
                ent_delay.insert(tk.END, "%s" % (delay))
                ent_samples.insert(tk.END, "%s" % (now))
        else:
            if var_utc.get() == 1:
                ent_samples.delete("0","end")
                ent_samples.insert(tk.END, "%s" % (utc))
            else:
                ent_samples.delete("0","end")
                ent_samples.insert(tk.END, "%s" % (now))

    def toggle_steps():
        if var_steps.get() == 1:
            var_sweep.set(0)
            ent_steps["background"] = "#b36600"
            for element in [ent_frequency2, ent_cycles, ent_n_records]:
                element["background"] = "#000000"
                element.delete("0","end")
            for label in [lbl_frequency2, lbl_cycles, lbl_n_records]:
                label["foreground"] = "#000000"
        else:
            ent_steps["background"] = "#000000"
            ent_steps.delete("0","end")
    def toggle_sweep():
        if var_sweep.get() == 1:
            var_steps.set(0)
            ent_steps["background"] = "#000000"
            ent_steps.delete("0","end")
            for element in [ent_frequency2, ent_cycles, ent_n_records]:
                element["background"] = "#0081b3"
            for label in [lbl_frequency2, lbl_cycles, lbl_n_records]:
                label["foreground"] = "#21c1ff"
        else:
            for element in [ent_frequency2, ent_cycles, ent_n_records]:
                element["background"] = "#000000"
                element.delete("0","end")
            for label in [lbl_frequency2, lbl_cycles, lbl_n_records]:
                label["foreground"] = "#000000"
    def toggle_random():
        if var_random.get() == 1:
            ent_random["background"] = "#329023"
            ent_interval.delete("0","end")
            ent_interval.insert(tk.END, "%s" % ("0"))
        else:
            ent_random["background"] = "#000000"
            ent_random.delete("0", "end")
    def toggle_forever():
        if var_forever.get() == 1:
            ent_cycles["background"] = "#000000"
            ent_cycles.delete("0","end") 
            lbl_cycles["foreground"] = "#000000"    # if (get current checkbutton state) is "1" then....
            ent_samples["foreground"] = "#000000"
            ent_samples.delete("0","end") 
            lbl_samples["foreground"] = "#000000"
        else:
            ent_cycles["background"] = "#0081b3"
            lbl_cycles["foreground"] = "#21c1ff"
            ent_samples["foreground"] = "white"
            lbl_samples["foreground"] = "white"
            now = strftime('%H:%M %m-%d-%Y', localtime())
            ent_samples.insert(tk.END, "%s" % (now))
    def toggle_delay():
        if var_delay.get() == 1:
            ent_delay.delete("0", "end")
            ent_delay["background"] = "#b39300"
            if var_utc.get() == 1:
                now = (datetime.now() + (datetime.utcnow() - datetime.now())+ timedelta(minutes=10)).strftime('%H:%M %m-%d-%Y')                
                ent_delay.insert(tk.END, "%s" % (now))
            else:
                now = (datetime.now() + timedelta(minutes=10)).strftime('%H:%M %m-%d-%Y')
                ent_delay.insert(tk.END, "%s" % (now))
        else:
            ent_delay["background"] = "#000000"
            ent_delay.delete("0", "end")

    msg = "Use this Python Application to update Noise Survey Paramters on all modules remotely"
    

    response = requests.get("https://api.ipgeolocation.io/ipgeo?apiKey=284b9115bcd942438fc207f2457c0492")
    data = json.loads(response.content)
    latitude = data['latitude'][:-1]+"N" if float(data['latitude']) >= 0 else data['latitude'][1:-1]+"S"
    longitude = data['longitude'][:-1]+"E" if float(data['longitude']) >= 0 else data['longitude'][1:-1]+"W"
    org = data['organization']
    org = org.replace(" ","_")
    ip = data['ip']

    parser = argparse.ArgumentParser(description = msg, formatter_class=RawDescriptionHelpFormatter)
    parser.add_argument("-v", "--version", action = "version", version="%(prog)s 4.4.1")
    parser.parse_args()

    window = tk.Tk()
    window.title("Update Noise Survey Parameters")
    window.configure(bg="black")
    window.grid_columnconfigure(0, weight=1)
    window.grid_rowconfigure(0, weight=1)
    window.resizable(False, False)
    frame_inputs=tk.Frame(window ,padx=5, pady=5, bg="black")
    frame_inputs.grid(row=0,column=0, sticky=tk.NSEW)

    lbl_user = tk.Label(master=frame_inputs, text="RPi username:", foreground="white", background="black")
    lbl_user.grid(column=0, row=0, sticky=tk.W, padx=5, pady=5)
    ent_user = tk.Entry(master=frame_inputs, width=20, background="black", foreground="white")
    ent_user.grid(column=1, row=0, padx=5, pady=5)
    ent_user.focus_set()
    CreateToolTip(ent_user, text = 'Enter the Raspberry Pi login username.')

    lbl_pass = tk.Label(master=frame_inputs, text="RPi password:", foreground="white", background="black")
    lbl_pass.grid(column=3, row=0, sticky=tk.W, padx=5, pady=5)
    ent_pass = tk.Entry(master=frame_inputs, width=20, background="black", foreground="white")
    ent_pass.grid(column=4, row=0, padx=5, pady=5)
    CreateToolTip(ent_pass, text = 'Enter the Raspberry Pi user password.')

    lbl_org= tk.Label(master=frame_inputs, text="Organization:", foreground="white", background="black")
    lbl_org.grid(column=0, row=1, sticky=tk.W, padx=5, pady=5)
    ent_org = tk.Entry(master=frame_inputs, width=20, background="black", foreground="white")
    ent_org.grid(column=1, row=1, padx=5, pady=5)
    CreateToolTip(ent_org, text = 'Enter your Organization or general Location, e.g. CU Boulder.')
    ent_org.insert(tk.END, "%s" %(org))

    lbl_gcs = tk.Label(master=frame_inputs, text="GCS Coordinates:", foreground="white", background="black")
    lbl_gcs.grid(column=3, row=1, sticky=tk.W, padx=5, pady=5)
    ent_gcs = tk.Entry(master=frame_inputs, width=20, background="black", foreground="white")
    ent_gcs.grid(column=4, row=1, padx=5, pady=5)
    CreateToolTip(ent_gcs, text = 'Latitude and Longitude of your Location in the Format: 40.0149 -105.2705.')
    ent_gcs.insert(tk.END, "%s%s" %(latitude, longitude))

    lbl_bandwidth = tk.Label(master=frame_inputs, text="Bandwidth (Hz):", foreground="white", background="black")
    lbl_bandwidth.grid(column=0, row=2, sticky=tk.W, padx=5, pady=5)
    ent_bandwidth = EntNum(master=frame_inputs, width=20, background="black", foreground="white")
    ent_bandwidth.grid(column=1, row=2, padx=5, pady=5)
    CreateToolTip(ent_bandwidth, text = 'Enter the desired bandwidth in Hz.')

    var_sweep = tk.IntVar()
    chck_sweep = tk.Checkbutton(master=frame_inputs, variable=var_sweep, text="Frequency Sweep", foreground="#21c1ff", background="black", command=toggle_sweep)
    chck_sweep.grid(column=3, row=2, sticky=tk.W, padx=5, pady=5, columnspan=2)
    CreateToolTip(chck_sweep, text = 'Checking this box will cause the data collection to sweep\n'
                                        'across frequencies, starting with "Start Center Frequency"\n'
                                        'in Bandwidth steps and ending with "End Center Frequency".\n'
                                        '!! Not compatible with "Frequency Steps"!!')

    lbl_frequency = tk.Label(master=frame_inputs, text="Start Center Frequency (Hz):", foreground="white", background="black")
    lbl_frequency.grid(column=0, row=3, sticky=tk.W, padx=5, pady=5)
    ent_frequency = EntNum(master=frame_inputs, width=20, background="black", foreground="white")
    ent_frequency.grid(column=1, row=3, padx=5, pady=5)
    CreateToolTip(ent_frequency, text = 'Enter center frequency in Hz. If "Sweep" is checked\n'
                                        'this will become the first center frequency to be recorded.')


    lbl_frequency2 = tk.Label(master=frame_inputs, text="End Center Frequency (Hz):", foreground="black", background="black")
    lbl_frequency2.grid(column=3, row=3, sticky=tk.W, padx=5, pady=5)
    ent_frequency2 = EntNum(master=frame_inputs, width=20, background="black", foreground="white")
    ent_frequency2.grid(column=4, row=3, padx=5, pady=5)
    CreateToolTip(ent_frequency2, text = 'Enter center frequency in Hz. If "Sweep" is checked\n'
                                         'this will become the final center frequency to be recorded.')


    lbl_gain = tk.Label(master=frame_inputs, text="Receive Gain in db (0-76):", foreground="white", background="black")
    lbl_gain.grid(column=0, row=4, sticky=tk.W, padx=5, pady=5)
    ent_gain = EntNum(master=frame_inputs, width=20, background="black", foreground="white")
    ent_gain.grid(column=1, row=4, padx=5, pady=5)
    CreateToolTip(ent_gain, text = 'Selecting 0 will cause the SDR to determine\n'
                                    'the optimal gain on its own.')

    lbl_n_records = tk.Label(master=frame_inputs, text="# of Recordings per Frequency:", foreground="black", background="black")
    lbl_n_records.grid(column=3, row=4, sticky=tk.W, padx=5, pady=5)
    ent_n_records = EntNum(master=frame_inputs, width=20, background="black", foreground="white")
    ent_n_records.grid(column=4, row=4, padx=5, pady=5)
    CreateToolTip(ent_n_records, text = 'If "Sweep" is checked, this determines how many times\n'
                                        'the same frequency is recorded in a single sweep.')

    lbl_length = tk.Label(master=frame_inputs, text="Length in seconds:", foreground="white", background="black")
    lbl_length.grid(column=0, row=5, sticky=tk.W, padx=5, pady=5)
    ent_length = EntNum(master=frame_inputs, width=20, background="black", foreground="white")
    ent_length.grid(column=1, row=5, padx=5, pady=5)
    CreateToolTip(ent_length, text = "Determines how long a single\n"
                                     "IQ data recording will be.")
    
    lbl_cycles = tk.Label(master=frame_inputs, text="# of Times cycling through Frequencies:", foreground="black", background="black")
    lbl_cycles.grid(column=3, row=5, sticky=tk.W, padx=5, pady=5)
    ent_cycles = EntNum(master=frame_inputs, width=20, background="black", foreground="white")
    ent_cycles.grid(column=4, row=5, padx=5, pady=5)
    CreateToolTip(ent_cycles, text = 'Used in combination with "Sweep". Makes it\n'
                                        'possible to repeat the sweep n amount of times.')

    lbl_interval = tk.Label(master=frame_inputs, text="Time between Recordings (seconds):", foreground="white", background="black")
    lbl_interval.grid(column=0, row=6, sticky=tk.W, padx=5, pady=5)
    ent_interval = EntNum(master=frame_inputs, width=20, background="black", foreground="white")
    ent_interval.grid(column=1, row=6, padx=5, pady=5)
    CreateToolTip(ent_interval, text = 'Determines in what intervals data will be recorded.\n'
                                        'A value of 7 seconds will start the first recording at\n'
                                        'a calendar time that\'s a multiple of 7.')

    var_steps = tk.IntVar()
    chck_steps = tk.Checkbutton(master=frame_inputs, variable=var_steps, text="Frequency Steps (Hz):", foreground="#ffa226", background="black", command=toggle_steps)
    chck_steps.grid(column=3, row=6, sticky=tk.W, padx=5, pady=5, columnspan=2)
    CreateToolTip(chck_steps, text = 'Checking this box will cause the data collection to assign\n'
                                        'different center frequencies to an amount of IP address listed\n'
                                        'below, determined by "Number of Frequency Steps", and\n'
                                        'separated by "Frequency Steps".\n')

    ent_steps = EntNum(master=frame_inputs, width=20, background="#000000", foreground="white")
    ent_steps.grid(column=4, row=6, padx=5, pady=5)
    CreateToolTip(ent_steps, text = 'Determines the distance in frequency between recordings\n'
                                    'on different SDRs if "Frequency Steps" is checked.')

    lbl_samples = tk.Label(master=frame_inputs, text="Data Collection End Time and Day:", foreground="white", background="black")
    lbl_samples.grid(column=0, row=7, sticky=tk.W, padx=5, pady=5)
    ent_samples = tk.Entry(master=frame_inputs, width=20, background="black", foreground="white")
    ent_samples.grid(column=1, row=7, padx=5, pady=5)
    CreateToolTip(ent_samples, text = 'Format HH:MM mm-dd-YYYY. (24h clock)')

    var_random = tk.IntVar()
    chck_random = tk.Checkbutton(master=frame_inputs, variable=var_random, text="Random Interval - Upper Limit (s):", foreground="#a2e697", background="black", command=toggle_random)
    chck_random.grid(column=3, row=7, sticky=tk.W, padx=5, pady=5)
    CreateToolTip(chck_random, text = 'Before checking this box, set interval to 0.\n'
                                        'Checking this box will replace the regular interval\n'
                                        'with a random interval with "Upper Bound".')
    ent_random = EntNum(master=frame_inputs, width=20, background="#000000", foreground="white")
    ent_random.grid(column=4, row=7, padx=5, pady=5)
    CreateToolTip(ent_random, text = 'The random interval will be between a minimum determined\n'
                                        'by the bandwidth and the upper bound / maximum provided here.')

    var_delay = tk.IntVar()
    chck_delay = tk.Checkbutton(master=frame_inputs, variable=var_delay, text="Delayed Start:", foreground="#ffd92b", background="black", command=toggle_delay)
    chck_delay.grid(column=0, row=8, sticky=tk.W, padx=5, pady=5, columnspan=2)
    CreateToolTip(chck_delay, text = 'Checking this box will cause the data collection to start\n'
                                        'at the selected time instead of immediately.')
    ent_delay = tk.Entry(master=frame_inputs, width=20, background="#000000", foreground="white")
    ent_delay.grid(column=1, row=8, padx=5, pady=5)
    CreateToolTip(ent_delay, text = 'Format HH:MM mm-dd-YYYY. (24h clock)')

    var_utc = tk.IntVar()
    chck_utc = tk.Checkbutton(master=frame_inputs, variable=var_utc, text="UTC Time Format", foreground="#ff2570", background="black", command=toggle_time)
    chck_utc.grid(column=3, row=8, sticky=tk.W, padx=5, pady=5, columnspan=2)
    CreateToolTip(chck_utc, text = 'Changes time examples to the UTC format.')
    
    var_forever = tk.IntVar()
    chck_forever = tk.Checkbutton(master=frame_inputs, variable=var_forever, text="Loop forever", foreground="#ff2570", background="black", command=toggle_forever)
    chck_forever.grid(column=4, row=8, sticky=tk.W, padx=5, pady=5, columnspan=2)
    CreateToolTip(chck_forever, text = 'Checking this box will ignore the end date and\n'
                                        'instead run a survey until the data collection is\n'
                                        'stopped with "Interrupt Surveys".')

    separator = ttk.Separator(master=frame_inputs)
    separator.grid(column=0, row=9, columnspan=5, sticky="ew")

    lbl_ips = tk.Label(master=frame_inputs, text="Enter one IP Address per Line:", foreground="white", background="black")
    lbl_ips.grid(column=3, row=10, columnspan = 2, padx=5, pady=5)
    txt_ips = tk.Text(master=frame_inputs, height=10, width=50, background="black", foreground="white")
    txt_ips.grid(column=3, row=11, columnspan = 2, rowspan=3, padx=5, pady=5)
    txt_ips.insert(tk.END, "%s" %(ip))

    #var_popup = tk.IntVar()
    #chck_popup = tk.Checkbutton(master=frame_inputs, variable=var_popup, text="Output Notifications to IP address field.", foreground="white", background="black")
    #chck_popup.grid(column=0, row=10, sticky=tk.W, padx=5, pady=5, columnspan=2)
    #CreateToolTip(chck_popup, text = 'Turns off notifications that each RPI was successfully connected.')

    scroll_ips = ttk.Scrollbar(master=frame_inputs, command=txt_ips.yview)
    scroll_ips.grid(column=5, row=11, rowspan=3, sticky='nsew')
    txt_ips['yscrollcommand'] = scroll_ips.set
    CreateToolTip(txt_ips, text = 'Provide a list of IP address to connect to.\n'
                                    'The devices at the end of these addresses need\n'
                                    'to use the same username and password.')
    
    if var_utc.get() == 0:
        now = (datetime.now() + timedelta(minutes=20)).strftime('%H:%M %m-%d-%Y')
        ent_samples.insert(tk.END, "%s" % (now))
    else:
        now = (datetime.utcnow()+ timedelta(minutes=20)).strftime('%H:%M %m-%d-%Y')
        ent_samples.insert(tk.END, "%s" % (now))

    def end():
        window.destroy()

    def start_all():
        try:
            username = ent_user.get()
            password = ent_pass.get()
            Param_USRP_Bandwidth = ent_bandwidth.get().replace(",","")
            Param_USRP_Centre_Frequency = ent_frequency.get().replace(",","")
            Param_USRP_Gain = ent_gain.get().replace(",","")
            Param_USRP_Length = str(int(float(ent_length.get().replace(",","")) * float(Param_USRP_Bandwidth)))
            Param_USRP_Interval = ent_interval.get().replace(",","")
            Param_USRP_Random_Interval = ent_random.get().replace(",","")
            Param_ips = txt_ips.get(1.0, 'end-1c').splitlines()
            Param_n_ips = len(Param_ips)
            Param_USRP_Cycles = ent_cycles.get().replace(",","")
            Param_org = ent_org.get()
            Param_gcs = ent_gcs.get()
            Param_USRP_Recordings = ent_n_records.get().replace(",","")

            if not username or not password:
                raise ValueError("Username and/or Password missing!")
            if not Param_ips:
                raise ValueError("Provide an IP address!")
            if var_random.get() == 1 and int(ent_interval.get()) != 0:
                if int(Param_USRP_Random_Interval) < int(Param_USRP_Bandwidth)/1e6*0.2:
                    raise ValueError("The time between recordings must be at least BW/1e6*0.2!")
                raise ValueError('"Time between Recordings" needs to be 0 when using a random Interval!')
            check_remainder = int(Param_USRP_Interval)
            if (check_remainder >=60 and check_remainder%60 != 0) or (check_remainder <=60 and 60%check_remainder != 0):
                raise ValueError('"Time between Recordings" needs to be a multiple of 60 or divide 60 without remainder!')

        except Exception as e:
            messagebox.showerror("Error!", "Fill out all fields correctly before submitting: \n %s" % (repr(e)))
            return

        if var_forever.get() == 0:
            enddate = datetime.strptime(ent_samples.get(), '%H:%M %m-%d-%Y')
            print(enddate)
            if var_utc.get() == 0:
                now = datetime.today()
            else:
                now = datetime.utcnow()
            difference = enddate - now
            total = difference.total_seconds()
            if not Param_USRP_Recordings and not Param_USRP_Cycles:
                if int(total) <= 0:
                    messagebox.showerror("Error!", "End time of the survey needs to be larger than current time.")
                    return
            if var_delay.get() == 1:
                startdate = datetime.strptime(ent_delay.get(), '%H:%M %m-%d-%Y')
                print(startdate)
                if startdate >= enddate:
                    messagebox.showerror("Error!", "The delayed start has to occurr before the scheduled end of the survey.")
                    return
                future = startdate - now
                delay = future.total_seconds()
                total = total - delay
                if var_random.get() == 0:
                    total_recordings = int(total//int(Param_USRP_Interval))
                else:
                    total_recordings = int(total//int((Param_USRP_Random_Interval)))
                if int(delay) <= 0:
                    messagebox.showerror("Error!", "Check the survey's end and delayed start time: \n %s" % (repr(e)))
                    return
            elif var_random.get() == 1:
                delay = 0
                try:
                    total_recordings = int(total//int((Param_USRP_Random_Interval)))
                except Exception as e:
                    messagebox.showerror("Error!", "Make sure the interval is 0 and a random upper limit is given: \n %s" % (repr(e)))
                    return
            else:
                delay = 0
                try:
                    total_recordings = int(total//int(Param_USRP_Interval))
                except Exception as e:
                    messagebox.showerror("Error!", "Make sure the interval is not 0: \n %s" % (repr(e)))
                    return
        else:
            total_recordings = 1
            if var_utc.get() == 0:
                now = datetime.today()
            else:
                now = datetime.utcnow()
            delay = 0
            if var_delay.get() == 1:
                startdate = datetime.strptime(ent_delay.get(), '%H:%M %m-%d-%Y')
                future = startdate - now
                delay = future.total_seconds()

        if var_steps.get() == 1:
            try:
                Param_USRP_Steps = len(Param_ips)
                Param_USRP_N_Steps = len(Param_ips)
                bands = []
                frequency = int(Param_USRP_Centre_Frequency)
                for i in range(Param_USRP_N_Steps):
                    bands.append(frequency + (i * Param_USRP_Steps))
            except Exception as e:
                messagebox.showerror("Error!", "Provide step number and size: \n %s" % (repr(e))) 
                return

        if var_sweep.get() == 1:
            try:
                Param_USRP_Last_Frequency = ent_frequency2.get().replace(",","")
                freq_steps = (int(Param_USRP_Last_Frequency)-int(Param_USRP_Centre_Frequency))//int(Param_USRP_Bandwidth)+1
                print("Number of Frequency Steps: ", freq_steps)
            except Exception as e:
                messagebox.showerror("Error!", "Cycle stop frequency needed: \n %s" % (repr(e)))
                return
            if Param_USRP_Recordings and not Param_USRP_Cycles:
                try:
                    Param_USRP_Last_Frequency = ent_frequency2.get().replace(",","")
                    print("here")
                    Param_USRP_Cycles = str(max(int(total_recordings//((int(Param_USRP_Recordings)*int(freq_steps)))),1))
                    print("Number of Cycles: ", Param_USRP_Cycles)
                except Exception as e:
                    messagebox.showerror("Error!", "Provide stop frequency and either \n"
                                            "recordings per frequency or cycles: \n %s" % (repr(e)))
                    return
            elif Param_USRP_Cycles and not Param_USRP_Recordings:
                try:
                    Param_USRP_Cycles = ent_cycles.get().replace(",","")
                    Param_USRP_Last_Frequency = ent_frequency2.get().replace(",","")
                    Param_USRP_Recordings = str(max(int(total_recordings//(int(Param_USRP_Cycles)*int(freq_steps))),1))
                    print("Number of samples per frequency per cycles: ", Param_USRP_Recordings)
                except Exception as e:
                    messagebox.showerror("Error!", "Provide stop frequency and either \n"
                                            "recordings per frequency or cycles: \n %s" % (repr(e)))
                    return
            elif Param_USRP_Cycles and Param_USRP_Recordings:
                try:
                    Param_USRP_Last_Frequency = ent_frequency2.get().replace(",","")
                    print("Number of samples per frequency per cycles: ", Param_USRP_Recordings)
                except Exception as e:
                    messagebox.showerror("Error!", "Provide stop frequency and either \n"
                                            "recordings per frequency or cycles: \n %s" % (repr(e)))
                    return
        else:
            Param_USRP_Last_Frequency = 0

        if var_forever.get() == 1:
            total_recordings = 1
            Param_USRP_Cycles = 0

        if not Param_USRP_Bandwidth or not Param_USRP_Centre_Frequency or not Param_USRP_Length or not Param_USRP_Interval or not Param_USRP_Gain:
            #raise ValueError("Provide Center Frequency, Bandwidth, Interval, Length, # of Samples, and Gain")
            messagebox.showerror("Provide Center Frequency, Bandwidth, Interval, Length, and Gain")
            return
        
        log = []
        for i in range(Param_n_ips):
            counter = 100/Param_n_ips * (i+1)
            s = pxssh.pxssh(timeout=30)
            progress['value'] = counter
            frame_inputs.update_idletasks()
            try:
                s.login(Param_ips[i], username, password)
                s.sendline("ps -ef | grep 'rf_survey.py' | grep -v grep")
                s.prompt()
                print(str(s.before)[35:])
                output = str(s.before)[35:]
                if "rf_survey.py" in output:
                    messagebox.showinfo("Error!", "A survey is already running on %s.\n Interrupt it first." % (Param_ips[i]))
                    return
                if var_steps.get() == 1:
                    Param_USRP_Centre_Frequency = bands[i]
                cli_command = Commands(Param_USRP_Centre_Frequency, Param_USRP_Bandwidth, Param_USRP_Length, Param_USRP_Gain, total_recordings, Param_USRP_Interval, Param_org, Param_gcs, Param_USRP_Last_Frequency, Param_USRP_Cycles, Param_USRP_Random_Interval, Param_USRP_Recordings, delay)
                #print("SSH session login successful")
                print(cli_command.send_command(var_forever.get(), var_delay.get(), var_sweep.get(), var_random.get())[0])
                s.sendline(cli_command.send_command(var_forever.get(), var_delay.get(), var_sweep.get(), var_random.get())[0])
                s.prompt()         # match the prompt
                print(s.before)     # print everything before the prompt.         
                s.logout()
                if var_delay.get() == 1:
                    if var_utc.get() == 0:
                        now = datetime.today()
                    else:
                        now = datetime.utcnow()
                    future = startdate - now
                    delay = future.total_seconds()
                #if var_popup.get() == 0:
                #    messagebox.showinfo("Success!", "RF Survey started on %s at %s UTC.\n" % (Param_ips[i], datetime.utcnow().strftime("%H:%M:%S")))
                #else:
                log.append("RF Survey started on %s at %s UTC.\n" % (Param_ips[i], datetime.utcnow().strftime("%H:%M:%S")))
                pass
            except pxssh.ExceptionPxssh as e:
                #if var_popup.get() == 0:
                #    messagebox.showerror("Connection failed", "SSH session with %s failed, %s.\n" % (Param_ips[i], repr(e)))
                #else:
                log.append("SSH session with %s failed, %s.\n" % (Param_ips[i], repr(e)))
                pass
        #if var_popup.get() == 1:
        txt_ips.delete("1.0","end")
        for i in range(len(log)):  
            txt_ips.insert(tk.END, "%i: %s" % (i+1, log[i]))

    def stop_all():
        log = []
        try:
            username = ent_user.get()
            password = ent_pass.get()
            Param_ips = txt_ips.get(1.0, 'end-1c').splitlines()
            Param_n_ips = len(Param_ips)
            if not username or not password or not Param_ips:
                raise ValueError("")
        except ValueError as e:
            messagebox.showerror("Error!", "Provide username, password, and IPs before attempting to interrupt surveys") 

        for i in range(Param_n_ips):
            counter = 100/Param_n_ips * (i+1)
            s = pxssh.pxssh(timeout=60)
            progress['value'] = counter
            frame_inputs.update_idletasks()
            try:
                s.login(Param_ips[i], username, password)
                #print("SSH session login successful")
                #s.sendline ("ps -ef | grep 'rf_survey.py' | grep -v grep | awk '{print $2}' | xargs kill")
                s.sendline("python3 $HOME/rf_survey/kill.py")
                s.prompt()         # match the prompt
                #print(s.before)     # print everything before the prompt.
                s.logout()
                #if var_popup.get() == 0:
                #    messagebox.showinfo("Success!", "RF Survey stopped on %s at %s UTC.\n" % (Param_ips[i], datetime.utcnow().strftime("%H:%M:%S")))
                #else:
                log.append("RF Survey stopped on %s at %s UTC.\n" % (Param_ips[i], datetime.utcnow().strftime("%H:%M:%S")))
                pass
            except pxssh.ExceptionPxssh as e:
                #if var_popup.get() == 0:
                #    messagebox.showerror("Connection failed", "SSH session with %s failed, %s.\n" % (Param_ips[i], repr(e)))
                #else:
                log.append("SSH session with %s failed, %s.\n" % (Param_ips[i], repr(e)))
                pass
        #if var_popup.get() == 1:
        txt_ips.delete("1.0","end")
        for i in range(len(log)):  
            txt_ips.insert(tk.END, "%i: %s" % (i+1, log[i]))

    btn_start_all = tk.Button(master=frame_inputs, text="Start Surveys", command=start_all, highlightbackground="black", foreground="black", background="white")
    btn_start_all.grid(column=0, row=11, columnspan=2, sticky=tk.W+tk.E, padx=5, pady=5)
    btn_end_all = tk.Button(master=frame_inputs, text="Interrupt Surveys", command=stop_all, highlightbackground="black", foreground="black", background="white")
    btn_end_all.grid(column=0, row=12, columnspan=2, sticky=tk.W+tk.E, padx=5, pady=5) 
    btn_end = tk.Button(master=frame_inputs, text="Close Application", command=end, highlightbackground="black", foreground="black", background="white", width=40)
    btn_end.grid(column=0, row=13, columnspan=2, sticky=tk.W+tk.E, padx=5, pady=5) 

    progress = ttk.Progressbar(master=frame_inputs, orient=tk.HORIZONTAL, length=100, mode="determinate")
    progress.grid(column=0, row=14, columnspan=5, sticky=tk.W+tk.E, padx=5, pady=5)

    frame_inputs.grid(column=0, row=0)
    frame_inputs.grid_rowconfigure(0, weight=1)
    frame_inputs.grid_columnconfigure(0, weight=1)

    window.mainloop()

if __name__ == "__main__":
    main(sys.argv[1:])
