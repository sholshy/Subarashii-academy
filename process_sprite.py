from PIL import Image

def process():
    im = Image.open('carly_sprite.png').convert("RGBA")
    body = im.crop((0, 0, 510, 512))
    
    face_closed = im.crop((170, 512 + 170*2, 340, 512 + 170*3))
    face_open = im.crop((170, 512 + 0, 340, 512 + 170))
    
    # Try Y=85
    idle = body.copy()
    idle.paste(face_closed, (170, 85), face_closed)
    idle.save("carly_idle.png")
    
    talk = body.copy()
    talk.paste(face_open, (170, 85), face_open)
    talk.save("carly_talk.png")

if __name__ == '__main__':
    process()
