"""
This script runs the application using a development server.
It contains the definition of routes and views for the application.
"""

from flask import Flask, render_template, request, flash, redirect, url_for
import asyncio
import cv2
import io
import glob
import os
import sys
import time
import uuid
import requests
from urllib.parse import urlparse
from io import BytesIO
# To install this module, run:
# python -m pip install Pillow
from PIL import Image, ImageDraw
from azure.cognitiveservices.vision.face import FaceClient
from msrest.authentication import CognitiveServicesCredentials
from azure.cognitiveservices.vision.face.models import TrainingStatusType, Person

import json
from azure.storage.blob import BlobServiceClient, BlobClient, ContainerClient, __version__

KEY = "bb62ac5e759643cebae4c5c8a315e8d9"
ENDPOINT = "https://azuretestface.cognitiveservices.azure.com/"


app = Flask(__name__)
face_client = FaceClient(ENDPOINT, CognitiveServicesCredentials(KEY))

connect_str =  'DefaultEndpointsProtocol=https;AccountName=testazstorageaccount;AccountKey=K7UlluSxxom3lmtIZShvht2Jm6PQ+weYDE/JDHjPH8cx8QuevXISuaUl5GJZN8+J8TtjhVG3BqwrN7pdcdPzKA==;EndpointSuffix=core.windows.net'
container_name = "azureml-blobstore-483db3bd-786b-415c-9f70-0a40dc4e9373";
face_attributes = ['age', 'gender', 'headPose', 'smile', 'facialHair', 'glasses', 'emotion'];

PERSON_GROUP_ID = "";

# Make the WSGI interface available at the top level so wfastcgi can get it.
wsgi_app = app.wsgi_app
ALLOWED_EXTENSIONS = {'jpg', 'jpeg', 'JPG', 'JPEG'}
ALLOWED_EXTENSION_VID = {'mp4', 'MP4'}

def allowed_file(filename, allow_ex):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in allow_ex

@app.route('/', methods = ["GET", "POST"])
def hello():
    if request.method == "POST":               
        
        return render_template("registerFace.html", message="")
    return render_template("registerFace.html", message="")

@app.route('/Analysis', methods = ["GET", "POST"])
def helloanalysis():
    if request.method == "POST":               
        
        return render_template("AnalyzeVideo.html", message_analyse="")
    return render_template("AnalyzeVideo.html", message_analyse="")

@app.route('/profile/<message_in>', methods=["GET", "POST"])
def profile(message_in):    
    return render_template("registerFace.html", message=message_in)
    #return render_template("index.html", message=message_in)


@app.route('/video_profile/<message_in>', methods=["GET", "POST"])
def video_profile(message_in):    
    return render_template("AnalyzeVideo.html", message_analyse=message_in)
    #return render_template("index.html", message_analyse=message_in)

def getRectangle(faceDictionary):
    rect = faceDictionary.face_rectangle
    left = rect.left
    top = rect.top
    right = left + rect.width
    bottom = top + rect.height
    
    return ((left, top), (right, bottom))

def registerFace(user_name, dirname, uploadspath):
    responseMsg = "Face successfully registered"
    PERSON_GROUP_ID = user_name; # assign a random ID (or name it anything)
    print(PERSON_GROUP_ID)
    
    '''
    Create the PersonGroup
    '''
    # Create empty Person Group. Person Group ID must be lower case, alphanumeric, and/or with '-', '_'.
    print('Person group:', PERSON_GROUP_ID)
    face_client.person_group.create(person_group_id=PERSON_GROUP_ID, name=PERSON_GROUP_ID)

    # Define boy
    boy = face_client.person_group_person.create(PERSON_GROUP_ID, PERSON_GROUP_ID)

    '''
    Detect faces and register to correct person
    '''
    # Find all jpeg images of friends in working directory  
    # get current directory     
    boy_images = [file for file in glob.glob(os.path.join(uploadspath, dirname+'*.*'))]

    print(boy_images)
    # Add to a boy person
    try:
        for image in boy_images:
            bb = open(image, 'r+b')
            face_client.person_group_person.add_face_from_stream(PERSON_GROUP_ID, boy.person_id, bb)
    except Exception as e:
        return str(e)
    finally:
        bb.close()
    
    '''
    Train PersonGroup
    '''
    print()
    print('Training the person group...')
    # Train the person group
    face_client.person_group.train(PERSON_GROUP_ID)

    while (True):
        training_status = face_client.person_group.get_training_status(PERSON_GROUP_ID)
        print("Training status: {}.".format(training_status.status))
        print()
        if (training_status.status is TrainingStatusType.succeeded):
            responseMsg = "Face successfully registered"
            break
        elif (training_status.status is TrainingStatusType.failed):
            responseMsg = "Face Registration has failed, try again."
            break
        time.sleep(5)

    return responseMsg


