from pcloud import PyCloud
import os

class CloudInterface(object):
    def __init__(self,user,password):
        self.pc = PyCloud(user,password)

    def uploadFiles(self,localpath,folderid):
        pcfilesuploads = []
        results = []
        for dirpath, dirnames, filenames in os.walk(localpath):
            for n in filenames:
                pcfilesuploads.append(localpath+n)
            for f in pcfilesuploads:
                results.append(self.pc.uploadfile(files=[f],folderid=folderid))
        return results

    def cloneFolders(self,localpath,folderid):
        subfolders = os.listdir(localpath)
        folderlist = self.pc.listfolder(folderid=folderid)
        current_folder = {};
        # find current folders to decide which folders we need.
        for value in folderlist['metadata']['contents']:
            if (value.get('isfolder')):
                current_folder[value.get('name','')] = value.get('folderid',0)


        for folder in subfolders:
            if folder not in current_folder:
                # creates new folder and its it to current folder list
                results = self.pc.createfolder(folderid=folderid,name=folder)
                if results['result'] == 0:
                    current_folder[folder] =  results['metadata']['folderid']
        return current_folder;


    def getFiles(self,folder=True,folderid=0):
        ls = self.pc.listfolder(folderid=folderid)
        folders = {}
        for item in ls['metadata']['contents']:
            if folder and (item.get('isfolder')):
                folders[item.get('name','')] = item.get('folderid',0)
            elif folder == False and item.get('isfolder') == False:
                folders[item.get('name','')] = item.get('fileid')
        return folders

    def getConfig(self,folderid=0):
        # this gets configuration file from pcloud
        pass
