import xml.etree.ElementTree as ElementTree
from itertools import count, filterfalse
from mutagen.mp3 import MP3
import xml.dom.minidom as minidom
import re, os

QLCXML = None
INUSEFUNCTIONIDS = None

def init(qlcxml):
    global QLCXML, INUSEFUNCTIONIDS

    QLCXML = ElementTree.fromstring(re.sub(r'\sxmlns="[^"]+"', '', qlcxml, count=1))
    INUSEFUNCTIONIDS = findInUseFunctionIds()

def extractFromQLC(query, allowMultipleResults = False):
    global QLCXML 
    
    result = False
    for target in QLCXML.findall(query):
        if not result:
            if allowMultipleResults:
                result = []
                result.append(target)
            else: 
                result = target
        else:
            if allowMultipleResults:
                result.append(target)
            else:
                raise Exception("Multiple results with query '"+query+"' exist")
                
    return result

def extractDurationFromAudioID(audioPathPrefix, audioId):
    audioFunction = extractFromQLC(".//Function[@ID='"+str(audioId)+"']/Source")
    
    if audioFunction is not None:
        # This doesn't appear to be the same duration as QLC, but hopefully it's close enough. We'll see!
        # TODO: Error catching if we can't get the duration
        path = os.path.join(audioPathPrefix, audioFunction.text)
        duration = str(MP3(path).info.length).split(".")
        duration = duration[0] + duration[1][:3]
    else:
        raise Exception("Audio function missing source, That doesn't sound right?")
        
    return ""+str(duration)+""
    
def extractDurationFromShowID(audioId):
    showFunction = extractFromQLC(".//Function[@ID='"+str(audioId)+"']/Track[@Name='Audio']/ShowFunction")

    if showFunction is not None:
        if 'Duration' in showFunction.attrib:
            return int(showFunction.attrib['Duration'])
        else:
            raise Exception("ShowFunction missing duration, That doesn't sound right?")
    else:
        raise Exception("Function missing ShowFunction, That doesn't sound right?")
                    
def extractFunctions():
    extractedfunctions = extractFromQLC(".//Engine/Function", True)

    functions = {}

    if extractedfunctions:
        for function in extractedfunctions:
            if function.attrib['Type'] not in functions:
                functions[function.attrib['Type']] = {}
                
            if all(x in function.attrib for x in ['ID', 'Name', 'Type']):
                functions[function.attrib['Type']][function.attrib["Name"]] = {}
                functions[function.attrib['Type']][function.attrib["Name"]]['id'] = int(function.attrib["ID"])

                speedelement = function.find(".//Speed")
                if speedelement is not None:
                    if speedelement.attrib['Duration']:
                        functions[function.attrib['Type']][function.attrib["Name"]]['duration'] = speedelement.attrib['Duration']
         
                runorderelement = function.find(".//RunOrder")
                if runorderelement is not None:
                    functions[function.attrib['Type']][function.attrib["Name"]]['runorder'] = runorderelement.text                       
            else:
                functionasstring = ElementTree.tostring(function, encoding='utf8').decode('utf-8')
                raise Exception("'"+functionasstring+"' missing 'ID', 'Name' or 'Type' attributes, That doesn't sound right?")
        return functions
    else:
        raise Exception("No functions found in QLC")

def findInUseFunctionIds():
    functions = extractFromQLC(".//Engine/Function", True)
    
    ids = []
    
    if functions:
        for function in functions:
            if 'ID' in function.attrib:
                ids.append(int(function.attrib['ID']))
            else:
                functionasstring = ElementTree.tostring(function, encoding='utf8').decode('utf-8')
                raise Exception("'"+functionasstring+"' missing 'ID' attribute, That doesn't sound right?")
    else:
        raise Exception("No functions found in QLC")
    
    return ids
    
def generateFunctionId():
    global INUSEFUNCTIONIDS
    
    nextAvaliableId = next(filterfalse(set(INUSEFUNCTIONIDS).__contains__, count(1)))
    INUSEFUNCTIONIDS.append(nextAvaliableId)
    
    return nextAvaliableId
    
# I'm sure this is wrong... But it seems to work for what we're doing here!
def timecodeToMS(timecode):
    pattern = re.compile("\d\d:\d\d.\d\d\d$")
    if pattern.match(timecode):
        tssplit = timecode.split(":")
        smssplit = tssplit[1].split(".")
        minutes = int(tssplit[0]) * 60000
        seconds = int(smssplit[0]) * 1000
        ms = int(smssplit[1])
    else:
        raise Exception("Timecode '"+timecode+"' does not match required pattern - 00:00.000")
    
    return minutes + seconds + ms
    
def createTrack(parent,id,name,sceneid=False):
    Track = ElementTree.SubElement(parent, "Track")
    Track.set("ID", str(id))
    Track.set("Name", name)
    if sceneid:
        Track.set("SceneID", str(sceneid))
    Track.set("isMute", "0")

    return Track
    
def createTrackFunction(parent,id,starttime,duration,color="#556b80"):
    TrackFunction = ElementTree.SubElement(parent, "ShowFunction")
    TrackFunction.set("ID", str(id))
    TrackFunction.set("StartTime", str(starttime))
    TrackFunction.set("Duration", str(duration))
    TrackFunction.set("Color", color)

    return TrackFunction
    
def createFunction(parent,id,type,name,speed,direction,runorder,speedmodes,path=False,steps=False,boundscene=False):
    Function = ElementTree.SubElement(parent, "Function")
    Function.set("ID", str(id))
    Function.set("Type", type)
    Function.set("Name", name)
    if boundscene is not False:
        Function.set("BoundScene", str(boundscene))
    if path:
        Function.set("Path", path)
   
    FunctionSpeed = ElementTree.SubElement(Function, "Speed")
    FunctionSpeed.set("FadeIn", str(speed['fadein']))
    FunctionSpeed.set("FadeOut", str(speed['fadeout']))
    FunctionSpeed.set("Duration", str(speed['duration']))

    FunctionDirection = ElementTree.SubElement(Function, "Direction")
    FunctionDirection.text = direction

    FunctionRunOrder = ElementTree.SubElement(Function, "RunOrder")
    FunctionRunOrder.text = runorder

    FunctionSpeedModes = ElementTree.SubElement(Function, "SpeedModes")
    FunctionSpeedModes.set("FadeIn", str(speedmodes['fadein']))
    FunctionSpeedModes.set("FadeOut", str(speedmodes['fadeout']))
    FunctionSpeedModes.set("Duration", str(speedmodes['duration']))

    if steps:
        for step in steps:
            FunctionStep = ElementTree.SubElement(Function, "Step")
            FunctionStep.set("Number", str(step['number']))
            FunctionStep.set("FadeIn", str(step['fadein']))
            FunctionStep.set("Hold", str(step['hold']))
            if 'values' in step:
                FunctionStep.set("Values", str(step['values']))
            if 'note' in step:
                FunctionStep.set("Note", str(step['note']))
            FunctionStep.set("FadeOut", str(step['fadeout']))
            FunctionStep.text = str(step['functionid']) 
    
    return Function
    
def outputData(xmlstring,pretty=False,standard=True):
    parsed = minidom.parseString(xmlstring)

    if pretty:
        print()
        print("QLC XML (Pretty)")
        print(parsed.toprettyxml(indent="\t"))
    
    if standard:
        print()
        print("QLC XML (Standard)")
        print(parsed.toxml())
