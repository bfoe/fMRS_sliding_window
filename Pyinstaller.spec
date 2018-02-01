# -*- mode: python -*-
a = Analysis(['fMRS_sliding_window.py'],
             excludes=[ 'win32pdh','win32pipe',
                        'select', 'pydoc', 'pickle', '_hashlib', '_ssl',
                        'setuptools', 'scipy', 'bsddb', 'multiprocessing', 'ctypes'],
             hiddenimports=[],
             hookspath=None,
             runtime_hooks=None)
             
for d in a.datas:
    if 'pyconfig' in d[0]: 
        a.datas.remove(d)
        break
a.datas = [x for x in a.datas if not ('mpl-data\\fonts' in os.path.dirname(x[1]))]                     
a.datas = [x for x in a.datas if not ('mpl-data\fonts' in os.path.dirname(x[1]))]                     
a.datas = [x for x in a.datas if not ('mpl-data\\sample_data' in os.path.dirname(x[1]))]            
a.datas = [x for x in a.datas if not ('mpl-data\sample_data' in os.path.dirname(x[1]))]            
a.datas = [x for x in a.datas if not ('tk8.5\msgs' in os.path.dirname(x[1]))]            
a.datas = [x for x in a.datas if not ('tk8.5\images' in os.path.dirname(x[1]))]            
a.datas = [x for x in a.datas if not ('tk8.5\demos' in os.path.dirname(x[1]))]            
a.datas = [x for x in a.datas if not ('tcl8.5\opt0.4' in os.path.dirname(x[1]))]            
a.datas = [x for x in a.datas if not ('tcl8.5\http1.0' in os.path.dirname(x[1]))]            
a.datas = [x for x in a.datas if not ('tcl8.5\encoding' in os.path.dirname(x[1]))]            
a.datas = [x for x in a.datas if not ('tcl8.5\msgs' in os.path.dirname(x[1]))]            
a.datas = [x for x in a.datas if not ('tcl8.5\tzdata' in os.path.dirname(x[1]))]
a.binaries = a.binaries - TOC([
  ('libifcoremd.dll', None, None),
  ('libifportmd.dll', None, None),
  ('libiompstubs5md.dll', None, None),
  ('libmmd.dll', None, None),
  ('tbb.dll', None, None),      
  ('svml_dispmd.dll', None, None)
])
a.binaries += [('tarquin.exe', 'tarquin.exe', 'DATA')]
a.binaries += [('cvm_ia32.dll', 'cvm_ia32.dll', 'DATA')]
a.binaries += [('libfftw-3.2.2.dll', 'libfftw-3.2.2.dll', 'DATA')]
a.binaries += [('vcomp100.dll', 'vcomp100.dll', 'DATA')]
pyz = PYZ(a.pure)
exe = EXE(pyz,
          a.scripts,
          a.binaries,
          a.zipfiles,
          a.datas,
          name='fMRS_sliding_window.exe',
          debug=False,
          strip=None,
          upx=True,
          console=True)         
          