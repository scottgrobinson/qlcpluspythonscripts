#!/usr/bin/env python3

import csv, collections, json, os, click
import xml.etree.ElementTree as ElementTree
import QLCScriptFunctions as qlcsf

@click.command()
@click.option('--qlcfile', help='Location of the QLC .qxw file', required=True)
@click.option('--cuefile', help='Location of the cue .csv file', required=True)
def main(qlcfile, cuefile):
    global QLCFUNCTIONS, CUES

    with open(qlcfile) as f:
         qlcsf.init(f.read())
         
    QLCFUNCTIONS = qlcsf.extractFunctions()        
    FADEDURATION = {'SLOW' : 3000, 'MEDIUM' : 1750, 'QUICK' : 500, 'NONE' : 0}

    CUES = collections.OrderedDict()
    COLLECTIONS = []
    try:
        SCRIPTPATH = os.path.dirname(os.path.realpath(__file__))
        CSVPATH = os.path.join(SCRIPTPATH, cuefile)
        with open(CSVPATH) as csv_file:  
            csv_reader = list(csv.reader(csv_file, delimiter=','))
            
            line_count = 0
            for key,row in enumerate(csv_reader):
                if line_count != 0:
                    cueName = row[0].strip()
                    fadeIn = row[1].strip()

                    if fadeIn not in ("SLOW","MEDIUM","QUICK","NONE"):
                        raise Exception("Fade '"+fadeIn+"' not supported. Supported fades 'SLOW,MEDIUM,QUICK,NONE'")

                    if key+1 == len(csv_reader):
                        fadeOut = "SLOW"
                    else:
                        fadeOut = csv_reader[key+1][1].strip()
                    
                    function1Type = row[2].strip()
                    function1Name = row[3].strip()
                    function2Type = row[4].strip()
                    function2Name = row[5].strip()
                    function3Type = row[6].strip()
                    function3Name = row[7].strip()

                    COLLECTIONFUNCTIONS = []
                   
                    def validateAndUpdateFunction(functionType,functionName): 
                        if functionType in ("Chaser","CHASER","chaser"):
                            functionType = "Chaser"
                        elif functionType in ("Scene","SCENE","scene"):
                            functionType = "Scene"
                        elif functionType in ("Show","SHOW","show"):
                            functionType = "Show"
                        else:
                            raise Exception("Function '"+functionType+"' not valid")
                            
                        if functionName not in QLCFUNCTIONS[functionType]:
                            raise Exception(cueName+" '"+functionType+" - "+functionName+"' not found in QLC")
                        
                        return functionType
                         
                    def addToCollection(functionType, functionName):
                        COLLECTIONFUNCTIONS.append(QLCFUNCTIONS[functionType][functionName]['id'])                      
                    
                    def addCue(cueName, fadeIn, functionType, functionId, notes):                        
                        data = {}
                        data['id'] = qlcsf.generateFunctionId()
                        data['type'] = functionType
                        data['fadein'] = FADEDURATION[fadeIn]
                        data['fadeout'] = FADEDURATION[fadeOut]
                        data['functionid'] = functionId
                        data['notes'] = notes
                        CUES[cueName] = data
                                                                
                    if function1Type:
                        function1Type = validateAndUpdateFunction(function1Type, function1Name)
                        addCue(cueName, fadeIn, function1Type, QLCFUNCTIONS[function1Type][function1Name]['id'], function1Name)
                    else:
                        raise Exception("No actions specified for cue '"+cueName+"'")
                    
                    if function2Type:
                        function2Type = validateAndUpdateFunction(function2Type, function2Name)
                        collectionName = function1Name + " / " + function2Name
                        addToCollection(function1Type, function1Name)
                        addToCollection(function2Type, function2Name)
                    if function3Type:
                        function3Type = validateAndUpdateFunction(function3Type, function3Name)
                        collectionName = function1Name + " / " + function2Name + " / " + function3Name
                        addToCollection(function3Type, function3Name)

                    if COLLECTIONFUNCTIONS:
                        collectionId = False      
                        COLLECTIONFUNCTIONS.sort()
                        for i in COLLECTIONS:
                            if COLLECTIONFUNCTIONS == i['functions']:
                                collectionId = i['id']
                                break;
                                
                        if not collectionId:
                            collectionId = qlcsf.generateFunctionId()
                            data = {}
                            data['id'] = collectionId
                            data['name'] = collectionName
                            data['functions'] = COLLECTIONFUNCTIONS                                                    
                         
                            COLLECTIONS.append(data) 
                       
                        addCue(cueName, fadeIn, "Collection", collectionId, collectionName)      

                                   
                line_count += 1            
    except IOError:
        print("ERROR: Unable to open CSV file - Expecting CSV in '%s'" % CSVPATH)

    XML_Root = ElementTree.Element("Root")
    XML_Root.insert(1, ElementTree.Comment(' START OF AUTO GENERATED XML FROM QLCPYTHONSCRIPTS (DO NOT COPY ROOT ELEMENT ABOVE) '))

    # Create any required collections
    for collection in COLLECTIONS:
        Collection = ElementTree.SubElement(XML_Root, "Function")
        Collection.set("ID", ""+str(collection['id'])+"")
        Collection.set("Type", "Collection")
        Collection.set("Name", collection['name'] + " (Auto Generated)")
        STEPCOUNT = 0
        for function in collection['functions']:
            CollectionStep = ElementTree.SubElement(Collection, "Step")
            CollectionStep.set("Number", ""+str(STEPCOUNT)+"")
            CollectionStep.text = str(function)
            STEPCOUNT += 1
        
    speed = {"fadein" : 0, "fadeout" : 0, "duration" : 4294967294}
    speedmodes = {"fadein" : "PerStep", "fadeout" : "PerStep", "duration" : "Common"}
    steps = []
    STEPCOUNT = 0
    for key,cue in enumerate(CUES.keys()):
        step = {}
        step['number'] = STEPCOUNT
        step['hold'] = 0
        step['note'] = cue
        step['fadein'] = CUES[cue]['fadein']
        step['fadeout'] = CUES[cue]['fadeout']
        step['functionid'] = CUES[cue]['functionid']
        steps.append(step)   
        STEPCOUNT += 1        
    ShowChaserFunction = qlcsf.createFunction(parent=XML_Root, id=qlcsf.generateFunctionId(), type="Chaser", name="Master Cue List (Auto Generated)", speed=speed, direction="Forward", runorder="Loop", speedmodes=speedmodes, steps=steps)    

    XML_Root.insert(9999999, ElementTree.Comment(' END OF AUTO GENERATED XML FROM QLCPYTHONSCRIPTS (DO NOT COPY ROOT ELEMENT BELOW) '))

    xmlstring = ElementTree.tostring(XML_Root, 'utf-8')
    qlcsf.outputData(xmlstring, pretty=True, standard=False)

if __name__ == "__main__":
    main()