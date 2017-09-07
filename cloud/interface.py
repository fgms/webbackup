from pcloud import PyCloud

class CloudInterface(object):
    def __init__(self,user,password):
        self.pc = PyCloud(user,password)

    def getFiles(self,folder=True,folderid=0):
        ls = self.pc.listfolder(folderid=folderid)
        folders = {}
        for item in ls['metadata']['contents']:
            if folder and (item.get('isfolder')):
                folders[item.get('name','')] = item.get('folderid',0)
            elif folder == False and item.get('isfolder') == False:
                folders[item.get('name','')] = item.get('fileid')
        return folders
