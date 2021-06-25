#!/usr/bin/env python
"""
ssh example for a long command (backup mysql database), move file to
windows machine
"""
import time
import paramiko
import gzip
KEY_Location = "C:/Users/dale/.ssh/zbox.pem"
ADDRESS = "192.168.0.201"
USER = 'dale'
# COMMANDS = ['lsb_relea se -a', 'cd /media/MAIN-PC/DKF/DEV/MySql', 'ls']
# COMMANDS = ['cd /home/dale/Temp', 'sudo mysqldump -u dale -pdale weather | gzip -9 > weather_bak.sql.gz']
# """sudo mv weather.sql.gz /media/MAIN-PC/DKF/DEV/MySql/backup"""
# """mysqldump -u [uname] -p[pass] [dbname] | gzip -9 > [backupfile.sql.gz]"""
TEMP_PATH = "D:\\Temp"
REMOTE_PATH = "/home/remote/Downloads"
backup_file = "D:\\DKF\\DEV\\MySql\\backup\\weather_bak_data.sql.gz"



def main():
    with gzip.open(backup_file, 'rb') as f:
        for _ in range(30):
            print(f.readline().decode('utf-8')[:400])



if __name__ == "__main__":
    main()
