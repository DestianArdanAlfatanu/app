"""HTTP regression checks after check_student_seed.py, on a disposable CI database."""
import os
import subprocess
import sys
import time

import requests


def check():
    base = 'http://127.0.0.1:18002/api'
    env = dict(os.environ, ADMIN_EMAIL='ci-owner@lpk.id', ADMIN_PASSWORD='CI-owner-password-123',
               JWT_SECRET='ci-only-secret-not-for-production-123456', LPK_DEMO='0')
    process = subprocess.Popen([sys.executable, '-m', 'uvicorn', 'server:app', '--host', '127.0.0.1',
                                '--port', '18002'], cwd=os.path.dirname(__file__), env=env,
                               stdout=subprocess.DEVNULL)
    try:
        for _ in range(100):
            try:
                if requests.get(base+'/', timeout=1).status_code == 200:
                    break
            except requests.ConnectionError:
                pass
            time.sleep(.1)
        else:
            raise AssertionError('Test backend did not start')
        login = {'email': 'siswa.ci-b@lpk.id', 'password': 'Initial-test-123'}
        r = requests.post(base+'/student/auth/login', json=login, timeout=5)
        r.raise_for_status()
        old_headers = {'Authorization': 'Bearer '+r.json()['token']}
        r = requests.post(base+'/student/auth/change-password', headers=old_headers,
                          json={'old_password': 'wrong-current-password', 'new_password': 'Changed-test-456'}, timeout=5)
        assert r.status_code == 400, f'Wrong current password must not trigger 401 logout: {r.status_code}'
        assert requests.get(base+'/student/auth/me', headers=old_headers, timeout=5).status_code == 200
        r = requests.post(base+'/student/auth/change-password', headers=old_headers,
                          json={'old_password': login['password'], 'new_password': 'Changed-test-456'}, timeout=5)
        r.raise_for_status()
        new_headers = {'Authorization': 'Bearer '+r.json()['token']}
        me = requests.get(base+'/student/auth/me', headers=new_headers, timeout=5)
        me.raise_for_status()
        assert not me.json()['must_change_password']
        assert requests.get(base+'/student/auth/me', headers=old_headers, timeout=5).status_code == 401
        assert requests.post(base+'/student/auth/login', json=login, timeout=5).status_code == 401
        login['password'] = 'Changed-test-456'
        assert requests.post(base+'/student/auth/login', json=login, timeout=5).status_code == 200
        print('Portal password change and re-login regression checks passed')
    finally:
        process.terminate()
        process.wait(timeout=10)


if __name__ == '__main__':
    check()
