#!/usr/bin/python
#
# fMRS_sliding_window - sliding window averaging for functional MRS data
#     
# author: Bernd Foerster, bfoerster at gmail dot com
# 
# ----- VERSION HISTORY -----
#
# Version 0.1 - 31, January 2018
#   - public release on GitHub
#    
# ----- LICENSE -----                 
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License (GPL) as published 
# by the Free Software Foundation, either version 2 of the License, or
# (at your option) any later version. For more detail see the 
# GNU General Public License at <http://www.gnu.org/licenses/>.
# also the following additional license terms apply:
#
# ----- REQUIREMENTS ----- 
#
#   This program was developed under Python Version 2.7.6 for Windows 32bit
#   A windows standalone executable can be "compiled" with PyInstaller
#
#   The following Python libraries are required:
#     - NumPy (http://www.numpy.org/)
#   The following additional Python libraries are strongly recommended:
#   (the software works without, but with some loss of functionality)
#     To read spectro files in DICOM format 
#     - pydicom (http://pydicom.readthedocs.io)
#     To interactively choose input files 
#     - tkinter (http://wiki.python.org/moin/TkInter)
#     To gracefully handle user interrupts on Windows
#     - pywin32 (http://pypi.python.org/pypi/pywin32) 
#     
#   The program also requires the following external files
#   from TARQUIN (http://tarquin.sourceforge.net/):
#     - Windows: tarquin.exe, cvm_ia32.dll, libfftw-3.2.2.dll, vcomp100.dll
#     - MacOS:   tarquin, libz.1.dylib, libpng15.15.dylib
#     - Linux:   tarquin
#



Program_version = "v0.1" # program version

import sys
import math
import os
import signal
import random
import shutil
import subprocess
import time
import datetime
from getopt import getopt
from getopt import GetoptError
from distutils.version import LooseVersion

import csv
import numpy


TK_installed=True
try: from tkFileDialog import askopenfilename # Python 2
except: 
  try: from tkinter.filedialog import askopenfilename; # Python3
  except: TK_installed=False
try: import Tkinter as tk; # Python2
except: 
  try: import tkinter as tk; # Python3
  except: TK_installed=False
try: import win32gui, win32console
except: pass #silent  

FNULL = open(os.devnull, 'w')
old_target, sys.stderr = sys.stderr, FNULL # replace sys.stdout 
pydicom_installed=True
try: import dicom
except: pydicom_installed=False
sys.stderr = old_target # re-enable

pywin32_installed=True
try: import win32console, win32gui, win32con
except: pywin32_installed=True


if sys.platform=="win32": slash='\\'
else: slash='/'

def exit (code):
    # cleanup 
    try: shutil.rmtree(tempdir)
    except: pass # silent
    if pywin32_installed:
        try: # reenable console windows close button (useful if called command line or batch file)
            hwnd = win32console.GetConsoleWindow()
            hMenu = win32gui.GetSystemMenu(hwnd, 1)
            win32gui.DeleteMenu(hMenu, win32con.SC_CLOSE, win32con.MF_BYCOMMAND)
        except: pass #silent
    sys.exit(code)
def signal_handler(signal, frame):
    lprint ('User abort')
    exit(1)
def logwrite(message): 
    sys.stderr.write(datetime.datetime.now().strftime("%d/%m/%Y %H:%M:%S"))
    sys.stderr.write(' ('+ID+') - '+message+'\n')
    sys.stderr.flush()   
def lprint (message):
    print (message)
    logwrite(message)
def checkfile(file): # generic check if file exists
    if not os.path.isfile(file): 
        lprint ('ERROR:  File "'+file+'" not found '); exit(1)    
def expdecay(x,A,T2): # T2 of long component fixed to CSF_T2
    return A*numpy.exp(-x/T2)
def isDICOM (file):
    try: f = open(file, "rb")
    except: lprint ('ERROR: opening file'+file); exit(1)
    try:
        test = f.read(128) # through the first 128 bytes away
        test = f.read(4) # this should be "DICM"
        f.close()
    except: return False # on error probably not a DICOM file
    if test == "DICM": return True 
    else: return False    
def _get_from_SPAR (input, varstring):
    if varstring[len(varstring)-1] != ' ': varstring += ' ' # requires final space
    value = [text.split(':')[1] for text in input if text.split(':')[0]==varstring]
    if len(value)>0: value = value[0]
    else: lprint ('ERROR: unable to read parameter "'+varstring+'" in SPAR'); sysexit(1)
    return value        
def delete (file):
    try: os.remove(file)
    except: pass #silent
