import subprocess, sys, os
ROOT = os.path.dirname(os.path.abspath(__file__))
os.chdir(ROOT)
with open('test_run.log', 'w') as out, open('test_run.log', 'a') as err:
    p = subprocess.Popen([sys.executable, '-m', 'pytest', 'backend/tests/test_backend.py', '-v'], stdout=out, stderr=err)
print('pytest started, PID', p.pid)
p.wait()
sys.exit(p.returncode)

