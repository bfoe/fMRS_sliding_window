# fMRS sliding window
Sliding window averaging for functional MRS

The Software takes a dynamic series of several Single Voxel Spectra 
and fits the Brain metabolites while doing sliding window averaging
with a user specified window size

This software is basically a script calling the MRS processing tool</br>
TARQUIN (http://tarquin.sourceforge.net) 

### Requirements
&emsp;<a href="http://www.python.org">- Python</a></br>
&emsp;<a href="http://www.numpy.org/">- Numpy</a></br>
&emsp;<a href="http://www.scipy.org/">- SciPy</a></br>
The following additional Python libraries are strongly recommended:</br>
(the software works without, but with some loss of functionality)</br>
&emsp;<a href="http://pydicom.readthedocs.io">- PyDicom</a> (to read spectro files in DICOM format)</br> 
&emsp;<a href="http://wiki.python.org/moin/TkInter">- TkInter</a> (to interactively choose input files)</br> 
&emsp;<a href="http://pypi.python.org/pypi/pywin32">- PyWin32</a> (to gracefully handle user interrupts on Windows)</br>
The program also requires the following external files from <a href="http://tarquin.sourceforge.net">TARQUIN</a></br>
&emsp;- Windows: tarquin.exe, cvm_ia32.dll, libfftw-3.2.2.dll, vcomp100.dll</br>
&emsp;- MacOS:   tarquin, libz.1.dylib, libpng15.15.dylib</br>
&emsp;- Linux:   tarquin</br>
For convenience these files are included in the "Supportfiles_" archives for the respective platforms.</br>
Extract and copy to the folder were the main python script resides.</br>

### Runs under:
- Windows
- Linux
- MacOS

### Usage:
    fMRS_sliding_window.py --spec=<spectrofile>
    fMRS_sliding_window.py --help

### MR data:
![#f03c15](https://placehold.it/15/f03c15/000000?text=+) <b> Currently supports Philips formats only </b> ![#f03c15](https://placehold.it/15/f03c15/000000?text=+)

- SPAR/SDAT format, or
- Philips DICOM format(spectra are in files called XX*)

##
### License:
<a href="http://www.gnu.org/licenses">GPLv2</a> (see also inside `fMRS_sliding_window.py`)

### Author:
Bernd Foerster, bfoerster at gmail dot com
