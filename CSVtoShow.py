#!/usr/bin/env python3

import csv, collections, json, os, click
import xml.etree.ElementTree as ElementTree
import QLCScriptFunctions as qlcsf

@click.command()
@click.option('--qlcfile', help='Location of the QLC .qxw file', required=True)
@click.option('--cuefile', help='Location of the cue .csv file', required=True)
@click.option('--audiopathprefix', help='Audio path prefix (QLC path is releative to the .qxw file)', required=True)
def main(qlcfile, cuefile, audiopathprefix):
    global QLCFUNCTIONS, CUES

    with open(qlcfile) as f:
         qlcsf.init(f.read())
         
    QLCFUNCTIONS = qlcsf.extractFunctions() 
    FADEDURATION = {'SLOW' : 3000, 'MEDIUM' : 1750, 'QUICK' : 500, 'NONE' : 0}

    TIMECODECHASES = {}
    TRACKS = collections.OrderedDict()
    FUNCTIONS = collections.OrderedDict()

    showname = os.path.splitext(os.path.basename(cuefile))[0]
    AUDIOID = QLCFUNCTIONS['Audio'][showname]['id']
    
    try:
        with open(cuefile) as csv_file:  
            csv_reader = csv.reader(csv_file, delimiter=',')
            line_count = 0
            for row in csv_reader:
                if line_count != 0:
                    timecode = row[0].strip()
                    fadeIn = row[1].strip()
                    
                    if fadeIn not in ("SLOW","MEDIUM","QUICK","NONE"):
                        raise Exception("Fade '"+fadeIn+"' not supported. Supported fades 'SLOW,MEDIUM,QUICK,NONE'")
                        
                    fadeOut = row[2].strip()

                    if fadeOut not in ("SLOW","MEDIUM","QUICK","NONE"):
                        raise Exception("Fade '"+fadeOut+"' not supported. Supported fades 'SLOW,MEDIUM,QUICK,NONE'")
                        
                    functionType = row[3].strip()  
                    functionName = row[4].strip()
                    duration = row[5].strip()
                    
                    # We need to create new chases and functions for everything here
                    newFunctionId = qlcsf.generateFunctionId()
                    
                    # Means we can name the chase tracks sequentially
                    if functionType in ("Chaser","CHASER","chaser"):
                        functionType = "Chaser"
                        if timecode not in TIMECODECHASES:
                            TIMECODECHASES[timecode] = 1
                            trackcount = 1
                        else: 
                            TIMECODECHASES[timecode] += 1
                            trackcount = TIMECODECHASES[timecode]
                        track = "Chase " +  str(trackcount)
                        
                        # I.E Loop, SingleShot, PingPong etc
                        originalFunctionId = QLCFUNCTIONS[functionType][functionName]['id']
                        runOrder = QLCFUNCTIONS[functionType][functionName]['runorder']
                        
                        if runOrder == "Loop":
                            if not duration:
                                raise Exception("Function '"+functionName+"' at "+timecode+" is missing a duration - 'Loop Chaser' requires a duration")
                            else:
                                duration = qlcsf.timecodeToMS(duration)
                        elif runOrder == "SingleShot":
                             if duration:
                                raise Exception("Function '"+functionName+"' at "+timecode+" has a duration - 'Single Shot Chaser' fires only once for a pre-determined duration")
                             else:
                                duration = QLCFUNCTIONS[functionType][functionName]['duration']
                        elif runOrder == "PingPong":
                             raise Exception("Function '"+functionName+"' at "+timecode+" has a 'Ping Pong' run order. This is not supported. Create a 'Loop' chaser containing this chaser and specify a duration.")
                        else:
                             raise Exception("Function '"+functionName+"' at "+timecode+" using an unsupported RunOrder")         
                    elif functionType in ("Scene","SCENE","scene"):
                        functionType = "Scene"
                        track = functionName
                        
                        originalFunctionId = QLCFUNCTIONS[functionType][functionName]['id']

                        if not duration:
                            raise Exception("Function '"+functionName+"' at "+timecode+" is missing a duration - Scenes require a duration")
                        else:
                            duration = qlcsf.timecodeToMS(duration)
                    else:
                        raise Exception("Function '"+functionType+"' not valid")

                    # FUNCTIONS
                    if functionType not in FUNCTIONS:
                        FUNCTIONS[functionType] = {}
                        
                    if functionName not in FUNCTIONS[functionType]:
                        FUNCTIONS[functionType][functionName] = []
                        
                    data = {}
                    data['newid'] = newFunctionId
                    data['originalid'] = originalFunctionId
                    data['duration'] = duration
                    FUNCTIONS[functionType][functionName].append(data)
                    # END FUNCTIONS
                    
                    # TRACKS
                    if functionType not in TRACKS:
                        TRACKS[functionType] = {}
                                
                    if track not in TRACKS[functionType]:
                        TRACKS[functionType][track] = []
                    
                    data = {}
                    data['timecode'] = qlcsf.timecodeToMS(timecode)      

                    if duration:
                        data['duration'] = duration
                    data['functionid'] = newFunctionId
                    TRACKS[functionType][track].append(data)
                    # END TRACKS
                    
                line_count += 1            
    except IOError:
        print("ERROR: Unable to open CSV file - Expecting CSV in '%s'" % CSVPATH)
        
    XML_Root = ElementTree.Element("Root")
    XML_Root.insert(1, ElementTree.Comment(' START OF AUTO GENERATED XML FROM QLCPYTHONSCRIPTS (DO NOT COPY ROOT ELEMENT ABOVE) '))
    
    XML_Function = ElementTree.SubElement(XML_Root, "Function")
    XML_Function.set("ID",str(qlcsf.generateFunctionId()))
    XML_Function.set("Type", "Show")
    XML_Function.set("Name", showname)

    XML_TimeDivision = ElementTree.SubElement(XML_Function, "TimeDivision")
    XML_TimeDivision.set("Type", "Time")
    XML_TimeDivision.set("BPM", "120")
  
    AudioTrack = qlcsf.createTrack(parent=XML_Function, id=0, name="Audio")
    AudioTrackFunction = qlcsf.createTrackFunction(parent=AudioTrack, id=AUDIOID, starttime=0, duration=qlcsf.extractDurationFromAudioID(audiopathprefix, AUDIOID), color="#608053")

    TRACKCOUNT = 1
    # Make the Chaser tracks
    for chasertrack in TRACKS['Chaser']:
        ChaserTrack = qlcsf.createTrack(parent=XML_Function, id=TRACKCOUNT, name=chasertrack)
        for chaser in TRACKS['Chaser'][chasertrack]:
            ChaserTrackFunction = qlcsf.createTrackFunction(parent=ChaserTrack, id=chaser['functionid'], starttime=chaser['timecode'], duration=chaser['duration'])
        TRACKCOUNT += 1
        
    # Make the Scene tracks
    for scenetrack in TRACKS['Scene']:
        SceneTrack = qlcsf.createTrack(parent=XML_Function, id=TRACKCOUNT, name=scenetrack, sceneid=QLCFUNCTIONS['Scene'][scenetrack]['id'])
        for scene in TRACKS['Scene'][scenetrack]:
            SceneTrackFunction = qlcsf.createTrackFunction(parent=SceneTrack, id=scene['functionid'], starttime=scene['timecode'], duration=scene['duration'])
        TRACKCOUNT += 1

    # Make the Chaser functions
    for chaserfunction in FUNCTIONS['Chaser']:
        CHASERFUNCTIONCOUNT = 1
        for newfunction in FUNCTIONS['Chaser'][chaserfunction]:          
            speed = {"fadein" : 0, "fadeout" : 0, "duration" : newfunction['duration']}
            speedmodes = {"fadein" : "Default", "fadeout" : "Default", "duration" : "Common"}
            steps = [{"number" : 0, "fadein" : 0, "hold" : 0, "fadeout" : 0, "functionid" : newfunction['originalid']}]
            ChaserFunction = qlcsf.createFunction(parent=XML_Root, id=newfunction['newid'], type="Chaser", name=chaserfunction + " " + str(CHASERFUNCTIONCOUNT), path=showname, speed=speed, direction="Forward", runorder="Loop", speedmodes=speedmodes, steps=steps)    
            CHASERFUNCTIONCOUNT += 1

    # Make the Scene functions
    for scenefunction in FUNCTIONS['Scene']:
        SCENEFUNCTIONCOUNT = 1
        for newfunction in FUNCTIONS['Scene'][scenefunction]:
            speed = {"fadein" : 0, "fadeout" : 0, "duration" : 0}
            speedmodes = {"fadein" : "Default", "fadeout" : "Default", "duration" : "PerStep"}
            steps = [{"number" : 0, "fadein" : 0, "hold" : newfunction['duration'], "fadeout" : 0, "values" : 0, "functionid" : newfunction['originalid']}]
            SceneFunction = qlcsf.createFunction(parent=XML_Root, id=newfunction['newid'], type="Sequence", name=scenefunction + " " + str(SCENEFUNCTIONCOUNT), boundscene=newfunction['originalid'], path=showname, speed=speed, direction="Forward", runorder="SingleShot", speedmodes=speedmodes, steps=steps)   
            SCENEFUNCTIONCOUNT += 1

    XML_Root.insert(9999999, ElementTree.Comment(' END OF AUTO GENERATED XML FROM QLCPYTHONSCRIPTS (DO NOT COPY ROOT ELEMENT BELOW) '))
        
    xmlstring = ElementTree.tostring(XML_Root, 'utf-8')
    qlcsf.outputData(xmlstring, pretty=True, standard=False)

if __name__ == "__main__":
    main()
