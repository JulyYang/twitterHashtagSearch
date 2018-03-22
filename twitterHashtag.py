# Twitter hashtags Map
# Yi-Peng Yang(yyang49)
# Purpose: The srcipt enables users to search the hashtag they are interested in.
#           After input a hashtag, the script will use the twitter api key to get
#           the coordinates of the hashtags and produce a choropleth map of the
#           hashtag automatically
# Before running the script, please install the python-twitter library with the instruction:
#           https://python-twitter.readthedocs.io/en/latest/installation.html 
# Sample input: Twitter API has the limitation for users to search only for the
#           past seven days, to get the better performance, trying to use the hot
#           top hashtags. e.g. trndnl, nowplaying, phto, love

import os, sys, twitter, arcpy, traceback, urllib2, zipfile

def fetchZip(url, outputDir):
    '''Doanload zip file from URL and save it to the output directory.
    From fetchZip.py bY Dr. Tateosian'''
    response = urllib2.urlopen(url)
    binContents = response.read()
    response.close()

    outFileName = outputDir + os.path.basename(url)
    with open(outFileName, "wb") as outf:
        outf.write(binContents)

def renameFiles(oldf, newName):
    '''Rename the files to exclude the special characters in the file name.
    '''
    if os.path.exists(oldf):
        newf = os.path.dirname(oldf) + "/" + newName + os.path.splitext(oldf)[1]
        os.rename(oldf, newf)

def unzipArchive(archiveName, dest, newName):
    '''Unzip the zip file to the destination and rename all the files. The file
    downloaded from the website is not acceptable for arcpy mapping module. Call
    the renameFiles function to exclude the special characters. Modified from 
    extractFiles.py by Dr. Tateosian
    '''
    with zipfile.ZipFile(archiveName, "r") as zipObj:
        zipObj.extractall(dest)
        archiveList = zipObj.namelist()
        for fileName in archiveList:
            fPath = dest + fileName
            try:
                renameFiles(fPath, newName)
            except:
                print traceback.print_exc()

def write2File(file, list):
    outC = open(file, "w")
    header = "ID,Longitude,Latitude\n"
    outC.write(header)
    for i, v in enumerate(list):
        cContent = "{0},{1},{2}\n".format(i, v[0], v[1])
        outC.write(cContent)
    outC.close()


# Path setting
scriptPath = sys.argv[0]
scriptDir = os.path.dirname(scriptPath)+"/"
theURL = "http://thematicmapping.org/downloads/TM_WORLD_BORDERS_SIMPL-0.3.zip"
zipBasename = os.path.basename(theURL)
archiveFile = scriptDir + zipBasename
unzipDest = scriptDir + "basemap/"
newName = "worldmap"
targetShp = unzipDest + newName + ".shp"
mxdPath = "../data/baseMapdocument.mxd"
symLyrPath = "../data/gradColorsLyr.lyr"


# Twitter API settings to access the users information from Twitter
# Developers can register and get the unique code from Twitter.
api = twitter.Api(consumer_key='',
                  consumer_secret='',
                  access_token_key='',
                  access_token_secret='',
                  sleep_on_rate_limit= True)


if not os.path.exists(unzipDest):
    os.mkdir(unzipDest)
    try:
        fetchZip(theURL, scriptDir)# Download the basemap from the website
        unzipArchive(archiveFile, unzipDest, newName)# And unzip it to the directory
        os.remove(archiveFile)
    except:
        traceback.print_exc()


# When the hashtag being searched repeatedly, the output coodinate file(.txt)
#   will be store in the same folder with different index, so that they won't overwrite
#   each other. The required parameters for this function are output directory and the
#   searched hashtag.
hashtag = raw_input("What hashtag do you want to search?")
try:
    if hashtag != None:
        outDir = scriptDir + hashtag + "/"
        cFile = outDir + hashtag + ".txt"
        if not os.path.exists(outDir):
            os.mkdir(outDir)
            
        fList = os.listdir(outDir)
        numOftxt = 0
        for f in fList:
            if f.endswith(".txt") and hashtag in f:
                numOftxt = numOftxt + 1
                cFile = outDir + hashtag + str(numOftxt) + ".txt"
except:
    print traceback.print_exc
    sys.exit() 


# First Call twitter API, use hashtag as raw query to get data
firstSearch = api.GetSearch(raw_query = "l=&q=%23{0}&count=100".format(hashtag))
numOfData = len(firstSearch)
idList = []
coorList = []
for f in firstSearch:
    try:
        idList.append(f.id)
        if f.coordinates != None:
            coorList.append(f.coordinates["coordinates"])
    except:
        print traceback.print_exc()


