import math
import os
import string

import numpy as np
from PIL import Image, ImageDraw, ImageFont

def makeTextStim(text, filePath, imgSize=(1536,1024), color="white", size=40):
    # `text` is the text to write on the stimulus. Must either be a string
    # containing a single line, or a list of such strings
    
    font = ImageFont.truetype("arial.ttf", size=size)
    _text = text
    if isinstance(_text, str):
        _text = [_text]
    
    # Create the image
    img = Image.new('RGB', imgSize, color='black')
    imgDraw = ImageDraw.Draw(img)
    imgDraw.fontmode = "L"
    
    # Get the location of all text in the image
    xy = []
    # Find the width and height of each line, and the total height
    totalHeight = 0
    for line in _text:
        _, _, w, h = imgDraw.multiline_textbbox(
            (0, 0), 
            line, 
            font=font
        )
        xy.append([w, h])
        totalHeight += h
    # Center each line horizontally and the overall text vertically
    for k in range(len(xy)):
        xy[k][0] = (imgSize[0] - xy[k][0]) / 2
            
        y0 = (imgSize[1] - totalHeight) / 2 if k==0 else xy[k - 1][1] 
        xy[k][1] = y0 + (0 if k==0 else xy[k][1])
        
    # Write the text on the image
    for k, line in enumerate(_text):
        imgDraw.multiline_text(
            xy[k], 
            line, 
            font=font, 
            fill=color,
            align="center"
        )
        
    # Save the image
    img.save(filePath)
    
def makeLetterStims(dirName, **kwargs):
    for s in string.ascii_uppercase:
        filePath = os.path.abspath(os.path.join(dirName, s + ".png"))
        makeTextStim(s, filePath, **kwargs)
        
def makeInstructions(filePath, **kwargs):
    instructions = [
        "Hello",
        "\n",
        "This is the instruction page :)",
        "Press the space bar to continue"
    ]
    makeTextStim(instructions, filePath, **kwargs)
    
def makeFixationCross(filePath, size=(100,100), imgSize=(1536,1024), **kwargs):
    # Create the image
    img = Image.new('RGB', imgSize, color='black')
    imgDraw = ImageDraw.Draw(img)
    
    # Define the upper left and lower right corners of the cross bounding box
    # centered on the image
    box = np.floor(np.array([[-0.5, 0.5], [0.5, -0.5]]) * np.array(size))
    box = box + np.floor(np.array(imgSize) / 2)
    box = box.astype(int)
    
    # Define the coordinates for the horizontal and vertical lines of the cross
    center = box[0] + np.floor((box[1] - box[0]) / 2).astype(int)
    lines = []
    for k in range(2):
        lines.append(box.copy())
        lines[k][:,k] = center[k]
    
    # Draw the lines
    _kwargs = {"fill" : "white", "width" : 5}
    _kwargs.update(kwargs)
    for xy in lines:
        imgDraw.line(xy.flatten().tolist(), **_kwargs)
        
    # Save the image
    img.save(filePath)
    
    
def main(letter_kwargs={}, instructions_kwargs={}, cross_kwargs={}, **kwargs):
    # Make the instructions and letter stimuli
    
    start = os.path.dirname(__file__)
    fileDir = os.path.abspath(os.path.join(start, "..", "assets"))
    os.makedirs(fileDir, exist_ok=True)
    
    letter_kwargs.update(kwargs)
    makeLetterStims(fileDir, **letter_kwargs)
    
    filePath = os.path.join(fileDir, "instructions.png")
    instructions_kwargs.update(kwargs)
    makeInstructions(filePath, **instructions_kwargs)
    
    filePath = os.path.join(fileDir, "fixation_cross.png")
    cross_kwargs.update(kwargs)
    makeFixationCross(filePath, **cross_kwargs)
    
if __name__=="__main__":
    main(letter_kwargs={"size":64})