def run (command, parameters):
    string = '"'+command+'" '+parameters
    if debug: logwrite (string)
    process = subprocess.Popen(string, env=my_env,
                  shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    (stdout, stderr) = process.communicate()  
    if debug: logwrite (stdout)
    if debug: logwrite (stderr)    
    if process.returncode != 0: 
        lprint ('ERROR:  returned from "'+os.path.basename(command)+
                '", for details inspect logfile in debug mode')
        exit(1)
    return stdout    
def _vax_to_ieee_single_float(data): # borrowed from the python VeSPA project
    #Converts a float in Vax format to IEEE format.
    #data should be a single string of chars that have been read in from 
    #a binary file. These will be processed 4 at a time into float values.
    #Thus the total number of byte/chars in the string should be divisible
    #by 4.
    #Based on VAX data organization in a byte file, we need to do a bunch of 
    #bitwise operations to separate out the numbers that correspond to the
    #sign, the exponent and the fraction portions of this floating point
    #number
    #role :      S        EEEEEEEE      FFFFFFF      FFFFFFFF      FFFFFFFF
    #bits :      1        2      9      10                               32
    #bytes :     byte2           byte1               byte4         byte3    
    f = []; nfloat = int(len(data) / 4)
    for i in range(nfloat):
        byte2 = data[0 + i*4]; byte1 = data[1 + i*4]
        byte4 = data[2 + i*4]; byte3 = data[3 + i*4]
        # hex 0x80 = binary mask 10000000
        # hex 0x7f = binary mask 01111111
        sign  =  (ord(byte1) & 0x80) >> 7
        expon = ((ord(byte1) & 0x7f) << 1 )  + ((ord(byte2) & 0x80 ) >> 7 )
        fract = ((ord(byte2) & 0x7f) << 16 ) +  (ord(byte3) << 8 ) + ord(byte4)
        if sign == 0: sign_mult = 1.0
        else: sign_mult = -1.0;
        if 0 < expon:
            # note 16777216.0 == 2^24  
            val = sign_mult * (0.5 + (fract/16777216.0)) * pow(2.0, expon - 128.0)   
            f.append(val)
        elif expon == 0 and sign == 0: f.append(0)
        else: f.append(0) # may want to raise an exception here ...
    return f 
def usage():
    lprint ('')
    lprint ('Usage: '+Program_name+' [options] --spec=<spectrofile>')
    lprint ('')
    lprint ('   Available options are:')
    lprint ('       --outdir=<path>    : output directory, if not specified')
    lprint ('                            output goes to current working directory')
    lprint ('       --window=<integer> : number of spectra to average in sliding window')
    lprint ('                            should be within 1-50, if not specified ')
    lprint ('                            the user will be prompted to input interactively')
    lprint ('       --help (or -h)     : usage and help')
    lprint ('       --version          : version information')
    lprint ('')
def help():
    lprint ('')
    lprint ('the <spectrofile> can be a SPAR/SDAT file') 
    lprint ('   (either one can be specified, but both have to be present)')
    lprint ('or a Philips DICOM spectroscopy file')
    lprint ('   (when exported from the scanner these are called XX*)')
    lprint ('')
    lprint ('Limitations:')
    lprint (' - to read DICOM format the "pydicom" library is required')
    lprint ('   for installation instructions see http://pydicom.readthedocs.io')     
    lprint (' - to be able to interactively choose the input spectro file')
    lprint ('   the python "tkinter" library is required')
    lprint ('   for installation instructions see http://wiki.python.org/moin/TkInter')    
    lprint ('')

# general initialization stuff   
debug=False; NIFTI_Input=False; SPAR_Input=True
filename=''; workfile=''
slash='/'; 
if sys.platform=="win32": slash='\\' # not really needed, but looks nicer ;)
Program_name = os.path.basename(sys.argv[0]); 
if Program_name.find('.')>0: Program_name = Program_name[:Program_name.find('.')]
basedir = os.getcwd()+slash # current working directory is the default output directory 
for arg in sys.argv[1:]: # look in command line arguments if the output directory specified
    if "--outdir" in arg: basedir = os.path.abspath(arg[arg.find('=')+1:])+slash #
ID = str(random.randrange(1000, 2000));ID=ID[:3] # create 3 digit random ID for logfile 
try: sys.stderr = open(basedir+Program_name+'.log', 'a'); # open logfile to append
except: print('Problem opening logfile: '+basedir+Program_name+'.log'); exit(2)
my_env = os.environ.copy()
FNULL = open(os.devnull, 'w')
# catch signals to be able to cleanup temp files before exit
signal.signal(signal.SIGINT, signal_handler)  # keyboard interrupt
signal.signal(signal.SIGTERM, signal_handler) # kill/shutdown
if  'SIGHUP' in dir(signal): signal.signal(signal.SIGHUP, signal_handler)  # shell exit (linux)
# make tempdir
timestamp=datetime.datetime.now().strftime("%Y%m%d%H%M%S")
tempname='.'+Program_name+'_temp'+timestamp
tempdir=basedir+tempname+slash
if os.path.isdir(tempdir): # this should never happen
    lprint ('ERROR:  Problem creating temp dir (already exists)'); exit(1) 
try: os.mkdir (tempdir)
except: lprint ('ERROR:  Problem creating temp dir: '+tempdir); exit(1) 

# configuration specific initializations
# compare python versions with e.g. if LooseVersion(python_version)>LooseVersion("2.7.6"):
python_version = str(sys.version_info[0])+'.'+str(sys.version_info[1])+'.'+str(sys.version_info[2])
# sys.platform = [linux2, win32, cygwin, darwin, os2, os2emx, riscos, atheos, freebsd7, freebsd8]
if sys.platform=="win32":
    os.system("title "+Program_name)
    try: resourcedir = sys._MEIPASS+slash # when on PyInstaller 
    except: # in plain python this is where the script was run from
        resourcedir = os.path.abspath(os.path.dirname(sys.argv[0]))+slash; 
    command='attrib'; parameters=' +H "'+tempdir[:len(tempdir)-1]+'"'; 
    run(command, parameters) # hide tempdir
    if pywin32_installed:
        try: # disable console windows close button (substitutes catch shell exit under linux)
            hwnd = win32console.GetConsoleWindow()
            hMenu = win32gui.GetSystemMenu(hwnd, 0)
            win32gui.DeleteMenu(hMenu, win32con.SC_CLOSE, win32con.MF_BYCOMMAND)
        except: pass #silent        
else:
    resourcedir = os.path.abspath(os.path.dirname(sys.argv[0]))+slash;
if TK_installed:        
    TKwindows = tk.Tk(); TKwindows.withdraw() #hiding tkinter window
    TKwindows.update()
    # the following tries to disable showing hidden files/folders under linux
    try: TKwindows.tk.call('tk_getOpenFile', '-foobarz')
    except: pass
    try: TKwindows.tk.call('namespace', 'import', '::tk::dialog::file::')
    except: pass
    try: TKwindows.tk.call('set', '::tk::dialog::file::showHiddenBtn', '1')
    except: pass
    try: TKwindows.tk.call('set', '::tk::dialog::file::showHiddenVar', '0')
    except: pass
    TKwindows.update()

# parse commandline parameters (if present)
try: opts, args =  getopt( sys.argv[1:],'h',['help','version','spec=','outdir=', 'window='])
except:
    error=str(sys.argv[1:]).replace("[","").replace("]","")
    if "-" in str(error) and not "--" in str(error): 
          lprint ('ERROR: Commandline '+str(error)+',   maybe you mean "--"')
    else: lprint ('ERROR: Commandline '+str(error))
    usage(); exit(2)
if len(args)>0: 
    lprint ('ERROR: Commandline option "'+args[0]+'" not recognized')
    lprint ('       (see logfile for details)')
    logwrite ('       Calling parameters: '+str(sys.argv[1:]).replace("[","").replace("]",""))
    usage(); exit(2)  
argDict = dict(opts)
if "--outdir" in argDict and not [True for arg in sys.argv[1:] if "--outdir" in arg]:
    # "--outdir" must be spelled out, getopt also excepts substrings (e.g. "--outd"), but
    # my simple pre-initialization code to get basedir early doesn't
    lprint ('ERROR: Commandline option "--outdir" must be spelled out')
    usage(); exit(2)
if '-h' in argDict: usage(); help(); exit(0)   
if '--help' in argDict: usage(); help(); exit(0)  
if '--version' in argDict: lprint (Program_name+' '+Program_version); exit(0)
if '--spec' in argDict: filename=argDict['--spec']; checkfile(filename)
window_by_arg = False
if '--window' in argDict: 
    window_str = argDict['--window']
    try: sliding_window=int(window_str)
    except: lprint ('ERROR: problem converting --window argument to number'); exit(2)
    if sliding_window<1:  lprint ('ERROR: sliding window must be >=1');  exit(2)
    if sliding_window>50: lprint ('ERROR: sliding window must be <=50'); exit(2)
    window_by_arg = True
    
#choose file with tkinter
try:
   TKwindows = tk.Tk(); TKwindows.withdraw() #hiding tkinter window
   TKwindows.update()
except: pass
# the following tries to disablle showing hidden files/folders under linux
try: TKwindows.tk.call('tk_getOpenFile', '-foobarz')
except: pass
try: TKwindows.tk.call('namespace', 'import', '::tk::dialog::file::')
except: pass
try: TKwindows.tk.call('set', '::tk::dialog::file::showHiddenBtn', '1')
except: pass
try: TKwindows.tk.call('set', '::tk::dialog::file::showHiddenVar', '0')
except: pass
try: TKwindows.update()
except: pass
# this is the actual file open dialogue
Interactive = False
if TK_installed:
   # Choose Spectro file
    if filename == "": # use interactive input if not specified in commandline
        filename = askopenfilename(title="Choose Spectro file")
        if filename == "": lprint ('ERROR:  No Spectro input file specified'); exit(2)
        Interactive = True
    TKwindows.update()
else:
    if filename == "": 
        lprint ('ERROR:  No Spectro input file specified')
        lprint ('        to interactively choose input files you need tkinter')
        lprint ('        on Linux try "yum install tkinter"')
        lprint ('        on MacOS install ActiveTcl from:')
        lprint ('        http://www.activestate.com/activetcl/downloads')  
        usage()
        exit(2)
filename = os.path.abspath(filename)
TKwindows.update()
try: win32gui.SetForegroundWindow(win32console.GetConsoleWindow())
except: pass #silent

# read input from keyboard
if not window_by_arg:
    sliding_window=0; OK=False
    while not OK:
        dummy = raw_input("Enter sliding window [1..50]: ")
        if dummy == '': print ("Input Error")
        try: sliding_window = int(dummy);
        except: print ("Input Error")
        if sliding_window>=1 and sliding_window<=50: OK=True 


# ----- start to really do something -----
lprint ('Starting '+Program_name+' '+Program_version)
lprint ('Sliding window is set to '+str(sliding_window))
logwrite ('Calling sequence    '+' '.join(sys.argv))
logwrite ('OS & Python version '+sys.platform+' '+python_version)
logwrite ('tkinter & pydicom   '+str(TK_installed)+' '+str(pydicom_installed))

# read data
if isDICOM (filename):  # read DICOM  
    try: Dset = dicom.read_file(filename)
    except: lprint ('ERROR: reading DICOM file'); exit(1)
    # do some checks
    try: Modality=str(Dset.Modality) # must be MR           
    except: lprint ('ERROR: Unable to determine DICOM Modality'); exit(1)
    if Modality!='MR': lprint ('DICOM Modality not MR'); exit(1)
    try: Manufacturer=str(Dset.Manufacturer) # currently Philips only
    except: lprint ('ERROR: Unable to determine Manufacturer'); exit(1)
    if not Manufacturer.find("Philips")>=0: 
        lprint ('ERROR: Currently only Philips DICOM implemented'); exit(1)
    try: ImageType=str(Dset.ImageType) # sanity check: spectroscopy   
    except: 
        lprint ('ERROR: Unable to determine if DICOM containes spectroscopy data'); exit(1)
    if not ImageType.find("SPECTROSCOPY")>=0: 
        lprint ('ERROR: DICOM file does not contain spectroscopy data'); exit(1)
    # start reading data from DICOM
    ReIm=2 # real and imagininary parts
    try: samples=Dset.SpectroscopyAcquisitionDataColumns # n_points in time/frequency domain
    except: lprint ('ERROR: reading number of samples from DICOM file'); exit(1)
    try: rows=Dset[0x2001,0x1081].value #NumberOfDynamicScans
    except: lprint ('ERROR: reading number of dynamics from DICOM file'); exit(1)
    if rows<=1: lprint ('ERROR: not a multi TE aquisition'); exit(1)
    if rows<=min_nTE: lprint ('ERROR: minimum number of'+str(min_nTE)+'TEs required'); exit(1)
    # check if number of points is correct
    ndata_points=len (numpy.asarray(Dset[0x5600,0x0020].value))
    if ndata_points==2*rows*samples*ReIm: 
        ActRef=2 # two spectra, actual and water, this is the normal case
    elif ndata_points==rows*samples*ReIm: 
        ActRef=1 # only one spectrum
    else: 
        lprint ('ERROR: Unexpected number of total datapoints'); exit(1)  
    #read data
    spectro_rawdata = numpy.asarray(Dset[0x5600,0x0020].value)
else: # read SDAT
    # find SPAR/SDAT pair
    path=os.path.dirname(filename)
    name=os.path.splitext(os.path.basename(filename))[0]
    ext=os.path.splitext(os.path.basename(filename))[1]
    if ext.lower() == ".spar": 
      SPARfile=filename 
      SDATfile=[f for f in os.listdir(path) if f.lower().endswith('.sdat') and f.startswith(name)]
      SDATfile=SDATfile[0] # may want to raise an exception here ...
    elif ext.lower() == ".sdat":
      SDATfile=filename 
      SPARfile=[f for f in os.listdir(path) if f.lower().endswith('.spar') and f.startswith(name)]
      SPARfile=SPARfile[0] # may want to raise an exception here ...
    else: lprint ('ERROR: file extension should be SDAT/SPAR'); exit(1)
    # open SPAR
    try: input = open(SPARfile, "r").readlines()
    except: lprint ('ERROR: reading SPAR file'); exit(1)
    samples = int(_get_from_SPAR (input, 'samples'))
    rows = int(_get_from_SPAR (input, 'rows'))
    ActRef = int(_get_from_SPAR (input, 'mix_number'))
    if ActRef != 1: 
       lprint ('ERROR: SPAR/SDAT file seems to be a reference spectrum, choose an actual spectrum'); 
       exit(1)
    # guess missing data not contained in the SPAR file
    ReIm=2   # real and imagininary parts
logwrite ('Reading File '+filename)   
lprint ('') # spacer
    
       
# start processing with TARQUIN
##delete (tempdir+'tarquin_T2fit.csv') # cleanup
##delete (tempdir+'tarquin_T2fit.txt') # cleanup
##delete (tempdir+'avlist.csv')        # cleanup
##delete (tempdir+workfile)            # cleanup
results = []
for n_spectra in range(rows):
   space=''
   if n_spectra<9: space=' '
   lprint ('Processing spectrum '+space+str(n_spectra+1)+' of '+str(rows))
   avfile = open(tempdir+'avlist.csv', 'w')
   for i in range (sliding_window):
      number = n_spectra+1+i-int(sliding_window/2)
      if (number>0) and (number<=rows):
         avfile.write(str(number)+"\n")  
   avfile.close()
   arguments=' --input "'+filename+'"'
   arguments+=' --format philips'
   arguments+=' --av_list "'+tempdir+'avlist.csv"' 
   arguments+=' --output_csv  "'+tempdir+'tarquin_fMRS_fit.csv"'
   arguments+=' --ref 4.66 --max_metab_shift 0.015'
   arguments+=' --auto_phase true --dyn_freq_corr true'
   arguments+=' --start_pnt 20 --ref_signals 1h_naa --dref_signals 1h_naa --pul_seq press --int_basis 1h_brain'
   run (resourcedir+'tarquin', arguments)
   with open(tempdir+'tarquin_fMRS_fit.csv', 'r') as csvfile:
      data = csvfile.readlines()   
      header  = data[1]
      results = numpy.append (results, data[2])
 
#fit & write results
lprint ('') # spacer
stp=''; space = ' ' # for name collision detection
if os.path.isfile(os.path.splitext(os.path.basename(filename))[0]+stp+'.csv'): stp='_'+timestamp+ID
f = open(os.path.splitext(os.path.basename(filename))[0]+stp+'.csv', 'w')
f.write(Program_name+space+Program_version+' Results:\n')
f.write(header)
f.write(results)
f.close()

#delete tempdir
try: shutil.rmtree(tempdir)
except: pass # silent
lprint ('done\n')
sys.stderr.close() # close logfile

#reenable console windows close button
if pywin32_installed:
    try:
        hwnd = win32console.GetConsoleWindow()
        hMenu = win32gui.GetSystemMenu(hwnd, 1)
        win32gui.DeleteMenu(hMenu, win32con.SC_CLOSE, win32con.MF_BYCOMMAND)
    except: pass #silent

#pause
if Interactive:
    if sys.platform=="win32": os.system("pause") # windows
    else: 
        #os.system('read -s -n 1 -p "Press any key to continue...\n"')
        import termios
        print("Press any key to continue...")
        fd = sys.stdin.fileno()
        oldterm = termios.tcgetattr(fd)
        newattr = termios.tcgetattr(fd)
        newattr[3] = newattr[3] & ~termios.ICANON & ~termios.ECHO
        termios.tcsetattr(fd, termios.TCSANOW, newattr)
        try: result = sys.stdin.read(1)
        except IOError: pass
        finally: termios.tcsetattr(fd, termios.TCSAFLUSH, oldterm)   