@app.route('/register', methods = ["GET", "POST"])
def helloregister():
    if request.method == "POST":
        messagereturned = "";
        uploadspath = os.path.join(os.getcwd(), 'uploads')
        dirname = str(uuid.uuid4());
        try:
            if 'files[]' not in request.files:
                return render_template("registerFace.html", message="Please upload atleast 3 images")
                #return render_template("index.html", message="Please upload atleast 3 images")

            files = request.files.getlist('files[]')
            user_name = request.form["user_name"];

            for file in files:
                if file and allowed_file(file.filename, ALLOWED_EXTENSIONS):
                    file.save(os.path.join('uploads', dirname+file.filename))
                else:
                    messagereturned="Please upload jpg or jpeg";  
                    
            messagereturned=registerFace(user_name, dirname, uploadspath);
        except Exception as e:
            messagereturned = str(e);
        finally:
            for fname in os.listdir(uploadspath):
                if fname.startswith(dirname):
                    os.remove(os.path.join(uploadspath, fname))

            if messagereturned.find("(PersonGroupExists) Person group") == 0:
                messagereturned = "User Name already registered, Try another unique name.";
            return redirect(url_for('profile', message_in=messagereturned)) 
            #render_template("registerFace.html", message=messagereturned)
    return render_template("registerFace.html", message="")


def extract_imagesFromVid(pathIn, pathOut, dirname):
     count = 0
     vmax = 0
     successProcess = "success";
     try:
         vidcap = cv2.VideoCapture(pathIn)
         frames = vidcap.get(cv2.CAP_PROP_FRAME_COUNT)
         fps = int(vidcap.get(cv2.CAP_PROP_FPS))
    
         # calculate dusration of the video
         vmax = int(frames / fps) #seconds

         success,image = vidcap.read()
         while count<=vmax:
             vidcap.set(cv2.CAP_PROP_POS_MSEC,(count*1000))    # added this line 
             success,image = vidcap.read()
             print ('Read a new frame: ', success)
             pathhout = pathOut + "/" +dirname+ "frame%d.jpg" % count;
             cv2.imwrite(pathhout, image)     # save frame as JPEG file
             print(pathhout);
             count = count + 3

         successProcess = "success";
     except Exception as e:
         print(e);
         successProcess = e
     finally:
         return successProcess

def sendToAzure(aabbcc, face_key, face_name):
    try:
        blob_service_client = BlobServiceClient.from_connection_string(connect_str)
        container_client = blob_service_client.get_container_client(container_name)
        local_file_name = "face_"+str(uuid.uuid4()) + ".json"

        aabbjson = json.loads(aabbcc);
        aabbjson["face_key"] = face_key;
        aabbjson["face_name"] = face_name;

        aabbstr = json.dumps(aabbjson, default=vars)

        # Write text to the file
        file = open(local_file_name, 'w')
        file.write(aabbstr)
        file.close()

        # Create a blob client using the local file name as the name for the blob
        blob_client = blob_service_client.get_blob_client(container=container_name, blob=local_file_name)

        print("\nUploading to Azure Storage as blob:\n\t" + local_file_name)

        # Upload the created file
        with open(local_file_name, "rb") as data:
            blob_client.upload_blob(data)

        os.remove(local_file_name)
    except Exception as ex:
        print('Exception: Send to Azure failed..')
        print(ex)

