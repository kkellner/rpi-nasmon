import os

# S.M.A.R.T. (Self-Monitoring, Analysis and Reporting Technology) for hard drives

class SMART:
    #to run a smartctl command
    def RunSmartCtl(self, strArgs):
        #get the command with strArgs as the argument
        cmdString = "smartctl " + strArgs
        #get command output and store each line in a list
        output = os.popen(cmdString).read()
        lines = str.splitlines(output)
        
        return lines

    #get device health
    def GetDeviceHealth(self, deviceId):
        deviceInfoLines = self.RunSmartCtl("-H " + deviceId)
        return deviceInfoLines[-2]
    

    #get device attributes
    def GetDeviceAttributes(self, deviceId):
        deviceInfoLines = self.RunSmartCtl("-A " + deviceId)
        
        for i in range(len(deviceInfoLines)):
            if deviceInfoLines[i].startswith('ID#'):
                index = i+1
                break
        
        infoDict = dict()
        for i in range(index, len(deviceInfoLines)-1):
            x = deviceInfoLines[i].strip().split()
            infoDict[x[0]] = x[0:len(x)]
        
        return infoDict

if __name__ == '__main__':
    smart_features = SMART()
    deviceid = input("Enter device id: ")
    #fetchig disk health
    devHealth = smart_features.GetDeviceHealth(deviceid)
    #printing device health information
    print("Disk Health Information")
    print(devHealth)

    #fetching attributes details
    devAttr=smart_features.GetDeviceAttributes(deviceid)
    #printing attributes information
    print("Disk attribute Informaion")
    print("ID#      ATTRIBUTE_NAME         FLAG   VALUE  WORST  THRESH")
    for attributes in devAttr:
        print('\t'.join(devAttr[attributes][:6]))

    print (devAttr)
    #print("Drive temperature: "+devAttr['Temperature_Celsius'])