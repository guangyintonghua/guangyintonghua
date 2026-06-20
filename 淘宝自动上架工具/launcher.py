import subprocess, sys, os
os.chdir(os.path.dirname(os.path.abspath(__file__)))
subprocess.Popen([sys.executable, 'app.py'])
