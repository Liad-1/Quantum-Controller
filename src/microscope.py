from pycromanager import Core

class MicroScope:
    
    def __init__(self):
        self.core = Core()
        print(self.core.getVersionInfo())
        
