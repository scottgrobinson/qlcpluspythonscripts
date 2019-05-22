#!/usr/bin/env python3

import csv, collections, json, os, click, sys
import xml.etree.ElementTree as ElementTree
import QLCScriptFunctions as qlcsf

@click.command()
@click.option('--qlcfile', help='Location of the QLC .qxw file', required=True)
@click.option('--cuefile', help='Location of the cue .csv file', required=True)
@click.option('--audiopathprefix', help='Audio path prefix (QLC path is releative to the .qxw file)', required=True)
@click.option('--auditioncuefileformat', help='Processes the incoming .csv file as if its come from Adobe Audition', is_flag=True)
def main(qlcfile, cuefile, audiopathprefix, auditioncuefileformat):
    global QLCFUNCTIONS

    def processAuditionRow(description, start, duration, csv_rownum):
        def reformatTimecode(timecode):
            m = int(timecode.split(":")[0])
            s = int(timecode.split(":")[1].split(".")[0])
            ms = int(timecode.split(":")[1].split(".")[1])

            return "0"+str(m)+":"+format(str(s).zfill(2))+"."+'{:<03d}'.format(ms)

        data = {}
        # Hooky function to rebuild the duration
        data['timecode'] = reformatTimecode(start)

        data['functionname'] = description
        
        data['fadein'] = 'NONE'
        for fadetype in FADES:
            if '{'+fadetype+'}' in description:
                data['fadein'] = fadetype
                data['functionname'] = description.replace(' {'+fadetype+'}', '')

        data['fadeout'] = 'NONE'
        for fadetype in FADES:
            if '['+fadetype+']' in description:
                data['fadeout'] = fadetype
                data['functionname'] = data['functionname'].replace(' ['+fadetype+']', '')

        functionFound = False
        for functionType in QLCFUNCTIONS:
            for functionName in QLCFUNCTIONS[functionType]:
                if data['functionname'] == functionName:
                    if functionFound:
                        errors.append("[Line: "+str(csv_rownum)+"] Function '"+functionName+"' is defined in multiple function types. This is not supported")         
                        return    
                    data['functiontype'] = functionType.upper()
                    functionFound = True
                    break

        if functionFound == False:
            errors.append("[Line: "+str(csv_rownum)+"] Function '"+data['functionname']+"' not found in any function types")         
            return 

        # Hooky function to rebuild the duration
        data['duration'] = reformatTimecode(duration)
        return data

    def processRowData(data):
         # We need to create new chases and functions for everything here
        newFunctionId = qlcsf.generateFunctionId()

        # Means we can name the chase tracks sequentially
        if data['functiontype'] in ("Chaser","CHASER","chaser"):
            data['functiontype'] = "Chaser"
            if data['timecode'] not in TIMECODECHASES:
                TIMECODECHASES[data['timecode']] = 1
                trackcount = 1
            else: 
                TIMECODECHASES[data['timecode']] += 1
                trackcount = TIMECODECHASES[data['timecode']]
            track = "Chase " +  str(trackcount)
            
            # I.E Loop, SingleShot, PingPong etc
            if data['functionname'] not in QLCFUNCTIONS[data['functiontype']]:
                errors.append("[Line: "+str(csv_rownum)+"] Function '"+data['functionname']+"' not found in Chasers. Validate that the functionType is set correctly")         
            originalFunctionId = QLCFUNCTIONS[data['functiontype']][data['functionname']]['id']
            
            runOrder = QLCFUNCTIONS[data['functiontype']][data['functionname']]['runorder']
            
            if runOrder == "Loop":
                if not data['duration']:
                    errors.append("[Line: "+str(csv_rownum)+"] Function '"+data['functionname']+"' is missing a duration - 'Loop Chaser' requires a duration")
                    return
                else:
                    duration = qlcsf.timecodeToMS(data['duration'])
            elif runOrder == "SingleShot":
                    if data['duration']:
                        errors.append("[Line: "+str(csv_rownum)+"] Function '"+data['functionname']+"' has a duration - 'Single Shot Chaser' fires only once for a pre-determined duration")
                        return
                    else:
                        duration = QLCFUNCTIONS[data['functiontype']][data['functionname']]['duration']
            elif runOrder == "PingPong":
                errors.append("[Line: "+str(csv_rownum)+"] Function '"+data['functionname']+"' has a 'Ping Pong' run order. This is not supported. Create a 'Loop' chaser containing this chaser and specify a duration")
                return
            else:
                errors.append("[Line: "+str(csv_rownum)+"] Function '"+data['functionname']+"' using an unsupported RunOrder")
                return         
        elif data['functiontype'] in ("Scene","SCENE","scene"):
            data['functiontype'] = "Scene"
            track = data['functionname']
            
            if data['functionname'] not in QLCFUNCTIONS[data['functiontype']]:
                errors.append("[Line: "+str(csv_rownum)+"] Function '"+data['functionname']+"' not found in Scenes. Validate that the functionType is set correctly")
                return        
            originalFunctionId = QLCFUNCTIONS[data['functiontype']][data['functionname']]['id']

            if not data['duration']:
                errors.append("[Line: "+str(csv_rownum)+"] Function '"+data['functionname']+"' is missing a duration - Scenes require a duration")
                return
            else:
                duration = qlcsf.timecodeToMS(data['duration'])
        else:
            errors.append("[Line: "+str(csv_rownum)+"] Function '"+data['functiontype']+"' not valid")
            return

        # FUNCTIONS
        if data['functiontype'] not in FUNCTIONS:
            FUNCTIONS[data['functiontype']] = {}
            
        if data['functionname'] not in FUNCTIONS[data['functiontype']]:
            FUNCTIONS[data['functiontype']][data['functionname']] = []
            
        functiondata = {}
        functiondata['newid'] = newFunctionId
        functiondata['originalid'] = originalFunctionId
        functiondata['duration'] = duration
        functiondata['fadein'] = FADES[data['fadein']]
        functiondata['fadeout'] = FADES[data['fadeout']]
        FUNCTIONS[data['functiontype']][data['functionname']].append(functiondata)
        # END FUNCTIONS
        
        # TRACKS
        if data['functiontype'] not in TRACKS:
            TRACKS[data['functiontype']] = {}
                    
        if track not in TRACKS[data['functiontype']]:
            TRACKS[data['functiontype']][track] = []
        
        functiondata = {}
        functiondata['timecode'] = qlcsf.timecodeToMS(data['timecode'])      

        if duration:
            functiondata['duration'] = duration

        functiondata['functionid'] = newFunctionId
        TRACKS[data['functiontype']][track].append(functiondata)
        # END TRACKS

    if not os.path.isfile(qlcfile):
        raise Exception("Unable to open QLC file '"+qlcfile+"'")
    
    with open(qlcfile) as f:
        qlcsf.init(f.read())
         
    QLCFUNCTIONS = qlcsf.extractFunctions() 
    FADES = {'LONG' : 2500, 'SLOW' : 1250, 'MEDIUM' : 850, 'QUICK' : 440, 'RAPID' : 250, 'NONE' : 0}

    TIMECODECHASES = {}
    TRACKS = collections.OrderedDict()
    FUNCTIONS = collections.OrderedDict()

    showname = os.path.splitext(os.path.basename(cuefile))[0]
    if 'Audio' in QLCFUNCTIONS:
        if showname in QLCFUNCTIONS['Audio']:
            AUDIOID = QLCFUNCTIONS['Audio'][showname]['id']
        else:
            raise Exception("Audio track '"+showname+"' not found - An audio track named '"+showname+"' must be defined") 
    else:
        raise Exception("No audio tracks defined in QLC file - An audio track named '"+showname+"' must be defined") 
    
    SCRIPTPATH = os.path.dirname(os.path.realpath(__file__))
    CSVPATH = os.path.join(SCRIPTPATH, cuefile)

    if not os.path.isfile(CSVPATH):
        raise Exception("Unable to open cue file '"+CSVPATH+"'")

    with open(CSVPATH) as csv_file:
        if auditioncuefileformat:  
            csv_reader = csv.reader(csv_file, delimiter='\t')
        else:
            csv_reader = csv.reader(csv_file, delimiter=',')
        line_count = 0
        csv_rownum = 1
        errors = []
        for row in csv_reader:
            if line_count != 0:
                csv_rownum += 1

                if auditioncuefileformat:  
                    description = row[0].strip()
                    start = row[1].strip()
                    duration = row[2].strip()

                    if len(description.split(" + ")) > 1:
                        for item in description.split(" + "):
                            processRowData(processAuditionRow(item, start, duration, csv_rownum))
                    else:
                        processRowData(processAuditionRow(item, start, duration, csv_rownum))
                else:
                    forProcessing = {}
                    forProcessing['timecode'] = row[0].strip() 

                    forProcessing['fadein'] = row[1].strip()
                    if forProcessing['fadein'] not in FADES:
                        errors.append("[Line: "+str(csv_rownum)+"] Fade '"+fadeIn+"' not supported. Supported fades: "+', '.join(FADES.keys()))
                        continue

                    forProcessing['fadeout'] = row[2].strip()
                    if forProcessing['fadeout'] not in FADES:
                        errors.append("[Line: "+str(csv_rownum)+"] Fade '"+fadeOut+"' not supported. Supported fades: "+', '.join(FADES.keys()))
                        continue

                    forProcessing['functiontype'] = row[3].strip()  
                    forProcessing['functionname'] = row[4].strip()
                    forProcessing['duration'] = row[5].strip()

                    processRowData(forProcessing)
                
            line_count += 1            

    if errors:
        for error in errors:
            print(error)
        sys.exit(1)

    print(TRACKS)
    print(FUNCTIONS)

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
    qlcsf.createTrackFunction(parent=AudioTrack, id=AUDIOID, starttime=0, duration=qlcsf.extractDurationFromAudioID(audiopathprefix, AUDIOID), color="#608053")

    TRACKCOUNT = 1
    # Make the Chaser tracks
    for chasertrack in TRACKS['Chaser']:
        ChaserTrack = qlcsf.createTrack(parent=XML_Function, id=TRACKCOUNT, name=chasertrack)
        for chaser in TRACKS['Chaser'][chasertrack]:
            qlcsf.createTrackFunction(parent=ChaserTrack, id=chaser['functionid'], starttime=chaser['timecode'], duration=chaser['duration'])
        TRACKCOUNT += 1
        
    # Make the Scene tracks
    for scenetrack in TRACKS['Scene']:
        SceneTrack = qlcsf.createTrack(parent=XML_Function, id=TRACKCOUNT, name=scenetrack, sceneid=QLCFUNCTIONS['Scene'][scenetrack]['id'])
        for scene in TRACKS['Scene'][scenetrack]:
            qlcsf.createTrackFunction(parent=SceneTrack, id=scene['functionid'], starttime=scene['timecode'], duration=scene['duration'])
        TRACKCOUNT += 1

    # Make the Chaser functions
    for chaserfunction in FUNCTIONS['Chaser']:
        CHASERFUNCTIONCOUNT = 1
        for newfunction in FUNCTIONS['Chaser'][chaserfunction]:          
            speed = {"fadein" : 0, "fadeout" : 0, "duration" : newfunction['duration']}
            speedmodes = {"fadein" : "PerStep", "fadeout" : "PerStep", "duration" : "Common"}
            steps = [{"number" : 0, "fadein" : newfunction['fadein'], "hold" : 0, "fadeout" : newfunction['fadeout'], "functionid" : newfunction['originalid']}]
            qlcsf.createFunction(parent=XML_Root, id=newfunction['newid'], type="Chaser", name=chaserfunction + " " + str(CHASERFUNCTIONCOUNT), path=showname, speed=speed, direction="Forward", runorder="Loop", speedmodes=speedmodes, steps=steps)    
            CHASERFUNCTIONCOUNT += 1

    # Make the Scene functions
    for scenefunction in FUNCTIONS['Scene']:
        SCENEFUNCTIONCOUNT = 1
        for newfunction in FUNCTIONS['Scene'][scenefunction]:
            speed = {"fadein" : 0, "fadeout" : 0, "duration" : newfunction['duration']}
            speedmodes = {"fadein" : "PerStep", "fadeout" : "PerStep", "duration" : "Common"}
            steps = [{"number" : 0, "fadein" : newfunction['fadein'], "hold" : 0, "fadeout" : newfunction['fadeout'], "functionid" : newfunction['originalid']}]
            qlcsf.createFunction(parent=XML_Root, id=newfunction['newid'], type="Sequence", name=scenefunction + " " + str(SCENEFUNCTIONCOUNT), boundscene=newfunction['originalid'], path=showname, speed=speed, direction="Forward", runorder="SingleShot", speedmodes=speedmodes, steps=steps)   
            SCENEFUNCTIONCOUNT += 1

    XML_Root.insert(9999999, ElementTree.Comment(' END OF AUTO GENERATED XML FROM QLCPYTHONSCRIPTS (DO NOT COPY ROOT ELEMENT BELOW) '))
        
    xmlstring = ElementTree.tostring(XML_Root, 'utf-8')
    qlcsf.outputData(xmlstring, pretty=True, standard=False)

if __name__ == "__main__":
    main() # pylint: disable=no-value-for-parameter