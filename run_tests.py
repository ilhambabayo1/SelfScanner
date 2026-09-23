import subprocess, sys, os
os.chdir(r'C:\Users\HP USER\OneDrive\Documents\Self Scanner')
with open('test_run.log', 'w') as out, open('test_run.log', 'a') as err:
    p = subprocess.Popen([sys.executable, '-m', 'pytest', 'backend\\tests\\test_backend.py', '-v'], stdout=out, stderr=err)
print('pytest started, PID', p.pid)
