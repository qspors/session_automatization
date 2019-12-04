import subprocess
import json
import os
import time
import logging
from shlex import quote


class SessionManager:
    def __init__(self):
        self.log = logging.getLogger('Log Engine')
        self.fh = logging.FileHandler('/var/log/session-handler.log')
        self.fh.setFormatter(
            logging.Formatter('%(asctime)s | %(process)d | [%(levelname)s] | %(message)s', datefmt='%Y-%m-%d %H:%M:%S'))
        self.log.addHandler(self.fh)
        self.log.setLevel(logging.INFO)

    def separate_users(self):
        self.log.info(msg='Separate users')
        secret = subprocess.Popen(["aws", "secretsmanager", "get-secret-value", "--secret-id",
                                   "arn:aws:secretsmanager:us-east-1:492239587024:secret:/userlist-MDXmYW",
                                   "--output",
                                   "json"],
                                  stdout=subprocess.PIPE)
        output = json.loads(secret.communicate()[0].decode('utf-8'))
        existing_user_list = self.local_users()
        try:
            for item in eval(output.get('SecretString')):
                for key, value in item.items():
                    self.log.info('Start working on user: {} ###'.format(key))
                    if quote(key) in existing_user_list:
                        self.log.warning('User: {} is Exists'.format(key))
                        self.log.info('Check User: {} sudo membership'.format(key))
                        if value == 'true':
                            self.log.info('User: {} is global sudo group member'.format(key))
                            self.log.info('Check local membership'.format(key))
                            self.sudo(username=key)
                        else:
                            self.log.info('User: {} is not global sudo membership'.format(key))
                    elif value == 'false':
                        self.user_add(username=key)
                    elif value == 'true':
                        self.user_add(username=key)
                        time.sleep(1)
                        self.sudo(username=key)
                    else:
                        pass
        except ValueError as e:
            self.log.error('Error: {}'.format(e))
            pass

    def sudo(self, username: str):
        try:
            get_local_user_list = subprocess.Popen(["cut", "-d ", "-f1", "/etc/sudoers"],
                                                   stdout=subprocess.PIPE)
            local_output = get_local_user_list.communicate()[0].decode('utf-8')
            local_output = local_output.replace("#", "").replace("%", "")
            userlist = []
            for item in local_output.splitlines():
                if '#' in item:
                    continue
                elif '_' in item:
                    continue
                else:
                    if len(item) > 3:
                        userlist.append(item)
            local_userlist = list(dict.fromkeys(userlist))
            if username in local_userlist:
                return self.log.warning('User: {} Already in sudoers'.format(username))
            self.log.info('Add user: {} to \"SUDOERS\"'.format(username))
            asd = "grep -qxF '{} ALL=(ALL) NOPASSWD:ALL' /etc/sudoers" \
                  " || echo '{} ALL=(ALL) NOPASSWD:ALL' >> /etc/sudoers".format(
                username, username)
            os.system(asd)
            self.log.info('User: {} is added'.format(username))
        except OSError as e:
            self.log.error('Error: {}'.format(e))
            pass

    def user_add(self, username: str):
        self.log.info('Create user {}'.format(username))
        try:
            subprocess.Popen(
                ["useradd", "-m", "-d", "/home/{}".format(username), "{}".format(username), "-s", "/bin/bash"],
                stdout=subprocess.PIPE)
            self.log.info('User {} is created'.format(username))
        except subprocess.CalledProcessError as e:
            self.log.error('Error: {}'.format(e))
            pass

    @staticmethod
    def local_users():
        try:
            get_user_list = subprocess.Popen(
                ["cut", "-d:", "-f1", "/etc/passwd"],
                stdout=subprocess.PIPE)
            output = get_user_list.communicate()[0].decode('utf-8')
            user_list = []
            for item in output.splitlines():
                if '#' in item:
                    continue
                elif '_' in item:
                    continue
                else:
                    user_list.append(item)
            return user_list
        except Exception as e:
            print(e)

    def run(self):
        start_time = time.time()
        try:
            while True:
                self.separate_users()
                time.sleep(2700 - ((time.time() - start_time) % 2700))
        except RuntimeError:
            self.log.error('Runtime Error')
        except KeyboardInterrupt:
            self.log.error('Keyboard Interruption Error')


if __name__ == "__main__":
    SessionManager().run()
