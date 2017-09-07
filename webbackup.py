import os
import sys
import getopt
import configparser
import smtplib
import yaml

from cloud.interface import CloudInterface

def main():
    wb = WebBackup(sys.argv[1:])
    #wb.printOptions()


class WebBackup(object):
    def __init__(self,options):
        self.config={}
        self.sections={}
        self.website_config={}
        try:
            self.opts, args = getopt.getopt(options,"h:", ["config=","yaml=","dry-run"])
        except getopt.GetoptError:
            self.opts=[]
        self.loadConfig()
        self.website_config = self.loadYaml(self.getDictValue('--yaml',self.opts))
        for site in self.website_config:
            print(site['name'])
            print(site['ssh'])

    def loadYaml(self, yaml_file):
        if yaml_file and os.path.isfile(yaml_file):
            stream=open(yaml_file,'r')
            return yaml.load(stream)

    def loadConfig(self):
        config_file=self.getDictValue('--config', self.opts);
        if config_file and os.path.isfile(config_file):
            try:
                self.config=configparser.ConfigParser()
                self.config.read(config_file)
                for section in self.config.sections():
                    self.sections[section]=self.config.items(section)
            except:
                print('Couldnt read config file')
        else:
            print('Couldnt find %s configuration files'%(config_file))


    def getDictValue(self,key,dic):
        for opt, arg in dic:
            if (key == opt):
                return arg;
        return False

    def printDict(self,dic):
        for opt, arg in dic:
            print("%s:%s"%(opt,arg))

    def send_mail(data, msg):
        d = date.today()
        smtpserver = smtplib.SMTP(data['server'],587)
        smtpserver.ehlo()
        smtpserver.starttls()
        smtpserver.ehlo
        smtpserver.login(data['user'],data['password'])
        header = 'To:' + data['to'] + '\n' + 'From: ' + data['user'] + '\n' + 'Subject:FGMS Backup Results For: '+d.isoformat()+'\n'
        if data['cc']:
            header += 'Cc:'+data['cc']+'\n'

        smtpserver.sendmail(data['user'], data['to'],"%s \n\r %s %s" %(header, msg,log_capture_string.getvalue()))
        smtpserver.close()


if __name__ == '__main__':
    main()
