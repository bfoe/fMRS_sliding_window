#!/usr/bin/python
#
# fMRS_sstatistics - calculate statistics based on output from "fMRS_sliding_window"
#
# author: Bernd Foerster, bfoerster at gmail dot com
# 
# ----- VERSION HISTORY -----
#
# Version 0.1 - 20, February 2018
#   - public release on GitHub
#   - implementation only for a specific hardcoded paradigm
#   - for now the statistics is a simple pearson correlation coefficient 
#    
# ----- LICENSE -----                 
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License (GPL) as published 
# by the Free Software Foundation, either version 2 of the License, or
# (at your option) any later version. For more detail see the 
# GNU General Public License at <http://www.gnu.org/licenses/>.
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
from scipy import stats
try: 
    from scipy.sparse.csgraph import _validation    # needed for pyinstaller
    from scipy.special import _ufuncs_cxx           # needed for pyinstaller
except: pass


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
def delete (file):
    try: os.remove(file)
    except: pass #silent      
def usage():
    lprint ('')
    lprint ('Usage: '+Program_name+' [options] --csv=<csvfile> --paradigm=<paradigmfile>')
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
    lprint ('the <csvfile> is the output from fMRS_sliding_window') 
    lprint ('')
    lprint ('the <paradigmfile> is a textfile specifying the paradigm')
    lprint ('              in form of 0 and 1 values separated by lines') 
    lprint ('              if unspecified, the default "paradigm.txt"wil be used') 
    lprint ('')
    lprint ('Limitations:')   
    lprint (' - to be able to interactively choose the input files')
    lprint ('   the python "tkinter" library is required')
    lprint ('   for installation instructions see http://wiki.python.org/moin/TkInter')    
    lprint ('')

# general initialization stuff   
debug=False; NIFTI_Input=False; SPAR_Input=True
csvfilename=''; paradigmfile=''
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
# calc timestamp
timestamp=datetime.datetime.now().strftime("%Y%m%d%H%M%S")

# configuration specific initializations
# compare python versions with e.g. if LooseVersion(python_version)>LooseVersion("2.7.6"):
python_version = str(sys.version_info[0])+'.'+str(sys.version_info[1])+'.'+str(sys.version_info[2])
# sys.platform = [linux2, win32, cygwin, darwin, os2, os2emx, riscos, atheos, freebsd7, freebsd8]
if sys.platform=="win32":
    os.system("title "+Program_name)
    try: resourcedir = sys._MEIPASS+slash # when on PyInstaller 
    except: # in plain python this is where the script was run from
        resourcedir = os.path.abspath(os.path.dirname(sys.argv[0]))+slash; 
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
if '--csv' in argDict: csvfilename=argDict['--csv']; checkfile(csvfilename)
if '--paradigm' in argDict: paradigmfile=argDict['--paradigm']; checkfile(paradigmfile)
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
   # Choose CSV file
    if csvfilename == "": # use interactive input if not specified in commandline
        csvfilename = askopenfilename(title="Choose CSV file")
        if csvfilename == "": lprint ('ERROR:  No CSV input file specified'); exit(2)
        Interactive = True
    TKwindows.update()
else:
    if csvfilename == "": 
        lprint ('ERROR:  No CSV input file specified')
        lprint ('        to interactively choose input files you need tkinter')
        lprint ('        on Linux try "yum install tkinter"')
        lprint ('        on MacOS install ActiveTcl from:')
        lprint ('        http://www.activestate.com/activetcl/downloads')  
        usage()
        exit(2)
csvfilename = os.path.abspath(csvfilename)
#if TK_installed:
   # Choose Paradigm file
#    if paradigmfile == "": # use interactive input if not specified in commandline
#        paradigmfile = askopenfilename(title="Choose Paradigm file")
#    TKwindows.update()
#if paradigmfile == "": paradigmfile = "Paradigm.txt"
#paradigmfile = os.path.abspath(paradigmfile)
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
logwrite ('tkinter '+str(TK_installed))

