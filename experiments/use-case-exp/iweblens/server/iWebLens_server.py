import numpy as np
import sys
import time
import cv2
import os
from flask import Flask, request, jsonify
import io
import json
from PIL import Image
import threading
import base64

# construct the argument parse and parse the arguments
confthres = 0.3
nmsthres = 0.1

def get_labels(labels_path):
    # load the COCO class labels our YOLO model was trained on
    lpath=os.path.sep.join([yolo_path, labels_path])

    print(yolo_path)
    LABELS = open(lpath).read().strip().split("\n")
    return LABELS

def get_colors(LABELS):
    # initialize a list of colors to represent each possible class label
    np.random.seed(42)
    COLORS = np.random.randint(0, 255, size=(len(LABELS), 3),dtype="uint8")
    return COLORS

def get_weights(weights_path):
    # derive the paths to the YOLO weights and model configuration
    weightsPath = os.path.sep.join([yolo_path, weights_path])
    return weightsPath

def get_config(config_path):
    configPath = os.path.sep.join([yolo_path, config_path])
    return configPath

def load_model(configpath,weightspath):
    # load our YOLO object detector trained on COCO dataset (80 classes)
    print("Loading YOLO from disk...")
    net = cv2.dnn.readNetFromDarknet(configpath, weightspath)
    return net

def get_prediction(image,net,LABELS,COLORS):
    
    (H, W) = image.shape[:2]
    # determine only the *output* layer names that we need from YOLO
    ln = net.getLayerNames()
    ln = [ln[i[0] - 1] for i in net.getUnconnectedOutLayers()]
    # ln = [ln[i-1] for i in net.getUnconnectedOutLayers()]

    # construct a blob from the input image and then perform a forward
    # pass of the YOLO object detector, giving us our bounding boxes and
    # associated probabilities
    blob = cv2.dnn.blobFromImage(image, 1 / 255.0, (416, 416),
                                 swapRB=True, crop=False)
    net.setInput(blob)
    start = time.time()
    layerOutputs = net.forward(ln)
    print(layerOutputs)
    end = time.time()

    # show timing information on YOLO
    print("YOLO took {:.6f} seconds".format(end - start))

    # initialize our lists of detected bounding boxes, confidences, and
    # class IDs, respectively
    boxes = []
    confidences = []
    classIDs = []

    # loop over each of the layer outputs
    for output in layerOutputs:
        # loop over each of the detections
        for detection in output:
            # extract the class ID and confidence (i.e., probability) of
            # the current object detection
            scores = detection[5:]
            # print(scores)
            classID = np.argmax(scores)
            # print(classID)
            confidence = scores[classID]

            # filter out weak predictions by ensuring the detected
            # probability is greater than the minimum probability
            if confidence > confthres:
                # scale the bounding box coordinates back relative to the
                # size of the image, keeping in mind that YOLO actually
                # returns the center (x, y)-coordinates of the bounding
                # box followed by the boxes' width and height
                box = detection[0:4] * np.array([W, H, W, H])
                (centerX, centerY, width, height) = box.astype("int")

                # use the center (x, y)-coordinates to derive the top and
                # and left corner of the bounding box
                x = int(centerX - (width / 2))
                y = int(centerY - (height / 2))

                # update our list of bounding box coordinates, confidences,
                # and class IDs
                boxes.append([x, y, int(width), int(height)])

                confidences.append(float(confidence))
                classIDs.append(classID)

    # apply non-maxima suppression to suppress weak, overlapping bounding
    # boxes
    idxs = cv2.dnn.NMSBoxes(boxes, confidences, confthres,
                            nmsthres)

    ## Prepare the output
    json_output = []
    # ensure at least one detection exists
    if len(idxs) > 0:
        # loop over the indexes we are keeping
        for i in idxs.flatten():

            detected_item = {"label": LABELS[classIDs[i]]}
            detected_item["accuracy"] = confidences[i]
            json_output.append(detected_item)
            detected_item ["rectangle"] =  {  "left": boxes[i][0],
                                              "top": boxes[i][1],
                                              "width": boxes[i][2],
                                              "height": boxes[i][3],
                                              }
            json_output.append(detected_item)

            # print("Box: {}, {}, {}, {}".format(boxes[i][0], boxes[i][1], boxes[i][2], boxes[i][3]))
    return  json_output

## argument
if len(sys.argv) != 2:
    raise ValueError("Argument list is wrong. Please use the following format:  {} {}".
                     format("python iWebLens_server.py", "<yolo_config_folder>"))

yolo_path  = str(sys.argv[1])

## Yolov3-tiny versrion
labels_path = "coco.names"
configs_path = "yolov3-tiny.cfg"
weights_path = "yolov3-tiny.weights"

labels = get_labels(labels_path)
configs = get_config(configs_path)
weights = get_weights(weights_path)
colors = get_colors(labels)

# Initialize the Flask application
app = Flask(__name__)
# route http posts to this method
@app.route('/api/object_detection', methods=['POST'])
def main():
    try:
        # load our input image and grab its spatial dimensions
        data = request.json

        id = data['id']
        print(f"Id: {id}")

        img = data['image']
        img = base64.b64decode(img)
        img = Image.open(io.BytesIO(img))
        npimg=np.array(img)
        image=npimg.copy()
        image=cv2.cvtColor(image,cv2.COLOR_BGR2RGB)

        # load the neural net.  Should be local to this method as its multi-threaded endpoint
        nets = load_model(configs, weights)
        print("### Model Loaded ###")
        result = get_prediction(image, nets, labels, colors)
        print("### Prediction Done ###")

        response = {}
        response['id'] = id
        response['objects'] = result

        # return the  result
        print(f"Result: {result}")
        return jsonify(response)
    except Exception as e:

        print(f"Exception in webservice call: {e}")

@app.route('/api/hello_world', methods=['GET'])
def hello_world():
    try:

       
        response = {}
        response['key1'] = "Hello World 1!"
        response['key2'] = "Hello World 2!"

        
        # # return the  result
        return jsonify(response)
    except Exception as e:
        print(f"Exception in hello world webservice call: {e}")

    # start flask app
if __name__ == '__main__':
    app.run( threaded = True,  debug=True, host='0.0.0.0', port = 5000)
