import os
import sys
import getopt
import configparser
import smtplib
import subprocess
import yaml
import urllib.request
import time
from datetime import date
import logging
from io import StringIO as StringBuffer
import paramiko
from cloud.interface import CloudInterface

def main():
    wb = WebBackup(sys.argv[1:])
    wb.backupSites()

class WebBackup(object):
    def __init__(self,options):
        self.config={}
        self.sections={}
        self.website_config={}
        self.cloud={}
        self.logger={}
        self.log_capture_string = StringBuffer()

        version = subprocess.check_output(['git','rev-parse','--short','HEAD']).decode().strip('\n')
        try:
            self.opts, args = getopt.getopt(options,"hd:", ["config=","yaml=","site=","dry-run","debug","restore-point"])
        except getopt.GetoptError:
            self.opts=[]

        self.loadConfig()
        # ensure all directories are created
        for key in self.config['paths']:
            path = self.config['paths'][key]

        self.setupLogging()
        self.logger.info(self.opts)
        self.logger.info('Version: %s'%(version))



        # setup pcloud interface
        user = self.getDictValue('user', self.sections['pcloud'])
        passwd = self.getDictValue('pass', self.sections['pcloud'])
        self.cloud = CloudInterface(user,passwd)
        self.loadYamlWeb(self.getDictValue('config_file_id', self.sections['pcloud']))

    def __del__(self):
        msg = self.log_capture_string.getvalue()
        self.send_mail(msg);

    def backupSites(self):
        for site in self.website_config['hosting']:
            if self.getOpts('--site') != False :
                if site['name'] == self.getOpts('--site'):
                    self.backupSite(site)
            else:
                self.backupSite(site)


    def backupSite(self,site):
        self.logger.info('*** Section ' + site['name'])
        site['ssh']['key'] = self.getPath('pem_path')+ site['ssh']['key'];
        if 'port' not in site['ssh']:
            site['ssh']['port'] = 22
        if 'options' not in site['ssh']:
            site['ssh']['options'] = ''
        if os.path.isfile(site['ssh']['key']):
            self.ssh_cmd(site['ssh'],self.do_database_command(site['databases']))
            os.system('rm -r %s'%(self.getPath('tmp_path')+'*'));
            for cmd in self.do_rsync_command(site):
                os.system(cmd)
                self.logger.debug(cmd)

            for cmd in self.do_archive_command(site):
                os.system(cmd)
                self.logger.debug(cmd)

            self.do_send_pcloud(self.website_config['pcloud']['backup']['folderid'], site['name'])
        else:
            self.logger.error('Could not find key file %s '%(site['ssh']['key']))

    def do_send_pcloud(self,folderid,name):
        current_folders = self.cloud.cloneFolders(self.getPath('tmp_path'),folderid )
        self.logger.debug(current_folders)
        if name in current_folders:
            results = self.cloud.uploadFiles(self.getPath('tmp_path')+name+'/',current_folders[name])
            self.logger.debug(results)

    def do_archive_command(self, site):
        d = date.today()
        cmds = []
        name=site['name'];

        directory=self.getPath('backup_root')+name+'/'
        tmp_dir = self.getPath('tmp_path')+name+'/'
        self.create_dir(tmp_dir)
        archive_dir=self.getPath('archive_root')

        subfolders = os.listdir(directory)
        for folder in subfolders:
            if folder == 'mysql' or d.day == 1 or d.day == 15 or  self.getOpts('--restore-point'):
                self.logger.info('Archiving Folder' + folder)
                filename = name+'-'+folder+'-month-'+ str(d.month)+'-day-'+ str(d.day) +'.tar.gz'
                source = directory+folder;
                tar_file = archive_dir+filename

                cmds.append('cd %s && rm %s-%s-month* '%(archive_dir, name,folder ))
                cmds.append('tar --create --auto-compress --file=%s  %s'%(tar_file, source))
                cmds.append('split --bytes=560MB %s %s'%(tar_file,tmp_dir+filename+'.'))


        return cmds


    def do_database_command(self,databases):
        cmds = [];
        cmds.append("mkdir mysql")
        for db in databases :
            if 'host' not in db:
                db['host'] = 'localhost'
            if db['user'] and db['pass'] and db['name']:
                cmds.append("mysqldump -h %s -u %s -p'%s' %s > %s" % (db['host'],db['user'],db['pass'], db['name'], 'mysql/'+db['name']+'.sql'))
        cmds.append("chmod -R 755 mysql")
        return cmds

    def do_rsync_command(self,site):
        ssh = site['ssh'];
        cmds = []
        site['remotes'].append('mysql')
        for remote in site['remotes'] :
            rsync_remote = ssh['user']+'@'+ssh['host']+':'+remote
            rsync_local = self.getPath('backup_root')+site['name']
            self.create_dir(rsync_local)
            rsync_option = ssh['key']
            if ssh['options'] == 'ssh-dss':
                rsync_option = rsync_option + ' -oHostKeyAlgorithms=+ssh-dss'
            cmds.append("rsync --delete  -arz -e 'ssh -i %s' %s %s " % (rsync_option, rsync_remote,rsync_local))
        return cmds;

    def create_dir(self,path) :
        try:
            if not os.path.isdir(path):
                subprocess.Popen('mkdir -p '+ path, shell=True)
            return path
        except:
            return False

    def do_command(self, interface, command,echo=True):
        stdin, stdout, stderr = interface.exec_command(command)
        if echo :
            for line in stdout:
                self.logger.debug(command+' : '+line.strip('\n'))

    def ssh_cmd(self,ssh_config, cmds) :
        try:
            ssh = paramiko.SSHClient();
            ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            ssh.connect(ssh_config['host'],
                        port=int(ssh_config['port']),
                        username=ssh_config['user'],
                        key_filename=ssh_config['key'],
                        timeout=10
                        )
            for cmd in cmds:
                self.do_command(ssh,cmd)

            ssh.close()
        except paramiko.AuthenticationException:
            self.logger.error('SSH Failed Authentication Error')
            connection = False
        except paramiko.SSHException:
            self.logger.error('SSH Failed SSH Exception')
            connection = False
        except :
            self.logger.error('SSH Error -- Check Whitelist on Server %s'%(sys.exc_info()[0]))
            connection = False

    def getPath(self, name):
        path = './';
        try:
            path = self.getDictValue(name,self.sections['paths'])
        except:
            self.logger.error('Could not find %s key' %(name))
        return path

    def loadConfig(self):
        config_file=self.getOpts('--config');
        if config_file and os.path.isfile(config_file):
            try:
                self.config=configparser.ConfigParser()
                self.config.read(config_file)
                for section in self.config.sections():
                    self.sections[section]=self.config.items(section)
            except:
                self.logger.error('Couldnt read config file %s'%(config_file))
        else:
            self.logger.error('Couldnt find %s configuration files'%(config_file))

    def loadYamlFile(self, yaml_file):
        if yaml_file and os.path.isfile(yaml_file):
            stream=open(yaml_file,'r')
            self.website_config = yaml.load(stream)

    def loadYamlWeb(self, yaml_web ):
        filelink = self.cloud.pc.getfilelink(fileid=yaml_web)
        try:
            self.website_config = yaml.load(urllib.request.urlopen('https://'+filelink['hosts'][0]+filelink['path'] ).read())
        except:
            self.logger.error('Error with fileId')
            self.logger.error(filelink)
        return self

    def setupLogging(self):
        self.logger = logging.getLogger('basic_logger')
        FORMAT = '%(asctime)s - %(levelname)s - %(message)s'
        if self.getOpts('--debug') :
            logging.basicConfig(level=logging.DEBUG,format=FORMAT)
        else:
            logging.basicConfig(level=logging.INFO,format=FORMAT)

        paramiko.util.log_to_file(self.getPath('log_path')+'ssh.log')
        logging.getLogger("paramiko").setLevel(logging.WARNING)

        # log_capture_string.encoding = 'cp1251'
        ch = logging.StreamHandler(self.log_capture_string)

        if self.getOpts('--debug') :
            ch.setLevel(logging.DEBUG)
        else:
            ch.setLevel(logging.INFO)

        ### Optionally add a formatter
        formatter = logging.Formatter(FORMAT)
        ch.setFormatter(formatter)

        ### Add the console handler to the logger
        self.logger.addHandler(ch)


    def getDictValue(self,key,dic,default=False):
        for opt, arg in dic:
            if (key == opt):
                if arg == '':
                    return True
                return arg;
        return default

    def getOpts(self,key):
        return self.getDictValue(key,self.opts)

    def printDict(self,dic):
        for opt, arg in dic:
            print("%s:%s"%(opt,arg))

    def cleanup(self):
        # this removes the configuration files and ensure all is cleaned up.
        pass


    def send_mail(self, msg='Test Message'):
        d = date.today()
        data = self.website_config['email']
        smtpserver = smtplib.SMTP(data['server'],587)
        smtpserver.ehlo()
        smtpserver.starttls()
        smtpserver.ehlo
        smtpserver.login(data['user'],data['password'])
        header = 'To:' + data['to'] + '\n' + 'From: ' + data['user'] + '\n' + 'Subject:FGMS Backup Results For: '+d.isoformat()+'\n'
        if data['cc']:
            header += 'Cc:'+data['cc']+'\n'

        smtpserver.sendmail(data['user'], data['to'],"%s \n\r %s" %(header, msg))
        smtpserver.close()


if __name__ == '__main__':
    main()