# read CSV header
with open(csvfilename) as f:
    data = f.readlines()
    CSV_header1 = data[0] 
    CSV_header2 = data[1]  
# read CSV data
metabolites = numpy.genfromtxt(csvfilename,delimiter=",",skip_header=2)

# read Paradigm data
#with open(paradigmfile, 'rb') as f:
#   paradigm_raw = csv.reader(f)
#   paradigm_lst = []
#   for row in paradigm_raw: 
#      try: paradigm_lst.append(row[0])
#      except: lprint ('ERROR:  reading Paradigm values'); exit (2)  
#try: paradigm = numpy.asarray(paradigm_lst,int)
#except: lprint ('ERROR:  converting Paradigm values to numbers'); exit (2)  
#if len(paradigm_lst) !=  paradigm.shape[0]:
#   lprint ('ERROR:  converting Paradigm values')
#   exit (2)        

# set fixed paradigm  
paradigm = numpy.zeros (360, dtype=float)
for i in range (60,120): paradigm[i]=1.
for i in range (180,240): paradigm[i]=1.
for i in range (300,360): paradigm[i]=1.
#print (paradigm)

# consistency check CSV-Paradigm
if paradigm.shape[0] != metabolites.shape[0]:
   lprint ('ERROR:  dimension mismatch of CSV data ('+str(metabolites.shape[0])+') and Paradigm ('+str(paradigm.shape[0])+')')
   exit (2)   
   
# cut off last paradigm block
max_shift=60
paradigm = paradigm [0:paradigm.shape[0]-max_shift]   

 
# calc & write Paradigm data with sliding window
paradigm_sl_win = numpy.zeros(paradigm.shape[0], dtype=float);
for i in range (paradigm.shape[0]):
   start = i-int(sliding_window/2)
   if start < 0: start=0
   end   = i+int(sliding_window/2)
   if end > paradigm.shape[0]: end = paradigm.shape[0]
   #print (start,end, paradigm[start:end+1],numpy.mean(paradigm[start:end+1]))
   paradigm_sl_win[i] = numpy.mean(paradigm[start:end+1])
#f = open(os.path.splitext(os.path.basename(paradigmfile))[0]+'_SlWin_.txt', 'w')
#for i in range (paradigm_sl_win.shape[0]):
#   f.write(str(paradigm_sl_win[i])+"\n")
#f.close ()   

FNULL = open(os.devnull, 'w')
old_target, sys.stderr = sys.stderr, FNULL # replace sys.stdout    
pvalue = numpy.zeros ([metabolites.shape[1],max_shift], dtype=float)
correlation = numpy.zeros ([metabolites.shape[1],max_shift], dtype=float) 
for j in  range (max_shift): 
   for i in  range (3, metabolites.shape[1]):
      #diff = paradigm_sl_win[0:paradigm_sl_win.shape[0]-j] - metabolites[0:metabolites.shape[0]-j,i]
      #diff = paradigm_sl_win[:] - metabolites[:,i]      
      #t_value[i,j] = (numpy.average(diff) * numpy.sqrt(len(diff))) / (numpy.std(diff, ddof=1))
      correlation[i,j], pvalue[i,j] = stats.stats.pearsonr (paradigm_sl_win[:], metabolites[j:j+paradigm_sl_win.shape[0],i])
sys.stderr = old_target # re-enable            
      