# Check remaining rate limit of Twitter API request and call twitter API again,
#   use hashtag and tweetID as raw query, so that we won't get repeated data
rateLimit = api.CheckRateLimit("https://api.twitter.com/1.1/application/rate_limit_status.json?resources=help,users,search,statuses")
if rateLimit.remaining > 50:
    while numOfData < 3500:
        try:
            minID = min(idList)
            keepSearch = api.GetSearch(raw_query = "l=&q=%23{0}&max_id={1}&count=100".format(hashtag, minID))
            numOfData = numOfData + len(keepSearch)
            for k in keepSearch:
                idList.append(k.id)
                if k.coordinates != None:
                    coorList.append(k.coordinates["coordinates"])
        except:
            print traceback.print_exc()

# Write coordinate data to file
write2File(cFile, coorList)

# Create coordinates point shapefile, then join the point and basemap shapefiles
arcpy.env.workspace = outDir
arcpy.env.overwriteOutput = 1
tempLyr = os.path.splitext(os.path.basename(cFile))[0]
lyrName = os.path.splitext(cFile)[0]+"_layer.lyr"
joinShp = tempLyr + ".shp"
joinOutput = os.path.splitext(cFile)[0]+ "_choroMap.shp"
proj = "WGS 1984"
try:
    arcpy.MakeXYEventLayer_management(cFile, "Longitude", "Latitude", tempLyr, proj)
    arcpy.SaveToLayerFile_management(tempLyr, lyrName)
    arcpy.FeatureClassToShapefile_conversion([lyrName], outDir)
    arcpy.SpatialJoin_analysis(targetShp, joinShp, joinOutput,
                               "JOIN_ONE_TO_ONE", "#", "#", "COMPLETELY_CONTAINS")
    arcpy.Delete_management(lyrName)
    print "Success"   
except arcpy.ExecuteError:
    print arcpy.GetMessages(2)   


# Edit the map layout
# Use the existing map document and symbology referenced layer to create a PNG output map
try:
    mxdName = os.path.join(scriptDir, mxdPath)
    symboLyr = os.path.join(scriptDir, symLyrPath)  
    mxd = arcpy.mapping.MapDocument(mxdName)
    dfs = arcpy.mapping.ListDataFrames(mxd)
    df = dfs[0]
    scaleLyr = arcpy.mapping.Layer(joinOutput)
    pointLyr = arcpy.mapping.Layer(joinShp)
    sourceLyr = arcpy.mapping.Layer(symboLyr)
    
    arcpy.mapping.AddLayer(df, scaleLyr)
    arcpy.mapping.AddLayer(df, pointLyr)
        
    lyrs = arcpy.mapping.ListLayers(mxd)
    layerToModify = lyrs[1]
    arcpy.mapping.UpdateLayer(df, layerToModify, sourceLyr)
        
    layerToModify.symbology.valueField = "Join_Count"        
    layerToModify.symbology.numClasses = 5
    arcpy.RefreshActiveView()
        
    imageName =  os.path.splitext(os.path.basename(cFile))[0]
    outputPNG = "Hashtag_{0}".format(imageName)
    arcpy.mapping.ExportToPNG(mxd, outDir + outputPNG)
    arcpy.Delete_management(joinOutput)
    arcpy.Delete_management(joinShp)
    os.remove(cFile)
except arcpy.ExecuteError:
    print arcpy.GetMessages(2)


# Write the title, hashtag, the image and the total searched data to HTML
try:
    htmlName = outDir + "index.html"
    htmlF = open(htmlName, "w")
    htmlHeader = '''<!DOCTYPE html>
    <html>
     <head>
     </head>
    '''.format(hashtag)
    
    htmlBody = '''
    <body bgcolor="#CEECF5">
     <h1 align="center">The twitter hashtag map</h1>
     <hr noshade width = "100%">
     <h2 align="center">#{0}</h2>
     <center><img src='{1}' ></center>\n'''.format(hashtag, outputPNG + ".png")

    htmlFooter = '''
     <footer>
      <p font size="20">The results came from {0} of tweets.</p>
     </footer>
    </body>
    </html>
    '''.format(str(numOfData))
    htmlF.write(htmlHeader + htmlBody + htmlFooter)
    htmlF.close()
except:
    print traceback.print_exc()