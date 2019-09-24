#!/usr/bin/python3

import sys
import os
import pyvips

if len(sys.argv) != 4:
    print("usage: tile-directory input-image output-image")
    sys.exit(1)

# the size of each tile ... 16x16 for the demo tiles
tile_size = 16

# load all the tile images, forcing them to the tile size
print(f"loading tiles from {sys.argv[1]} ...")
for root, dirs, files in os.walk(sys.argv[1]):
    tiles = [pyvips.Image.thumbnail(os.path.join(root, name), tile_size, 
                                    height=tile_size, size="force") 
             for name in files]

# drop any alpha
tiles = [image.flatten() if image.hasalpha() else image
         for image in tiles]

# copy the tiles to memory, since we'll be using them many times
tiles = [image.copy_memory() for image in tiles]

# calculate the average rgb for an image, eg. image -> [12, 13, 128]
def avg_rgb(image):
    m = image.stats()
    return [m(4,i)[0] for i in range(1,4)]

# find the avg rgb for each tile
tile_colours = [avg_rgb(image) for image in tiles]

# load the main image ... we can do this in streaming mode, since we only 
# make a single pass over the image
main = pyvips.Image.new_from_file(sys.argv[2], access="sequential")

# find the abs of an image, treating each pixel as a vector
def pyth(image):
    return sum([band ** 2 for band in image.bandsplit()]) ** 0.5

# calculate a distance map from the main image to each tile colour
distance = [pyth(main - colour) for colour in tile_colours]

# make a distance index -- hide the tile index in the bottom 16 bits of the
# distance measure
index = [(distance[i] << 16) + i for i in range(len(distance))]

# find the minimum distance for each pixel and mask out the bottom 16 bits to
# get the tile index for each pixel
index = index[0].bandrank(index[1:], index=0) & 0xffff

# replicate each tile image to make a set of layers, and zoom the index to
# make an index matching the output size
layers = [tile.replicate(main.width, main.height) for tile in tiles]
index = index.zoom(tile_size, tile_size)

# now for each layer, select pixels matching the index ... libvips 8.9 adds a
# `case` operator that can do this a little faster, but we just use 
# `ifthenelse`
final = pyvips.Image.black(main.width * tile_size, main.height * tile_size)
for i in range(len(layers)):
    final = (index == i).ifthenelse(layers[i], final)

print(f"writing {sys.argv[3]} ...")
final.write_to_file(sys.argv[3])