#write results
lprint ('') # spacer
stp=''; space = ' ' # for name collision detection
if os.path.isfile(os.path.splitext(os.path.basename(csvfilename))[0]+'_correlations'+stp+'.csv'): stp='_'+timestamp+ID
f1 = open(os.path.splitext(os.path.basename(csvfilename))[0]+'_correlations'+stp+'.csv', 'w')
f2 = open(os.path.splitext(os.path.basename(csvfilename))[0]+'_pvalues'+stp+'.csv', 'w')
f1.write(Program_name+space+Program_version+' Results:\n')
f2.write(Program_name+space+Program_version+' Results:\n')
f1.write(CSV_header2)
f2.write(CSV_header2)
for j in  range (max_shift): 
   for i in  range ( metabolites.shape[1]):
      f1.write(str(correlation[i,j]))
      f2.write(str(pvalue[i,j]))
      if i<metabolites.shape[1]-1: f1.write (',')
      if i<metabolites.shape[1]-1: f2.write (',')
   f1.write ('\n')
   f2.write ('\n')   
f1.close()
f2.close()  

#analyse results
Found = False
treshold = 0.707 #(r-squared = 0.5, means 50% chance that tis is really correlated)
tresh2 = 0.5
p_tresh = 0.05
mask = pvalue<p_tresh
results =  correlation*mask
NaNs = numpy.isnan(results)
results[NaNs]=0
metabolitenames = CSV_header2.rstrip('\n').split(",")
for i in  range ( metabolites.shape[1]):
   amax = round(numpy.amax (results[i,:])*100.)/100.
   amin = round(numpy.amin (results[i,:])*100.)/100.
   imax = numpy.argmax (results[i,:])
   imin = numpy.argmin (results[i,:])
   c_max = format(amax, '.2f') 
   p_max = format(pvalue[i,imax], '.2E')
   c_min = format(amin, '.2f') 
   p_min = format(pvalue[i,imin], '.2E')   
   if amax>treshold:
      Found = True   
      lprint ('Significant correlation = '+c_max+' (p='+p_max+') in metabolite "'+metabolitenames[i]+'" at shift '+str(imax))
   elif amax>tresh2:
      Found = True 
      lprint ('Possible    correlation = '+c_max+' (p='+p_max+') in metabolite "'+metabolitenames[i]+'" at shift '+str(imax))   
   if amin<-1.0*treshold: 
      Found = True 
      lprint ('Significant correlation =' +c_min+' (p='+p_min+') in metabolite "'+metabolitenames[i]+'" at shift '+str(imin))
   if amin<-1.0*treshold: 
      Found = True 
      lprint ('Possible    correlation =' +c_min+' (p='+p_min+') in metabolite "'+metabolitenames[i]+'" at shift '+str(imin))
   
if not Found: 
   lprint ('No correlations found (correlation>'+str(treshold)+', p<'+str(p_tresh)+')') 
lprint ('\ndone\n')    
    
# paired t-test: http://iaingallagher.tumblr.com/post/50980987285/t-tests-in-python
#baseline  = numpy.asarray([67.2, 67.4, 71.5, 77.6, 86.0, 89.1, 59.5, 81.9, 105.5])
#follow_up = numpy.asarray([62.4, 64.6, 70.4, 62.6, 80.1, 73.2, 58.2, 71.0, 101.0])
#diff = baseline - follow_up
#t_score, p_value = stats.ttest_rel(baseline,follow_up)
#print (t_score, p_value)
#print (numpy.correlate (baseline, follow_up))


# paired t-test: https://stackoverflow.com/questions/2324438/how-to-calculate-the-statistics-t-test-with-numpy
#follow_up  = numpy.asarray([55.0, 55.0, 47.0, 47.0, 55.0, 55.0, 55.0, 63.0])
#baseline = numpy.asarray([54.0, 56.0, 48.0, 46.0, 56.0, 56.0, 55.0, 62.0])
#diff = baseline - follow_up
#t_score, p_value = stats.ttest_rel(baseline,follow_up)
#print (t_score, p_value)
#t_value = (numpy.average(diff) * numpy.sqrt(len(diff))) / (numpy.std(diff, ddof=1))
#s = numpy.random.standard_t(len(diff), size=1000000)
#p = numpy.sum(s<t_value) / float(len(s))
#p_val = 2 * min(p, 1 - p)
#print (t_value, p_val)


#reenable console windows close button
sys.stderr.close() # close logfile
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


