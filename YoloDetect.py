import os
import sys
import argparse
import cv2
from ultralytics import YOLO

os.environ["KMP_DUPLICATE_LIB_OK"] = "TRUE"

parser = argparse.ArgumentParser()
parser.add_argument('--model', help='Path to YOLO model file (e.g., "weights/best.pt")',
                    required=True)
parser.add_argument('--source', help='Image source: image file ("test.jpg"), video file ("testvid.mp4"), or index of USB camera ("usb0")',
                    required=True)
parser.add_argument('--thresh', help='Minimum confidence threshold for displaying detected objects (e.g., "0.5")',
                    default=0.5)
parser.add_argument('--resolution', help='Resolution in WxH to display inference results (e.g., "640x480"). Only used for camera sources.',
                    default=None)

args = parser.parse_args()

model_path = args.model
img_source = args.source
min_thresh = float(args.thresh)
user_res = args.resolution

if not os.path.exists(model_path):
    print(f'ERROR: Model path "{model_path}" is invalid or model was not found.')
    sys.exit(0)

try:
    model = YOLO(model_path, task='detect')
    labels = model.names
except Exception as e:
    print(f"ERROR: Failed to load YOLO model. Check the file format. Error: {e}")
    sys.exit(0)

bbox_colors = [(164,120,87), (68,148,228), (93,97,209), (178,182,133), (88,159,106),
               (96,202,231), (159,124,168), (169,162,241), (98,118,150), (172,176,184)]

img_ext_list = ['.jpg','.jpeg','.png','.bmp']
vid_ext_list = ['.avi','.mov','.mp4','.mkv','.wmv']

cap = None
imgs_list = []
source_type = None
resize = False
resW, resH = None, None

if user_res:
    resize = True
    try:
        resW, resH = map(int, user_res.split('x'))
    except ValueError:
        print('Invalid resolution format. Use WxH (e.g., "640x480").')
        sys.exit(0)

if os.path.isfile(img_source):
    _, ext = os.path.splitext(img_source)
    ext = ext.lower()
    if ext in [x.lower() for x in img_ext_list]:
        source_type = 'image'
        imgs_list.append(img_source)
    elif ext in [x.lower() for x in vid_ext_list]:
        source_type = 'video'
        cap = cv2.VideoCapture(img_source)
    else:
        print(f'File extension {ext} is not supported.')
        sys.exit(0)
elif img_source.startswith('usb'):
    source_type = 'usb'
    try:
        usb_idx = int(img_source[3:])
        cap = cv2.VideoCapture(usb_idx)
        
        if user_res:
            cap.set(cv2.CAP_PROP_FRAME_WIDTH, resW)
            cap.set(cv2.CAP_PROP_FRAME_HEIGHT, resH)

    except ValueError:
        print(f'Invalid USB camera index in {img_source}. Must be an integer (e.g., "usb0").')
        sys.exit(0)
else:
    print(f'Input "{img_source}" is invalid. Must be an image file, video file, or USB index (e.g., "usb0").')
    sys.exit(0)

img_count = 0
while True:
    frame = None
    if source_type == 'image':
        if img_count >= len(imgs_list):
            print('All images have been processed. Exiting program.')
            break
        frame = cv2.imread(imgs_list[img_count])
        img_count += 1
        if frame is None:
            print(f'Warning: Could not read image {imgs_list[img_count-1]}. Skipping.')
            continue
    
    elif source_type == 'video' or source_type == 'usb':
        ret, frame = cap.read()
        if not ret or frame is None:
            print(f'{"Reached end of the video" if source_type == "video" else "Camera disconnected"}. Exiting program.')
            break
    
    if resize and source_type != 'usb':
        frame = cv2.resize(frame, (resW, resH))

    results = model(frame, verbose=False)
    detections = results[0].boxes

    for i in range(len(detections)):
        xyxy = detections[i].xyxy.cpu().numpy().squeeze()
        
        if xyxy.size == 0 or xyxy.ndim == 0: continue
        if xyxy.ndim > 1: xyxy = xyxy[0] 

        xmin, ymin, xmax, ymax = xyxy.astype(int)
        classidx = int(detections[i].cls.item())
        classname = labels[classidx]
        conf = detections[i].conf.item()

        if conf > min_thresh:
            color = bbox_colors[classidx % 10]
            cv2.rectangle(frame, (xmin,ymin), (xmax,ymax), color, 2)

            label = f'{classname}: {int(conf*100)}%'
            labelSize, baseLine = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1)
            label_ymin = max(ymin, labelSize[1] + 10)
            cv2.rectangle(frame, (xmin, label_ymin-labelSize[1]-10), (xmin+labelSize[0], label_ymin+baseLine-10), color, cv2.FILLED)
            cv2.putText(frame, label, (xmin, label_ymin-7), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 0), 1)

    cv2.imshow('YOLO Detection Results', frame)

    if source_type == 'image':
        key = cv2.waitKey()
    else:
        key = cv2.waitKey(5)

    if key in [ord('q'), ord('Q'), 27]:
        break
    elif key in [ord('s'), ord('S')]:
        cv2.waitKey()
    elif key in [ord('p'), ord('P')]:
        cv2.imwrite('capture.png', frame)

if cap is not None:
    cap.release()
cv2.destroyAllWindows()