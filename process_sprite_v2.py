from PIL import Image
import os

base_path = r"c:\Users\shols\PycharmProjects\PythonProject3\Cache\Personaje\base.png"
base = Image.open(base_path).convert("RGBA")
print(f"Base size: {base.size}")

face_path = r"c:\Users\shols\PycharmProjects\PythonProject3\Cache\Personaje\cara (1).png"
face = Image.open(face_path).convert("RGBA")
print(f"Face size: {face.size}")

# If same size, composite them
if base.size == face.size:
    print("Same size! Compositing...")
    for i in range(1, 7):
        b = base.copy()
        f = Image.open(fr"c:\Users\shols\PycharmProjects\PythonProject3\Cache\Personaje\cara ({i}).png").convert("RGBA")
        b.paste(f, (0,0), f)
        b.save(fr"c:\Users\shols\PycharmProjects\PythonProject3\Cache\Personaje\talk_{i}.png")
    print("Done")
else:
    print("Different sizes, cannot paste at 0,0 directly.")