def extractAttributesFromVidImgs(limit, directory, dirname, person_name):
    counter = 0
    PERSON_GROUP_ID = person_name;
    #limit=14;
    face_key = str(uuid.uuid4());
    for index, filename in zip(range(limit), os.listdir(directory)):
        if os.path.isfile(os.path.join(directory, filename)) and filename.startswith(dirname):
            try:
                testImage = 'img/'+filename;
                print("******START IMAGE******{}".format(testImage))
                test_image_array = glob.glob(testImage)
                # print(test_image_array)
                image = open(test_image_array[0], 'r+b')
                # print(image)
                face_ids = []
                counter = counter + 1;            
                if counter % 7 == 0:
                    print(counter)
                    time.sleep(60)

                faces = face_client.face.detect_with_stream(image, return_face_attributes=face_attributes);
            
                for face in faces:
                    face_ids.append(face.face_id)

                fset1 = face_ids[0:10]
                fset2 = face_ids[10:20]

                resultset1 = face_client.face.identify(fset1, PERSON_GROUP_ID)
                print('Identifying faces in {}'.format(os.path.basename(image.name)))
                if not resultset1:
                    print('No person identified in the person group for faces from {}.'.format(os.path.basename(image.name)))
                for person in resultset1:
                    if len(person.candidates) > 0:
                        print('Person for face ID {} is identified in {} with a confidence of {}.'.format(person.face_id, os.path.basename(image.name), person.candidates[0].confidence)) # Get topmost confidence score
                    else:
                        print('No person identified for face ID {} in {}.'.format(person.face_id, os.path.basename(image.name)))
            
                if len(fset2) > 0:
                    resultset2 = face_client.face.identify(fset2, PERSON_GROUP_ID)
                    print('Identifying faces in {}'.format(os.path.basename(image.name)))
                if not resultset2:
                    print('No person identified in the person group for faces from {}.'.format(os.path.basename(image.name)))
                for person in resultset2:
                    if len(person.candidates) > 0:
                        print('Person for face ID {} is identified in {} with a confidence of {}.'.format(person.face_id, os.path.basename(image.name), person.candidates[0].confidence)) # Get topmost confidence score
                    else:
                        print('No person identified for face ID {} in {}.'.format(person.face_id, os.path.basename(image.name)))

                conf = [];
                confInd = [];

                for r in range(len(resultset1)):
                    if len(resultset1[r].candidates) > 0:
                        for cc in range(len(resultset1[r].candidates)):
                            # print(resultset1[r].candidates[cc])
                            if len(conf) == 0:
                                conf.insert(0, resultset1[r].candidates[cc].confidence)
                                confInd.insert(0, r)
                            else:
                                if resultset1[r].candidates[cc].confidence > conf[0]:
                                    conf[0] = resultset1[r].candidates[cc].confidence
                                    confInd[0] = r

                if len(resultset2) > 0:
                    for r in range(len(resultset2)):
                        if len(resultset2[r].candidates) > 0:
                            for cc in range(len(resultset2[r].candidates)):
                                # print(resultset2[r].candidates[cc])
                                if len(conf) == 0:
                                    conf.insert(0, resultset2[r].candidates[cc].confidence)
                                    confInd.insert(0, r)
                                else:
                                    if resultset2[r].candidates[cc].confidence > conf[0]:
                                        conf[0] = resultset2[r].candidates[cc].confidence
                                    confInd[0] = r

                if len(confInd) > 0:
                    selectedFace = faces[confInd[0]]

                ii = Image.open(testImage)
                draw = ImageDraw.Draw(ii)
                draw.rectangle(getRectangle(selectedFace), outline='red')
                print(ii)

                face = selectedFace

                print(face.face_id)
                print()
                print('Facial attributes detected:')
                print('Age: ', face.face_attributes.age)
                print('Gender: ', face.face_attributes.gender)
                print('Head pose: ', face.face_attributes.head_pose)
                print('Smile: ', face.face_attributes.smile)
                print('Facial hair: ', face.face_attributes.facial_hair)
                print('Glasses: ', face.face_attributes.glasses)
                print('Emotion: ')
                print('\tAnger: ', face.face_attributes.emotion.anger)
                print('\tContempt: ', face.face_attributes.emotion.contempt)
                print('\tDisgust: ', face.face_attributes.emotion.disgust)
                print('\tFear: ', face.face_attributes.emotion.fear)
                print('\tHappiness: ', face.face_attributes.emotion.happiness)
                print('\tNeutral: ', face.face_attributes.emotion.neutral)
                print('\tSadness: ', face.face_attributes.emotion.sadness)
                print('\tSurprise: ', face.face_attributes.emotion.surprise)
                print()
                jsonResp = json.dumps(selectedFace, default=vars)
                sendToAzure(jsonResp, face_key, person_name)
            except Exception as e:
                print('Exception: extracting attributes from image failed..')
                print(e)
            finally:
                image.close()
                

