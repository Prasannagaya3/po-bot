import subprocess, sys, os
script = os.path.join(os.path.dirname(__file__), 'po_bot_saver.py')
subprocess.Popen([sys.executable, script], creationflags=0x08000000)  # CREATE_NO_WINDOW
