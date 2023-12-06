import os
import string

from PIL import Image, ImageDraw, ImageFont

def makeStim(text, filePath, imgSize=(3840,2160), color="white", size=40):
    # `text` is the text to write on the stimulus. Must either be a string
    # containing a single line, or a list of such strings
    
    font = ImageFont.truetype("arial.ttf", size=size)
    _text = text
    if isinstance(_text, str):
        _text = [_text]
    
    # Create the image
    img = Image.new('RGB', imgSize, color='black')
    imgDraw = ImageDraw.Draw(img)
    
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
            
        y0 = xy[k - 1][1] if k > 0 else (imgSize[1] - totalHeight) / 2
        xy[k][1] = y0 + xy[k][1]
        
    # Write the text on the image
    for k, line in enumerate(_text):
        imgDraw.multiline_text(
            xy[k], 
            line, 
            font=font, 
            fill=color
        )
        
    # Save the image
    img.save(filePath)
    
def makeLetterStims(dirName, **kwargs):
    for s in string.ascii_uppercase:
        filePath = os.path.abspath(os.path.join(dirName, s + ".png"))
        makeStim(s, filePath, **kwargs)
        
def makeInstructions(filePath, **kwargs):
    instructions = [
        "Hello",
        "\n",
        "This is the instruction page :)",
        "Press the space bar to continue"
    ]
    makeStim(instructions, filePath, **kwargs)
    
def makeAllAssets(**kwargs):
    start = os.path.dirname(__file__)
    fileDir = os.path.abspath(os.path.join(start, "..", "assets"))
    os.makedirs(fileDir, exist_ok=True)
    
    makeLetterStims(fileDir, **kwargs)
    makeInstructions(os.path.join(fileDir, "instructions.png"), **kwargs)
    
if __name__=="__main__":
    makeAllAssets()