def extractAttributesFromImgs(person_name, dirname, pathvid, uploadImgPath):
    PERSON_GROUP_ID = person_name;
    msgreturned = "success"
    try:
        boy = face_client.person_group.get(person_group_id=PERSON_GROUP_ID);

        messagereturned = extract_imagesFromVid(pathvid, uploadImgPath, dirname)
        if messagereturned == "success":
            directoryImg = os.path.join(os.getcwd(),'img');
            limit = len([name for name in os.listdir(directoryImg) if os.path.isfile(os.path.join(directoryImg, name)) and name.startswith(dirname)])    
            
            extractAttributesFromVidImgs(limit, directoryImg, dirname, person_name);
            msgreturned = "Video processed successfully.."
        else:
            return messagereturned;
    except Exception as ee:
        print(ee)
        msgreturned = ee;
    finally:
        return msgreturned;



@app.route('/analyse', methods = ["GET", "POST"])
def helloanalyse():
    if request.method == "POST":
        messagereturned = "success"
        uploadImgPath = os.path.join(os.getcwd(), 'img')
        dirname = str(uuid.uuid4());
        pathvid = "";
        face_user_name = request.form["user_name2"];
        try:
            # check if the post request has the file part
            if 'file' not in request.files:            
                return render_template("AnalyzeVideo.html", message_analyse="Please upload mp4 videos.");

            file = request.files['file'];
            if file.filename == '':
                return render_template("AnalyzeVideo.html", message_analyse="Please upload mp4 videos.");
            if file and allowed_file(file.filename, ALLOWED_EXTENSION_VID):
                boy123 = face_client.person_group.get(person_group_id=face_user_name);
                pathvid=os.path.join(os.getcwd(), dirname+file.filename);
                file.save(pathvid);
            else:
                messagereturned = "Please upload mp4 videos.";
                return render_template("AnalyzeVideo.html", message_analyse="Please upload mp4 videos.");
            
            messagereturned = extractAttributesFromImgs(face_user_name, dirname, pathvid, uploadImgPath)
                
        except Exception as e:
            messagereturned = str(e);
        finally:
            if os.path.exists(pathvid):
                os.remove(pathvid)

            for fname in os.listdir(uploadImgPath):
                if fname.startswith(dirname):
                    os.remove(os.path.join(uploadImgPath, fname))

            if messagereturned == "(PersonGroupNotFound) Person group is not found. (Parameter 'personGroupId')":
                messagereturned = "User name is not registered. Please register and try again.."

            return redirect(url_for("video_profile", message_in=messagereturned))

    return redirect(url_for("hello"))

if __name__ == '__main__':
    import os
    HOST = os.environ.get('SERVER_HOST', 'localhost')
    try:
        PORT = int(os.environ.get('SERVER_PORT', '5555'))
    except ValueError:
        PORT = 5555
    app.run(HOST, PORT)
